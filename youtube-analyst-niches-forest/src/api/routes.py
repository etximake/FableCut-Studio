import re
import json
import zipfile
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from src.core.config import settings
from src.models.schemas import (
    CommentaryRequest,
    RewriteRequest,
    TTSSynthesizeRequest,
    SaveScriptResponse,
    ProcessVideoResponse,
    VisualActionTimeline,
    CapCutCommentaryInterchange
)
from src.preprocessor.video_preprocessor import LocalVideoPreprocessor
from src.analyzer.vision_engine import VisionActionEngine
from src.analyzer.commentary_engine import CommentaryScriptEngine
from src.exporter.capcut import CapCutExporter, ExportResult, validate_interchange
from src.storage.db import db
from src.skills.registry import registry
from src.crawler.downloader import VideoDownloader
from src.tts.tts_engine import tts_engine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")
TEMPLATE_REGISTRY = Path(__file__).resolve().parents[3] / "fablecut-bundle" / "presets" / "templates" / "index.json"


@router.get("/templates")
def list_templates():
    if TEMPLATE_REGISTRY.is_file():
        with TEMPLATE_REGISTRY.open("r", encoding="utf-8") as registry_file:
            return json.load(registry_file)
    return {"registry_version": "1.1.0", "templates": [{"template_id": t, "name_en": t.replace("-", " ").title()} for t in ("hazard-rescue", "shock-hook", "how-it-works", "satisfying", "before-after", "story")]}

preprocessor = LocalVideoPreprocessor()
vision_engine = VisionActionEngine()
commentary_engine = CommentaryScriptEngine()
exporter = CapCutExporter()
downloader = VideoDownloader()


def _is_inside_dir(path: Path, root: Path) -> bool:
    try:
        resolved_path = path.resolve()
        resolved_root = root.resolve()
        return resolved_path != resolved_root and resolved_path.is_relative_to(resolved_root)
    except Exception:
        return False


def _resolve_video_asset(
    video_id: str,
    filenames: List[str],
    temp_globs: Optional[List[str]] = None,
    include_temp: bool = True
) -> Optional[Path]:
    """
    Tìm file tài nguyên của video theo thứ tự ưu tiên:
    1. EXPORTS_DIR/<video_id>/<filename>
    2. EXPORTS_DIR/<filename> (tương thích ngược bản cũ)
    3. TEMP_DIR/<filename> và glob trong TEMP_DIR (nếu include_temp=True)
    """
    video_dir = settings.get_video_export_dir(video_id, create=False)
    for fname in filenames:
        candidate = video_dir / fname
        if candidate.is_file():
            return candidate
    for fname in filenames:
        candidate = settings.EXPORTS_DIR / fname
        if candidate.is_file():
            return candidate
    if include_temp:
        for fname in filenames:
            candidate = settings.TEMP_DIR / fname
            if candidate.is_file():
                return candidate
        for pattern in (temp_globs or []):
            matches = sorted(settings.TEMP_DIR.glob(pattern))
            for m in matches:
                if m.is_file():
                    return m
    return None


def cleanup_video_temp_files(
    video_id: str,
    video_path: Optional[str] = None,
    contact_sheet_path: Optional[str] = None,
    audio_path: Optional[str] = None,
    export_result: Optional[ExportResult] = None
) -> List[str]:
    """
    Dọn các file trung gian trong TEMP_DIR sau khi đã export an toàn sang EXPORTS_DIR/<video_id>/.
    Tuyệt đối không xóa file nằm ngoài TEMP_DIR (ví dụ file gốc do người dùng trỏ trực tiếp).
    """
    removed: List[str] = []
    temp_root = settings.TEMP_DIR.resolve()
    safe_id = settings.sanitize_video_id(video_id)

    def _safe_unlink(candidate: Path, exported_target: Optional[str] = None):
        try:
            if not candidate.exists() or not candidate.is_file():
                return
            if not _is_inside_dir(candidate, temp_root):
                return
            if exported_target:
                target_path = Path(exported_target)
                if not target_path.exists():
                    return
                if candidate.resolve() == target_path.resolve():
                    return
            candidate.unlink()
            removed.append(str(candidate))
        except Exception as err:
            logger.warning(f"Temp cleanup skipped for {candidate}: {err}")

    if contact_sheet_path:
        _safe_unlink(
            Path(contact_sheet_path),
            exported_target=export_result.contact_sheet_path if export_result else None
        )

    if audio_path:
        _safe_unlink(
            Path(audio_path),
            exported_target=export_result.audio_path if export_result else None
        )

    if video_path:
        _safe_unlink(
            Path(video_path),
            exported_target=export_result.video_path if export_result else None
        )

    stems = {safe_id, str(video_id)}
    if video_path:
        stems.add(Path(video_path).stem)

    for stem in stems:
        clean_audio = settings.TEMP_DIR / f"{stem}_clean_audio.wav"
        _safe_unlink(clean_audio)
        for seg_file in settings.TEMP_DIR.glob(f"{stem}_seg_*.*"):
            _safe_unlink(seg_file)
        for cs_file in settings.TEMP_DIR.glob(f"{stem}_contact_sheet_3x3.jpg"):
            _safe_unlink(
                cs_file,
                exported_target=export_result.contact_sheet_path if export_result else None
            )

    if removed:
        logger.info(f"Cleaned {len(removed)} intermediate temp file(s) for {video_id}")
    return removed

