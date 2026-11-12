import json
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Tuple, Optional
from src.core.config import settings
from src.models.schemas import CapCutCommentaryInterchange

logger = logging.getLogger(__name__)

class ExportResult:
    """Kết quả xuất file bao gồm CapCut JSON, phụ đề SRT, Voiceover Audio, Video gốc và Hình ảnh"""
    def __init__(
        self,
        json_path: str,
        srt_path: str,
        audio_path: Optional[str] = None,
        srt_vi_path: Optional[str] = None,
        contact_sheet_path: Optional[str] = None,
        thumbnail_path: Optional[str] = None,
        video_path: Optional[str] = None
    ):
        self.json_path = json_path
        self.srt_path = srt_path
        self.audio_path = audio_path
        self.srt_vi_path = srt_vi_path
        self.contact_sheet_path = contact_sheet_path
        self.thumbnail_path = thumbnail_path
        self.video_path = video_path

    def __iter__(self):
        # Giữ tính tương thích ngược cho các đoạn mã giải nén 2 phần tử (json_path, srt_path)
        return iter((self.json_path, self.srt_path))

    def __getitem__(self, item):
        return (self.json_path, self.srt_path)[item]

    def __repr__(self):
        return f"<ExportResult json={self.json_path} srt={self.srt_path} audio={self.audio_path} video={self.video_path} contact_sheet={self.contact_sheet_path} thumb={self.thumbnail_path}>"

