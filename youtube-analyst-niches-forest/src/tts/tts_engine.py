import os
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import numpy as np
import soundfile as sf
from src.core.config import settings
from src.models.schemas import CapCutCommentaryInterchange

logger = logging.getLogger(__name__)

class TTSEngine:
    """
    Engine chuyển văn bản thành giọng nói (Text-To-Speech):
    - Ưu tiên: Kokoro-82M (ONNX Local) - Giọng tiếng Anh truyền cảm, âm sắc tự nhiên như phim tài liệu / người làm vườn bản xứ.
    - Dự phòng & Mở rộng: Edge-TTS (Microsoft Neural) - Cực nhanh, hỗ trợ cả tiếng Anh và tiếng Việt.
    """

    VOICE_CATALOG = [
        # --- KOKORO-82M LOCAL VOICES (ENGLISH) ---
        {
            "id": "am_adam",
            "name": "Adam (US Male - Grounded Farm & Crafts)",
            "engine": "kokoro_local",
            "lang": "en",
            "accent": "US",
            "gender": "male",
            "description": "Tông trầm ấm, đĩnh đạc, mộc mạc; rất hợp video làm nông, vườn tược, thủ công, máy móc.",
            "recommended": True
        },
        {
            "id": "bm_george",
            "name": "George (UK Male - BBC Documentary)",
            "engine": "kokoro_local",
            "lang": "en",
            "accent": "UK",
            "gender": "male",
            "description": "Giọng nam Anh sang trọng, trầm bổng chuẩn phim tài liệu thiên nhiên Nat Geo / BBC.",
            "recommended": False
        },
        {
            "id": "af_bella",
            "name": "Bella (US Female - Warm & Expressive)",
            "engine": "kokoro_local",
            "lang": "en",
            "accent": "US",
            "gender": "female",
            "description": "Giọng nữ Mỹ ấm áp, truyền cảm, tự nhiên cho các cảnh thu hoạch, cây cỏ êm đềm.",
            "recommended": False
        },
        {
            "id": "am_michael",
            "name": "Michael (US Male - Clear Explainer)",
            "engine": "kokoro_local",
            "lang": "en",
            "accent": "US",
            "gender": "male",
            "description": "Giọng nam rõ ràng, tốc độ vừa phải, phù hợp phân tích kỹ thuật và hiện tượng.",
            "recommended": False
        },
        {
            "id": "bf_emma",
            "name": "Emma (UK Female - Nature & Story)",
            "engine": "kokoro_local",
            "lang": "en",
            "accent": "UK",
            "gender": "female",
            "description": "Giọng nữ Anh truyền cảm, phong thái kể chuyện sâu lắng.",
            "recommended": False
        },
        # --- EDGE-TTS CLOUD VOICES ---
        {
            "id": "en-US-ChristopherNeural",
            "name": "Christopher (US Male - Deep Baritone)",
            "engine": "edge_tts",
            "lang": "en",
            "accent": "US",
            "gender": "male",
            "description": "Giọng nam Mỹ trầm sâu, uy quyền, chuẩn dẫn phim tài liệu.",
            "recommended": False
        },
        {
            "id": "en-GB-RyanNeural",
            "name": "Ryan (UK Male - Storyteller)",
            "engine": "edge_tts",
            "lang": "en",
            "accent": "UK",
            "gender": "male",
            "description": "Giọng nam Anh tự nhiên, phong cách dẫn chuyện hiện đại.",
            "recommended": False
        },
        {
            "id": "vi-VN-NamMinhNeural",
            "name": "Nam Minh (VN Male - Chân chất)",
            "engine": "edge_tts",
            "lang": "vi",
            "accent": "VN",
            "gender": "male",
            "description": "Giọng nam Việt Nam rõ ràng, ấm áp (dành cho kịch bản tiếng Việt).",
            "recommended": False
        }
    ]

    def __init__(self, models_dir: Optional[Path] = None):
        self.models_dir = models_dir or (Path(__file__).parent.parent.parent / "models" / "tts")
        self.kokoro_model_path = self.models_dir / "kokoro-v1.0.onnx"
        self.kokoro_voices_path = self.models_dir / "voices-v1.0.bin"
        self._kokoro_instance = None
        self._kokoro_initialized = False

    def get_available_voices(self) -> List[Dict]:
        """Trả về danh mục giọng đọc có sẵn kèm trạng thái sẵn sàng của Kokoro"""
        kokoro_ready = self.is_kokoro_available()
        catalog = []
        for v in self.VOICE_CATALOG:
            item = dict(v)
            if item["engine"] == "kokoro_local":
                item["available"] = kokoro_ready
            else:
                item["available"] = True
            catalog.append(item)
        return catalog

    def is_kokoro_available(self) -> bool:
        """Kiểm tra file model Kokoro đã tải về chưa"""
        return self.kokoro_model_path.exists() and self.kokoro_voices_path.exists()

    def _get_kokoro(self):
        """Khởi tạo Kokoro-82M on-demand (lazy load)"""
        if not self._kokoro_initialized:
            if not self.is_kokoro_available():
                logger.warning("Kokoro model files not found in models/tts. Fallback to Edge-TTS.")
                return None
            try:
                from kokoro_onnx import Kokoro
                logger.info(f"Loading Kokoro-82M model from {self.kokoro_model_path}...")
                self._kokoro_instance = Kokoro(
                    model_path=str(self.kokoro_model_path),
                    voices_path=str(self.kokoro_voices_path)
                )
                self._kokoro_initialized = True
                logger.info("Kokoro-82M model loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize Kokoro-82M: {e}")
                self._kokoro_instance = None
                self._kokoro_initialized = True
        return self._kokoro_instance

    def synthesize_text(
        self,
        text: str,
        voice: str = "am_adam",
        speed: float = 1.0,
        output_path: Optional[str] = None
    ) -> Tuple[str, float]:
        """
        Sinh âm thanh từ 1 đoạn text:
        - Trả về (file_path, duration_seconds)
        """
        text = text.strip()
        if not text:
            raise ValueError("Văn bản cần chuyển sang giọng nói không được rỗng.")

        if not output_path:
            import uuid
            output_path = str(settings.TEMP_DIR / f"tts_{uuid.uuid4().hex[:8]}.wav")

        # Xác định engine dựa trên voice id
        kokoro = self._get_kokoro()
        is_kokoro_voice = any(v["id"] == voice and v["engine"] == "kokoro_local" for v in self.VOICE_CATALOG)

        if is_kokoro_voice and kokoro is not None:
            try:
                lang = "en-us"
                if voice.startswith("bm_") or voice.startswith("bf_"):
                    lang = "en-gb"
                samples, sample_rate = kokoro.create(text, voice=voice, speed=speed, lang=lang)
                sf.write(output_path, samples, sample_rate)
                duration = len(samples) / sample_rate
                return output_path, round(duration, 3)
            except Exception as e:
                logger.warning(f"Kokoro synthesis failed for voice '{voice}': {e}. Falling back to Edge-TTS.")

        # Fallback hoặc chọn Edge-TTS
        return self._synthesize_with_edge_tts(text, voice, speed, output_path)

    def _synthesize_with_edge_tts(
        self,
        text: str,
        voice: str,
        speed: float,
        output_path: str
    ) -> Tuple[str, float]:
        """Sinh âm thanh bằng Edge-TTS"""
        import edge_tts

        edge_voice = voice
        # Nếu voice là id của Kokoro nhưng phải fallback sang Edge-TTS:
        if voice.startswith("am_"):
            edge_voice = "en-US-ChristopherNeural"
        elif voice.startswith("bm_"):
            edge_voice = "en-GB-RyanNeural"
        elif voice.startswith("af_") or voice.startswith("bf_"):
            edge_voice = "en-US-JennyNeural"

        # Tính toán speed rate của edge-tts (ví dụ: +0%, +10%, -10%)
        rate_percent = int(round((speed - 1.0) * 100))
        rate_str = f"{rate_percent:+d}%"

        temp_mp3 = output_path if output_path.endswith(".mp3") else output_path.replace(".wav", ".mp3")
        
        async def _run():
            communicate = edge_tts.Communicate(text, edge_voice, rate=rate_str)
            await communicate.save(temp_mp3)

        asyncio.run(_run())

        # Đọc file để xác định thời lượng chính xác
        try:
            data, sr = sf.read(temp_mp3)
            duration = len(data) / sr
            # Nếu output_path cần là .wav, chuyển đổi bằng soundfile
            if output_path.endswith(".wav"):
                sf.write(output_path, data, sr)
                if os.path.exists(temp_mp3) and temp_mp3 != output_path:
                    os.remove(temp_mp3)
                return output_path, round(duration, 3)
            return temp_mp3, round(duration, 3)
        except Exception as e:
            logger.error(f"Error reading edge-tts audio: {e}")
            return temp_mp3, 0.0

    def synthesize_script(
        self,
        script: CapCutCommentaryInterchange,
        voice: str = "am_adam",
        speed: float = 1.0,
        output_path: Optional[str] = None
    ) -> Tuple[str, float]:
        """
        Sinh âm thanh hoàn chỉnh cho toàn bộ kịch bản CapCut:
        1. Sinh giọng nói cho từng phân đoạn (Segment).
        2. Đo chính xác độ dài từng câu và điều chỉnh thời gian kết thúc của phụ đề khớp đúng với âm thanh.
        3. Ghép nối các phân đoạn vào 1 file master audio duy nhất, đồng bộ mốc giây bắt đầu.
        4. Cập nhật metadata của script.
        """
        video_id = script.video_metadata.video_id
        if not output_path:
            video_dir = settings.get_video_export_dir(video_id)
            output_path = str(video_dir / f"{video_id}_voiceover.wav")

        total_duration = max(script.video_metadata.duration_seconds, 1.0)
        kokoro = self._get_kokoro()
        is_kokoro_voice = any(v["id"] == voice and v["engine"] == "kokoro_local" for v in self.VOICE_CATALOG)
        
        use_kokoro = is_kokoro_voice and kokoro is not None

        target_sr = 24000 if use_kokoro else 24000
        master_samples = np.zeros(int(target_sr * (total_duration + 5.0)), dtype=np.float32)
        seg_temp_paths: List[Path] = []

        try:
            cursor_sec = 0.0
            for seg in script.segments:
                text = seg.voiceover.strip()
                if not text:
                    continue

                start_sec = min(total_duration, max(cursor_sec, 0.0))
                seg.time_range.start = round(start_sec, 2)
                seg_temp_path = str(settings.TEMP_DIR / f"{video_id}_seg_{seg.beat}_{start_sec:.1f}.wav")
                seg_temp_paths.append(Path(seg_temp_path))
                seg_temp_paths.append(Path(seg_temp_path.replace(".wav", ".mp3")))

                # Sinh audio cho segment
                try:
                    audio_file, seg_dur = self.synthesize_text(text, voice=voice, speed=speed, output_path=seg_temp_path)
                    data, sr = sf.read(audio_file)
                    # Resample nếu khác sample rate
                    if sr != target_sr:
                        import scipy.signal
                        num_samples = int(len(data) * target_sr / sr)
                        data = scipy.signal.resample(data, num_samples).astype(np.float32)

                    # Chuyển stereo sang mono nếu cần
                    if data.ndim > 1:
                        data = data.mean(axis=1)

                    data = data.astype(np.float32)
                    seg_dur = len(data) / target_sr

                    # Tự động đồng bộ lại thời điểm kết thúc phân đoạn theo độ dài nói thực tế
                    next_start = total_duration
                    actual_end = round(min(start_sec + seg_dur + 0.15, next_start, total_duration), 2)
                    if actual_end <= start_sec:
                        continue
                    seg.time_range.end = actual_end
                    cursor_sec = actual_end

                    # Đặt vào master track đúng mốc thời gian start_sec
                    start_idx = int(start_sec * target_sr)
                    end_idx = min(start_idx + len(data), int(min(actual_end, total_duration) * target_sr))
                    if end_idx <= start_idx:
                        continue
                    data = data[:end_idx - start_idx]

                    if end_idx > len(master_samples):
                        # Mở rộng mảng nếu vượt quá thời lượng dự kiến
                        master_samples = np.pad(master_samples, (0, end_idx - len(master_samples) + int(target_sr * 2)))

                    # Chèn vào master track (tránh đè chồng lệch bằng phép cộng hoặc thay thế)
                    master_samples[start_idx:end_idx] = data

                except Exception as e:
                    logger.error(f"Error synthesizing segment '{seg.beat}': {e}")

            # Cắt bớt phần im lặng thừa ở đuôi master track
            final_sample_count = int(max(script.video_metadata.duration_seconds, 1.0) * target_sr)
            # Giữ lại ít nhất đến hết tiếng nói cuối cùng
            last_non_zero = np.where(np.abs(master_samples) > 1e-4)[0]
            if len(last_non_zero) > 0:
                final_sample_count = max(final_sample_count, last_non_zero[-1] + int(target_sr * 0.5))

            master_samples = master_samples[:final_sample_count]

            # Ghi master file
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            sf.write(output_path, master_samples, target_sr)
            final_dur = len(master_samples) / target_sr

            # Cập nhật metadata
            script.video_metadata.voiceover_audio_file = Path(output_path).name
            script.video_metadata.voiceover_voice = voice

            logger.info(f"Master voiceover synthesized: {output_path} (Duration: {final_dur:.2f}s, Voice: {voice})")
            return output_path, round(final_dur, 2)
        finally:
            for tmp_seg in seg_temp_paths:
                try:
                    if tmp_seg.exists() and tmp_seg.resolve() != Path(output_path).resolve():
                        tmp_seg.unlink()
                except Exception as cleanup_err:
                    logger.debug(f"Could not clean segment temp file {tmp_seg}: {cleanup_err}")


# Khởi tạo instance dùng chung
tts_engine = TTSEngine()