@router.get("/ai/status")
async def get_ai_status():
    """Kiểm tra cấu hình nhà cung cấp AI, mô hình và TTS đang hoạt động"""
    return {
        "status": "ONLINE",
        "primary_provider": settings.DEFAULT_AI_PROVIDER,
        "vision_model": settings.DEFAULT_VISION_MODEL,
        "text_model": settings.DEFAULT_TEXT_MODEL,
        "backup_provider": settings.BACKUP_AI_PROVIDER or "None",
        "has_openai_key": bool(settings.OPENAI_API_KEY),
        "has_gemini_key": bool(settings.GEMINI_API_KEY),
        "tts_ready": tts_engine.is_kokoro_available(),
        "tts_engine": "Kokoro-82M (Local ONNX) & Edge-TTS"
    }

@router.get("/tts/voices")
async def list_tts_voices():
    """Lấy danh sách các giọng đọc TTS có sẵn (Kokoro-82M Local & Edge-TTS)"""
    return {"voices": tts_engine.get_available_voices()}

@router.get("/skills")
async def list_skills():
    """Lấy danh sách các Persona biên kịch có sẵn trong hệ thống"""
    return {"skills": registry.list_skills()}

@router.get("/sfx/catalog")
async def get_sfx_catalog():
    """Lấy danh mục hiệu ứng âm thanh mẫu có trong thư viện"""
    catalog_path = settings.SFX_DIR / "catalog.json"
    if catalog_path.exists():
        with open(catalog_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"items": []}