class CapCutExporter:
    """Xuất kịch bản ra định dạng CapCut Interchange JSON v3, phụ đề SRT, âm thanh Voiceover và ảnh"""

    def __init__(self, exports_dir: Path = None):
        self._custom_exports_dir = exports_dir
        self.exports_dir.mkdir(parents=True, exist_ok=True)

    @property
    def exports_dir(self) -> Path:
        d = self._custom_exports_dir or settings.EXPORTS_DIR
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _seconds_to_srt_time(self, seconds: float) -> str:
        """Chuyển số giây sang định dạng giờ:phút:giây,mili (00:00:04,500)"""
        hrs = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int(round((seconds - int(seconds)) * 1000))
        return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"

    def generate_thumbnail(self, video_path: str, output_path: str, timestamp: float = 2.0) -> bool:
        """Trích xuất 1 khung hình làm thumbnail chất lượng cao bằng FFmpeg"""
        try:
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(max(0.0, timestamp)),
                "-i", str(video_path),
                "-vframes", "1",
                "-q:v", "2",
                str(output_path)
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return res.returncode == 0 and Path(output_path).exists()
        except Exception as e:
            logger.warning(f"Failed to generate thumbnail: {e}")
            return False

    def export(
        self,
        script: CapCutCommentaryInterchange,
        audio_path: Optional[str] = None,
        contact_sheet_path: Optional[str] = None,
        video_path: Optional[str] = None,
        sync_to_fablecut_data: bool = False
    ) -> ExportResult:
        """
        Lưu file .capcut.json, file .srt, voiceover audio, contact sheet 3x3 và thumbnail vào exports.
        Đồng thời tùy chọn đồng bộ sang fablecut-data/media/.
        """
        video_id = script.video_metadata.video_id
        video_dir = settings.get_video_export_dir(video_id, base_dir=self.exports_dir)
        json_filename = f"{video_id}_commentary.capcut.json"
        srt_filename = f"{video_id}_subtitles.srt"
        srt_vi_filename = f"{video_id}_subtitles_vi.srt"

        json_path = video_dir / json_filename
        srt_path = video_dir / srt_filename
        srt_vi_path = video_dir / srt_vi_filename
        final_video_path = None
        final_audio_path = None
        final_cs_path = None
        final_thumb_path = None

        # 1. Xử lý Video Footage nếu có
        if video_path and Path(video_path).exists():
            ext = Path(video_path).suffix or ".mp4"
            target_video = video_dir / f"{video_id}{ext}"
            if Path(video_path).resolve() != target_video.resolve():
                shutil.copy2(video_path, target_video)
            final_video_path = str(target_video)
        else:
            for ext in (".mp4", ".mov", ".mkv", ".webm"):
                existing_video = video_dir / f"{video_id}{ext}"
                if existing_video.exists():
                    final_video_path = str(existing_video)
                    break
                flat_video = self.exports_dir / f"{video_id}{ext}"
                if flat_video.exists():
                    final_video_path = str(flat_video)
                    break

        # 2. Xử lý Voiceover Audio nếu có
        if audio_path and Path(audio_path).exists():
            ext = Path(audio_path).suffix or ".wav"
            target_audio = video_dir / f"{video_id}_voiceover{ext}"
            if Path(audio_path).resolve() != target_audio.resolve():
                shutil.copy2(audio_path, target_audio)
            final_audio_path = str(target_audio)
            script.video_metadata.voiceover_audio_file = target_audio.name
        else:
            for ext in (".wav", ".mp3"):
                existing_audio = video_dir / f"{video_id}_voiceover{ext}"
                if existing_audio.exists():
                    final_audio_path = str(existing_audio)
                    script.video_metadata.voiceover_audio_file = existing_audio.name
                    break

        # 3. Xử lý Contact Sheet 3x3
        target_cs = video_dir / f"{video_id}_contact_sheet_3x3.jpg"
        source_cs = None
        if contact_sheet_path and Path(contact_sheet_path).exists():
            source_cs = Path(contact_sheet_path)
        elif target_cs.exists():
            source_cs = target_cs
        elif (self.exports_dir / f"{video_id}_contact_sheet_3x3.jpg").exists():
            source_cs = self.exports_dir / f"{video_id}_contact_sheet_3x3.jpg"
        else:
            # Tìm trong TEMP_DIR
            matches = list(settings.TEMP_DIR.glob(f"*{video_id}*_contact_sheet_3x3.jpg"))
            if matches:
                source_cs = matches[0]

        if source_cs and source_cs.exists():
            if source_cs.resolve() != target_cs.resolve():
                shutil.copy2(source_cs, target_cs)
            final_cs_path = str(target_cs)
            script.video_metadata.contact_sheet_file = target_cs.name

        # 4. Xử lý Thumbnail poster
        target_thumb = video_dir / f"{video_id}_thumbnail.jpg"
        thumb_source_video = video_path if (video_path and Path(video_path).exists()) else final_video_path
        if thumb_source_video and Path(thumb_source_video).exists():
            # Chọn mốc giây từ CLIMAX hoặc HOOK nếu có
            thumb_time = 2.0
            for seg in script.segments:
                if seg.beat in ("CLIMAX", "CLIMAX_SLOWMO", "TREATMENT", "AFTER", "REVEAL", "TURN", "STEP_2", "RELIEF", "VERDICT", "PAYOFF", "HOOK", "EMERGENCY", "QUESTION", "BEFORE", "CHARACTER", "SETUP"):
                    thumb_time = (seg.time_range.start + seg.time_range.end) / 2.0
                    break
                elif seg.beat in ("HOOK", "SETUP"):
                    thumb_time = (seg.time_range.start + seg.time_range.end) / 2.0

            if self.generate_thumbnail(thumb_source_video, str(target_thumb), timestamp=thumb_time):
                final_thumb_path = str(target_thumb)
                script.video_metadata.thumbnail_file = target_thumb.name
        elif target_thumb.exists():
            final_thumb_path = str(target_thumb)
            script.video_metadata.thumbnail_file = target_thumb.name

        # 5. Lưu file CapCut JSON (đã bao gồm thông tin ảnh mới nhất)
        interchange = script.model_dump()
        schema_path = Path(__file__).resolve().parents[3] / "fablecut-bundle" / "schema" / "input_schema.json"
        if not schema_path.is_file():
            raise FileNotFoundError(f"FableCut interchange schema not found: {schema_path}")
        try:
            import jsonschema
        except ImportError as exc:
            raise RuntimeError("jsonschema is required to validate FableCut interchange exports") from exc
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.Draft7Validator(schema).validate(interchange)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(interchange, f, ensure_ascii=False, indent=2)

        # 6. Tạo và lưu file SRT gốc
        srt_lines = []
        for idx, seg in enumerate(script.segments, start=1):
            start_str = self._seconds_to_srt_time(seg.time_range.start)
            end_str = self._seconds_to_srt_time(seg.time_range.end)
            text = seg.voiceover.strip()

            srt_lines.append(f"{idx}")
            srt_lines.append(f"{start_str} --> {end_str}")
            srt_lines.append(text)
            srt_lines.append("")

        with open(srt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(srt_lines))

        # 7. Tạo và lưu file SRT phụ đề dịch nghĩa tiếng Việt
        srt_vi_lines = []
        for idx, seg in enumerate(script.segments, start=1):
            start_str = self._seconds_to_srt_time(seg.time_range.start)
            end_str = self._seconds_to_srt_time(seg.time_range.end)
            text_vi = (seg.voiceover_vi_translation or seg.voiceover).strip()

            srt_vi_lines.append(f"{idx}")
            srt_vi_lines.append(f"{start_str} --> {end_str}")
            srt_vi_lines.append(text_vi)
            srt_vi_lines.append("")

        with open(srt_vi_path, "w", encoding="utf-8") as f:
            f.write("\n".join(srt_vi_lines))

        # 8. Đồng bộ sang fablecut-data/media/<video_id>/ nếu thư mục exports khác fablecut-data và không phải test custom dir
        if sync_to_fablecut_data and self._custom_exports_dir is None:
            possible_media_dirs = [
                settings.DATA_DIR.parent.parent / "fablecut-data" / "media",
                Path("D:/HOANG HA/Deverlopper Software/FableCut-Studio/fablecut-data/media")
            ]
            fablecut_media = next((d for d in possible_media_dirs if d.exists()), None)
            if fablecut_media and fablecut_media.resolve() != self.exports_dir.resolve():
                dest_video_dir = fablecut_media / video_dir.name
                dest_video_dir.mkdir(parents=True, exist_ok=True)
                for src_file in [final_video_path, final_audio_path, final_cs_path, final_thumb_path, str(json_path), str(srt_path), str(srt_vi_path)]:
                    if src_file and Path(src_file).exists():
                        dest_file = dest_video_dir / Path(src_file).name
                        try:
                            if Path(src_file).resolve() != dest_file.resolve():
                                shutil.copy2(src_file, dest_file)
                        except Exception as sync_err:
                            logger.warning(f"Sync file to fablecut-data/media failed: {sync_err}")

        return ExportResult(
            str(json_path),
            str(srt_path),
            final_audio_path,
            str(srt_vi_path),
            final_cs_path,
            final_thumb_path,
            final_video_path
        )
