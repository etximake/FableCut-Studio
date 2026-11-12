import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from src.core.config import settings
from src.models.schemas import AudioHint

logger = logging.getLogger(__name__)

HANGING_CONJUNCTIONS_VI = {"nhưng", "và", "bởi vì", "cho nên", "vì thế", "thế là", "mà", "thì", "nếu", "hoặc"}
HANGING_CONJUNCTIONS_EN = {"and", "but", "so", "because", "although", "which", "that", "if", "or", "while"}

class LocalVideoPreprocessor:
    """
    Module tiền xử lý video cục bộ bằng FFmpeg & Whisper:
    1. Trích xuất Smart Contact Sheet 3x3 có in sẵn Timestamp.
    2. Bóc tách âm thanh, lọc nhiễu dải tần.
    3. Chống ảo giác Whisper và phát hiện câu thoại bị cắt đầu/cụt đuôi.
    """

    def __init__(self, temp_dir: Optional[Path] = None):
        self.temp_dir = temp_dir or settings.TEMP_DIR
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def get_video_info(self, video_path: str) -> Dict[str, Any]:
        """Lấy thông số kỹ thuật (thời lượng, kích thước, audio stream) qua ffprobe"""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            video_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
        
        duration = float(data.get("format", {}).get("duration", 0.0))
        has_audio = any(s.get("codec_type") == "audio" for s in data.get("streams", []))
        
        video_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))

        return {
            "duration": duration,
            "width": width,
            "height": height,
            "has_audio": has_audio
        }

    def generate_contact_sheet(
        self,
        video_path: str,
        duration: float,
        output_path: Optional[str] = None
    ) -> str:
        """
        Trích xuất 9 khung hình cách đều nhau trong suốt thời lượng video,
        in nhãn mốc giây [MM:SS] lên góc ảnh và ghép thành lưới 3x3 (1 file ảnh duy nhất).
        """
        if not output_path:
            base_name = Path(video_path).stem
            output_path = str(self.temp_dir / f"{base_name}_contact_sheet_3x3.jpg")

        # Đảm bảo duration > 0
        safe_duration = max(duration, 1.0)
        fps_expr = f"9/{safe_duration}"

        # Filter graph: rút 9 frame -> scale chuẩn 640x360 -> in timestamp -> ghép tile 3x3
        vf_filter = (
            f"fps={fps_expr},"
            f"scale=640:360:force_original_aspect_ratio=decrease,"
            f"pad=640:360:(ow-iw)/2:(oh-ih)/2,"
            f"drawtext=text='%{{pts\\:gmtime\\:0\\:%M\\\\\\:%S}}':x=20:y=20:fontsize=32:fontcolor=yellow:box=1:boxcolor=black@0.7:boxborderw=5,"
            f"tile=3x3"
        )

        cmd = [
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-vf", vf_filter,
            "-frames:v", "1",
            "-q:v", "3",
            output_path
        ]

        logger.info(f"Generating contact sheet 3x3: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr}")
            # Fallback nếu drawtext lỗi font trên một số phiên bản: bỏ drawtext
            fallback_vf = f"fps={fps_expr},scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2,tile=3x3"
            fallback_cmd = ["ffmpeg", "-y", "-i", video_path, "-vf", fallback_vf, "-frames:v", "1", "-q:v", "3", output_path]
            subprocess.run(fallback_cmd, capture_output=True, text=True, check=True)

        return output_path

    def extract_clean_audio(self, video_path: str, output_path: Optional[str] = None) -> Optional[str]:
        """Bóc tách âm thanh kèm bộ lọc dải tần (highpass 200Hz, lowpass 3500Hz, de-noiser)"""
        if not output_path:
            base_name = Path(video_path).stem
            output_path = str(self.temp_dir / f"{base_name}_clean_audio.wav")

        af_filter = "highpass=f=200,lowpass=f=3500,afftdn=nf=-25,dynaudnorm"
        cmd = [
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-vn",
            "-af", af_filter,
            "-ar", "16000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning(f"Audio extraction failed (video may be silent): {result.stderr}")
            return None
        return output_path

    def analyze_audio_truncation(self, audio_path: Optional[str], video_duration: float) -> AudioHint:
        """
        Nhận diện giọng nói với Whisper và phân tích câu thoại bị cắt đầu/cụt đuôi.
        """
        if not audio_path or not os.path.exists(audio_path):
            return AudioHint(
                has_speech=False,
                status="NO_MEANINGFUL_SPEECH",
                clean_text="",
                duration_seconds=0.0,
                is_reliable=True,
                guidance="Video không có âm thanh. Dựa 100% vào hình ảnh trên Contact Sheet để viết lời bình."
            )

        # Thử nạp faster-whisper nếu môi trường có cài đặt
        transcription_text = ""
        is_speech_detected = False
        segments_data = []

        try:
            from faster_whisper import WhisperModel
            # Sử dụng model tiny hoặc base để chạy siêu tốc trong < 1s
            model = WhisperModel("base", device="cpu", compute_type="int8")
            segments, info = model.transcribe(audio_path, vad_filter=True, language=None)
            
            for seg in segments:
                if seg.no_speech_prob < 0.6:
                    segments_data.append({"start": seg.start, "end": seg.end, "text": seg.text.strip()})
            
            if segments_data:
                is_speech_detected = True
                transcription_text = " ".join(s["text"] for s in segments_data)
        except Exception as e:
            logger.warning(f"Local faster-whisper not available or error ({e}). Proceeding without speech text.")

        if not is_speech_detected or not transcription_text.strip():
            return AudioHint(
                has_speech=False,
                status="NO_MEANINGFUL_SPEECH",
                clean_text="",
                duration_seconds=video_duration,
                is_reliable=True,
                guidance="Không phát hiện giọng nói rõ ràng hoặc chỉ có nhạc nền/tạp âm. Ưu tiên 100% vào hình ảnh Contact Sheet."
            )

        # Kiểm tra cắt đầu / cụt đuôi
        first_seg = segments_data[0]
        last_seg = segments_data[-1]
        
        is_truncated_start = False
        is_truncated_end = False

        first_word = first_seg["text"].split()[0].lower() if first_seg["text"] else ""
        if first_seg["start"] < 0.6 and (first_word in HANGING_CONJUNCTIONS_VI or first_word in HANGING_CONJUNCTIONS_EN):
            is_truncated_start = True

        last_char = last_seg["text"][-1] if last_seg["text"] else ""
        if (video_duration - last_seg["end"] < 0.8) and last_char not in {".", "!", "?"}:
            is_truncated_end = True

        status = "COMPLETE"
        if is_truncated_start and is_truncated_end:
            status = "TRUNCATED_BOTH"
        elif is_truncated_start:
            status = "TRUNCATED_START"
        elif is_truncated_end:
            status = "TRUNCATED_END"

        guidance = "Câu thoại hoàn chỉnh. Có thể kết hợp cả hình ảnh và lời thoại gốc."
        if status != "COMPLETE":
            guidance = (
                f"CẢNH BÁO: Phát hiện câu thoại bị cắt cụt ({status}) từ clip dài. "
                "Chỉ kế thừa các thuật ngữ khoa học/số liệu nếu có, TUYỆT ĐỐI không nối tiếp câu nói dở dang; "
                "dựa vào hình ảnh Contact Sheet để tự viết lời bình mới."
            )

        return AudioHint(
            has_speech=True,
            status=status,
            clean_text=transcription_text,
            duration_seconds=video_duration,
            is_reliable=(status == "COMPLETE"),
            guidance=guidance
        )

    def process(self, video_path: str) -> Tuple[str, AudioHint, float]:
        """
        Quy trình xử lý hoàn chỉnh đầu vào:
        Trả về (đường_dẫn_ảnh_lưới_3x3, đối_tượng_audio_hint, thời_lượng_video)
        """
        info = self.get_video_info(video_path)
        duration = info["duration"]
        
        # 1. Trích xuất Smart Contact Sheet 3x3
        contact_sheet_path = self.generate_contact_sheet(video_path, duration)
        
        # 2. Xử lý âm thanh
        audio_path = None
        if info["has_audio"]:
            audio_path = self.extract_clean_audio(video_path)
        audio_hint = self.analyze_audio_truncation(audio_path, duration)

        return contact_sheet_path, audio_hint, duration