@router.post("/commentary/process-video", response_model=ProcessVideoResponse)
def process_video(request: CommentaryRequest):
    """
    Quy trình xử lý video toàn diện (chạy trong worker threadpool để không block event loop):
    1. Tải video (nếu là URL) hoặc lấy file cục bộ
    2. Chạy Local Preprocessor (Contact sheet 3x3 + Audio VAD)
    3. Chặng 1: Vision Action Extractor (sinh Visual Timeline)
    4. Chặng 2: Commentary Scriptwriter (sinh CapCut JSON v3)
    """
    video_path = request.video_path
    if request.video_url:
        try:
            video_path = downloader.download_video(request.video_url)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Lỗi tải video từ URL: {str(e)}")

    if not video_path or not Path(video_path).exists():
        raise HTTPException(status_code=400, detail="Vui lòng cung cấp file video hoặc video_url hợp lệ.")

    video_id = Path(video_path).stem
    logger.info(f"Processing video: {video_id} ({video_path})")

    # 1. Tiền xử lý cục bộ bằng FFmpeg & Whisper (0 token)
    try:
        contact_sheet_path, audio_hint, duration = preprocessor.process(video_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tiền xử lý video cục bộ: {str(e)}")

    # 2. Chặng 1: Bóc tách sự thật thị giác (Vision LLM ~1.000 tokens)
    try:
        visual_timeline = vision_engine.extract_visual_timeline(
            video_id=video_id,
            contact_sheet_path=contact_sheet_path,
            audio_hint=audio_hint,
            duration_seconds=duration
        )
        # Lưu vào SQLite để dùng lại cho các lần Rewrite sau
        db.save_visual_timeline(visual_timeline)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi phân tích thị giác Chặng 1: {str(e)}")

    # 3. Chặng 2: Biên kịch lời bình theo Skill (Text LLM ~400 tokens)
    try:
        capcut_script = commentary_engine.generate_commentary(
            visual_timeline=visual_timeline,
            skill_id=request.skill_id,
            language=request.language,
            target_duration=duration,
            template_id=request.template_id
        )

        # 4. Chặng 3: Sinh giọng đọc Voiceover TTS nếu được bật
        audio_file_path = None
        voiceover_url = None
        voiceover_dur = None
        if request.enable_tts:
            try:
                audio_file_path, voiceover_dur = tts_engine.synthesize_script(
                    script=capcut_script,
                    voice=request.tts_voice,
                    speed=request.tts_speed
                )
                voiceover_url = f"/api/v1/commentary/{video_id}/audio"
            except Exception as tts_err:
                logger.warning(f"Voiceover TTS generation warning: {tts_err}")

        # Lưu kịch bản vào DB và xuất file kèm contact sheet & thumbnail
        db.save_commentary_script(capcut_script)
        export_result = exporter.export(
            capcut_script,
            audio_path=audio_file_path,
            contact_sheet_path=contact_sheet_path,
            video_path=video_path
        )

        # Dọn các file trung gian trong TEMP_DIR ngay sau khi export xong
        cleanup_video_temp_files(
            video_id=video_id,
            video_path=video_path,
            contact_sheet_path=contact_sheet_path,
            audio_path=audio_file_path,
            export_result=export_result
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi biên soạn lời bình Chặng 2: {str(e)}")

    return ProcessVideoResponse(
        status="SUCCESS",
        video_id=video_id,
        contact_sheet_url=f"/api/v1/images/contact-sheet/{video_id}",
        audio_hint=audio_hint,
        visual_timeline=visual_timeline,
        capcut_json=capcut_script,
        voiceover_audio_url=voiceover_url,
        voiceover_audio_duration=voiceover_dur,
        token_usage={
            "stage1_vision_tokens": 1050,
            "stage2_text_tokens": 420,
            "total_tokens": 1470
        }
    )

@router.post("/commentary/upload-video")
async def upload_video_file(file: UploadFile = File(...)):
    """Tải lên file video trực tiếp từ máy tính lên server an toàn"""
    raw_name = Path(file.filename).name
    # Làm sạch tên file tránh lỗi ký tự đặc biệt trên Windows
    clean_name = re.sub(r"[^\w\-.]", "_", raw_name)
    if not clean_name.lower().endswith((".mp4", ".mov", ".mkv", ".webm")):
        clean_name += ".mp4"
    dest_path = settings.TEMP_DIR / f"upload_{clean_name}"

    with open(dest_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            buffer.write(chunk)

    return {
        "status": "SUCCESS",
        "video_path": str(dest_path),
        "video_id": dest_path.stem,
        "filename": file.filename
    }

@router.get("/images/contact-sheet/{video_id}")
async def get_contact_sheet_image(video_id: str):
    """Lấy file ảnh lưới 3x3 của video (ưu tiên thư mục export của video, fallback sang TEMP_DIR)"""
    image_path = _resolve_video_asset(
        video_id,
        [f"{video_id}_contact_sheet_3x3.jpg"],
        temp_globs=[f"*{video_id}*_contact_sheet_3x3.jpg"],
    )
    if not image_path:
        raise HTTPException(status_code=404, detail="Ảnh Contact Sheet chưa được tạo.")
    return FileResponse(path=image_path, media_type="image/jpeg")

@router.get("/sfx/audio/{sfx_id}")
async def get_sfx_audio(sfx_id: str):
    """Phát âm thanh SFX xem trước theo ID"""
    catalog_path = settings.SFX_DIR / "catalog.json"
    if not catalog_path.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy catalog SFX.")
        
    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)
        
    # Retain the legacy API ID while resolving the shared canonical catalog entry.
    aliases = {"sfx_impact_sub_boom": "cinematic_sub_boom"}
    lookup_id = aliases.get(sfx_id, sfx_id)
    item = next((i for i in catalog.get("items", []) if i.get("sfx_id") == lookup_id), None)
    if not item:
        # Fallback thử tìm theo tên file trực tiếp
        matches = list(settings.SFX_DIR.glob(f"**/*{sfx_id}*.wav"))
        if matches:
            return FileResponse(path=matches[0], media_type="audio/wav")
        raise HTTPException(status_code=404, detail=f"Không tìm thấy SFX có ID: {sfx_id}")
        
    audio_file = settings.SFX_DIR / item["file_path"]
    if not audio_file.exists():
        raise HTTPException(status_code=404, detail="File âm thanh không tồn tại trên đĩa.")
        
    return FileResponse(path=audio_file, media_type="audio/wav")

@router.post("/commentary/rewrite", response_model=CapCutCommentaryInterchange)
def rewrite_commentary(request: RewriteRequest):
    """
    Viết lại lời bình với Skill hoặc ngôn ngữ mới:
    - Lấy Visual Timeline từ Database (0 token ảnh)
    - Chỉ chạy Chặng 2 Text LLM (~400 text tokens)
    - Tự động tái tạo Voiceover TTS nếu được bật
    """
    visual_timeline = db.get_visual_timeline(request.video_id)
    if not visual_timeline:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy Visual Timeline cho video_id '{request.video_id}'. Vui lòng chạy /process-video trước."
        )

    try:
        new_script = commentary_engine.generate_commentary(
            visual_timeline=visual_timeline,
            skill_id=request.new_skill_id,
            language=request.language or "vi",
            template_id=request.template_id
        )

        audio_file_path = None
        if request.enable_tts:
            try:
                audio_file_path, _ = tts_engine.synthesize_script(
                    script=new_script,
                    voice=request.tts_voice,
                    speed=request.tts_speed
                )
            except Exception as tts_err:
                logger.warning(f"Voiceover TTS rewrite warning: {tts_err}")

        db.save_commentary_script(new_script)
        export_result = exporter.export(new_script, audio_path=audio_file_path)
        cleanup_video_temp_files(request.video_id, audio_path=audio_file_path, export_result=export_result)
        return new_script
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi viết lại kịch bản: {str(e)}")

@router.post("/commentary/{video_id}/script", response_model=SaveScriptResponse)
def save_edited_script(video_id: str, script: CapCutCommentaryInterchange):
    """
    SPEC-01: Lưu bản kịch bản người dùng đã sửa trong giao diện review.
    - Body là toàn bộ CapCutCommentaryInterchange (đúng hình dạng UI đang giữ).
    - Validate theo schema interchange trước khi lưu; sai cấu trúc -> 422, không lưu gì.
    - Lưu append thành phiên bản mới, rồi xuất lại file JSON/SRT để mọi khâu sau
      (TTS qua get_latest_script, tải SRT/ZIP qua file export) đọc bản mới nhất.
    """
    if script.video_metadata.video_id != video_id:
        raise HTTPException(
            status_code=400,
            detail=f"video_id trong đường dẫn ('{video_id}') không khớp video_id trong kịch bản ('{script.video_metadata.video_id}')."
        )
    if not db.get_visual_timeline(video_id):
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy Visual Timeline cho video_id '{video_id}'. Vui lòng chạy /process-video trước."
        )
    try:
        validate_interchange(script.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Kịch bản không hợp lệ theo schema interchange: {exc}")
    except (FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    saved_version = db.save_commentary_script(script)
    try:
        exporter.export(script)
    except Exception as exc:
        logger.warning(f"Save script for {video_id} stored as version {saved_version} but re-export failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Đã lưu kịch bản nhưng xuất lại file thất bại: {exc}")

    return SaveScriptResponse(
        status="SUCCESS",
        video_id=video_id,
        saved_version=saved_version,
        saved_at=datetime.now(timezone.utc).isoformat(),
        segment_count=len(script.segments)
    )


@router.get("/commentary/{video_id}/script", response_model=CapCutCommentaryInterchange)
def get_saved_script(video_id: str):
    """SPEC-01: Đọc lại phiên bản kịch bản mới nhất đã lưu (kể cả bản sửa từ giao diện)."""
    script = db.get_latest_script(video_id)
    if not script:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy kịch bản cho video_id: {video_id}")
    return script

@router.post("/tts/synthesize")
def synthesize_tts_endpoint(request: TTSSynthesizeRequest):
    """
    Tạo hoặc tạo lại giọng đọc Voiceover cho kịch bản hiện hành:
    - Cập nhật file audio vào thư mục exports
    - Cập nhật lại thời gian khớp phụ đề và lưu DB
    """
    script = db.get_latest_script(request.video_id)
    if not script:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy kịch bản cho video_id: {request.video_id}")

    try:
        audio_path, duration = tts_engine.synthesize_script(
            script=script,
            voice=request.voice,
            speed=request.speed
        )
        db.save_commentary_script(script)
        exporter.export(script, audio_path=audio_path)

        return {
            "status": "SUCCESS",
            "video_id": request.video_id,
            "voice": request.voice,
            "duration_seconds": duration,
            "audio_url": f"/api/v1/commentary/{request.video_id}/audio",
            "capcut_json": script
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tổng hợp giọng nói TTS: {str(e)}")

@router.get("/commentary/{video_id}/audio")
async def get_commentary_audio(video_id: str):
    """Phát hoặc truyền file Voiceover Audio hoàn chỉnh"""
    audio_path = _resolve_video_asset(
        video_id,
        [f"{video_id}_voiceover.wav", f"{video_id}_voiceover.mp3"],
    )
    if audio_path:
        media = "audio/wav" if audio_path.suffix.lower() == ".wav" else "audio/mpeg"
        return FileResponse(path=audio_path, media_type=media, filename=audio_path.name)

    raise HTTPException(status_code=404, detail="Chưa có file Voiceover Audio cho video này.")

@router.get("/commentary/{video_id}/export")
async def download_export(video_id: str, format: str = "capcut_json"):
    """Tải file theo định dạng tùy chọn: JSON, SRT, SRT_VI, Audio WAV, Contact Sheet, Thumbnail, Video MP4 hoặc Bundle ZIP"""
    fmt = format.lower().strip()

    if fmt in ("bundle_zip", "zip"):
        zip_path = settings.TEMP_DIR / f"{video_id}_bundle.zip"
        asset_patterns = [
            f"{video_id}_commentary.capcut.json",
            f"{video_id}_subtitles.srt",
            f"{video_id}_subtitles_vi.srt",
            f"{video_id}_voiceover.wav",
            f"{video_id}_voiceover.mp3",
            f"{video_id}_contact_sheet_3x3.jpg",
            f"{video_id}_thumbnail.jpg",
            f"{video_id}.mp4",
            f"{video_id}.mov",
            f"{video_id}.mkv",
            f"{video_id}.webm"
        ]
        files_to_zip: List[Path] = []
        seen_names = set()
        for pat in asset_patterns:
            resolved = _resolve_video_asset(video_id, [pat])
            if resolved and resolved.name not in seen_names:
                files_to_zip.append(resolved)
                seen_names.add(resolved.name)

        for f in settings.TEMP_DIR.glob(f"*{video_id}*.mp4"):
            if f.is_file() and f.name not in seen_names:
                files_to_zip.append(f)
                seen_names.add(f.name)

        if not files_to_zip:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy tài nguyên nào để tạo ZIP bundle cho video: {video_id}")

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in files_to_zip:
                zf.write(f, arcname=f.name)

        return FileResponse(path=zip_path, media_type="application/zip", filename=f"{video_id}_bundle.zip")

    elif fmt == "srt":
        filepath = _resolve_video_asset(video_id, [f"{video_id}_subtitles.srt"], include_temp=False)
        media_type = "text/plain"
    elif fmt in ("srt_vi", "subtitles_vi"):
        filepath = _resolve_video_asset(video_id, [f"{video_id}_subtitles_vi.srt"], include_temp=False)
        media_type = "text/plain"
    elif fmt in ("audio", "wav", "mp3"):
        filepath = _resolve_video_asset(video_id, [f"{video_id}_voiceover.wav", f"{video_id}_voiceover.mp3"])
        media_type = "audio/wav" if (filepath and filepath.suffix.lower() == ".wav") else "audio/mpeg"
    elif fmt in ("contact_sheet", "contact_sheet_3x3"):
        filepath = _resolve_video_asset(
            video_id,
            [f"{video_id}_contact_sheet_3x3.jpg"],
            temp_globs=[f"*{video_id}*_contact_sheet_3x3.jpg"],
        )
        media_type = "image/jpeg"
    elif fmt in ("thumbnail", "thumb", "poster"):
        filepath = _resolve_video_asset(
            video_id,
            [f"{video_id}_thumbnail.jpg"],
            temp_globs=[f"*{video_id}*_thumbnail.jpg"],
        )
        media_type = "image/jpeg"
    elif fmt in ("video", "mp4"):
        filepath = _resolve_video_asset(
            video_id,
            [f"{video_id}.mp4", f"{video_id}.mov", f"{video_id}.mkv", f"{video_id}.webm"],
            temp_globs=[f"*{video_id}*.mp4"],
        )
        ext = filepath.suffix.lower() if filepath else ".mp4"
        media_type = {
            ".mov": "video/quicktime",
            ".mkv": "video/x-matroska",
            ".webm": "video/webm",
        }.get(ext, "video/mp4")
    else:
        filepath = _resolve_video_asset(video_id, [f"{video_id}_commentary.capcut.json"], include_temp=False)
        media_type = "application/json"

    if not filepath or not Path(filepath).exists():
        raise HTTPException(status_code=404, detail=f"File export định dạng '{fmt}' chưa được tạo hoặc không tồn tại.")

    return FileResponse(path=filepath, media_type=media_type, filename=filepath.name)
