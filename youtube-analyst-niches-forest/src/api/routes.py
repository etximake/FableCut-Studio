import re
import json
import shutil
import zipfile
import logging
import base64
import struct
import time
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from src.core.config import settings
from src.models.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    CommentaryRequest,
    RewriteRequest,
    TTSSynthesizeRequest,
    SaveScriptResponse,
    ProcessVideoResponse,
    VisualActionTimeline,
    CapCutCommentaryInterchange,
    GenerateCommentaryRequest,
    SceneRange,
    CommentaryGenerationResponse,
    ExportRequest,
    VisualTimelineUpdate,
    PartialRewriteRequest,
    PartialRewriteResponse,
    RewriteResponse,
)
from src.preprocessor.video_preprocessor import LocalVideoPreprocessor
from src.analyzer.vision_engine import VisionActionEngine
from src.analyzer.commentary_engine import CommentaryScriptEngine, TEMPLATE_VOICE_DEFAULTS
from src.analyzer.scene_selector import (
    covers_full_video,
    describe_scenes,
    needs_scene_selection,
    propose_scenes,
    rebase_timeline,
    total_seconds,
    validate_scenes,
)
from src.exporter.capcut import CapCutExporter, ExportResult, validate_interchange
from src.storage.db import db
from src.skills.registry import registry
from src.crawler.downloader import VideoDownloader
from src.tts.tts_engine import tts_engine
from openai import OpenAI

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")
TEMPLATE_REGISTRY = Path(__file__).resolve().parents[3] / "fablecut-bundle" / "presets" / "templates" / "index.json"


@router.get("/templates")
def list_templates():
    if TEMPLATE_REGISTRY.is_file():
        with TEMPLATE_REGISTRY.open("r", encoding="utf-8") as registry_file:
            registry_data = json.load(registry_file)
    else:
        registry_data = {"registry_version": "1.1.0", "templates": [{"template_id": t, "name_en": t.replace("-", " ").title()} for t in ("hazard-rescue", "shock-hook", "how-it-works", "satisfying", "before-after", "story")]}
    # Enrich each entry with the narrator default + target feeling from the
    # single source of truth (TEMPLATE_VOICE_DEFAULTS), so template cards in
    # the UI show the feeling each template is designed to create.
    for entry in registry_data.get("templates", []):
        default_mode, feeling, _rule = TEMPLATE_VOICE_DEFAULTS.get(
            entry.get("template_id"), ("third_person", "understanding", "")
        )
        entry["narrator_mode"] = default_mode
        entry["target_feeling"] = feeling
    return registry_data

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


def _build_scene_note(original_duration: float, scenes: List[SceneRange]) -> str:
    if not scenes or covers_full_video(scenes, original_duration):
        return ""
    return (
        f"Video gốc {original_duration:.1f}s; đã chọn các cảnh {describe_scenes(scenes)} "
        f"(tổng {total_seconds(scenes):.1f}s) ghép thành 1 clip liên tục."
    )


def _resolve_source_video(video_id: str, stored_path: Optional[str]) -> Optional[Path]:
    """Tìm video GỐC để ghép cảnh. Không bao giờ dùng file export <video_id>.mp4
    vì sau lần xuất có chọn cảnh, file đó đã là clip ghép (ghép lại từ nó sẽ
    sai mốc giây). Thứ tự: đường dẫn đã lưu -> bản gốc đã giữ -> file trong TEMP_DIR."""
    if stored_path:
        candidate = Path(stored_path)
        if candidate.is_file():
            return candidate
    video_dir = settings.get_video_export_dir(video_id, create=False)
    for ext in (".mp4", ".mov", ".mkv", ".webm"):
        candidate = video_dir / f"{video_id}_original{ext}"
        if candidate.is_file():
            return candidate
    for ext in (".mp4", ".mov", ".mkv", ".webm"):
        candidate = settings.TEMP_DIR / f"{video_id}{ext}"
        if candidate.is_file():
            return candidate
    return None


def _preserve_original_video(video_id: str, source_path: str) -> None:
    """Giữ 1 bản sao video gốc cạnh file export, để lần sau đổi cảnh vẫn ghép
    lại được từ gốc. Best-effort: lỗi thì chỉ ghi log, không chặn xuất file."""
    try:
        source = Path(source_path)
        if not source.is_file():
            return
        video_dir = settings.get_video_export_dir(video_id)
        target = video_dir / f"{video_id}_original{source.suffix or '.mp4'}"
        if target.exists() or source.resolve() == target.resolve():
            return
        shutil.copy2(source, target)
    except Exception as err:
        logger.warning(f"Preserve original video failed for {video_id}: {err}")


def _apply_scene_selection(
    video_id: str,
    full_timeline: VisualActionTimeline,
    scenes: List[SceneRange],
    max_seconds: float,
    source_path: Optional[str],
    build_media: bool,
):
    """Áp dụng cảnh đã chốt: kiểm tra, dồn timeline, (tùy chọn) ghép clip.

    Trả về (active_timeline, trimmed_path_or_None, scenes_applied, scene_note).
    Cảnh bao toàn bộ video thì không ghép gì cả. Lỗi kiểm tra -> HTTP 400.
    """
    errors = validate_scenes(scenes, full_timeline.duration_seconds, max_seconds)
    if errors:
        raise HTTPException(status_code=400, detail="Lựa chọn cảnh không hợp lệ: " + " ".join(errors))
    existing = db.get_scene_selection(video_id)
    stored_source = source_path or (existing or {}).get("source_video_path")
    if covers_full_video(scenes, full_timeline.duration_seconds):
        db.save_scene_selection(
            video_id, [scene.model_dump() for scene in scenes],
            total_seconds(scenes), source_video_path=stored_source,
        )
        return full_timeline, None, scenes, ""
    active_timeline = rebase_timeline(full_timeline, scenes)
    scene_note = _build_scene_note(full_timeline.duration_seconds, scenes)
    trimmed_path = None
    if build_media:
        source = _resolve_source_video(video_id, stored_source)
        if source is None:
            raise HTTPException(
                status_code=400,
                detail="Không tìm thấy video gốc để ghép cảnh. Vui lòng tải lại video và phân tích lại.",
            )
        safe_id = settings.sanitize_video_id(video_id)
        trimmed_path = preprocessor.concat_scenes(
            str(source),
            [(scene.start, scene.end) for scene in scenes],
            output_path=str(settings.TEMP_DIR / f"{safe_id}_scenes.mp4"),
        )
        stored_source = str(source)
    db.save_scene_selection(
        video_id, [scene.model_dump() for scene in scenes],
        total_seconds(scenes), source_video_path=stored_source,
        trimmed_video_path=trimmed_path,
    )
    return active_timeline, trimmed_path, scenes, scene_note


def _get_active_timeline(video_id: str):
    """Trả về (full_timeline, active_timeline, scenes_applied).

    Active timeline là timeline đã dồn theo cảnh đã lưu (nếu có); nếu chưa
    từng chọn cảnh thì active = full. Chỉ tính toán, không ghép media.
    """
    full_timeline = db.get_visual_timeline(video_id)
    if not full_timeline:
        return None, None, []
    stored = db.get_scene_selection(video_id)
    if not stored:
        return full_timeline, full_timeline, []
    try:
        scenes = [SceneRange(**scene) for scene in stored["scenes"]]
    except Exception:
        return full_timeline, full_timeline, []
    if covers_full_video(scenes, full_timeline.duration_seconds):
        return full_timeline, full_timeline, scenes
    if validate_scenes(scenes, full_timeline.duration_seconds, float("inf")):
        return full_timeline, full_timeline, []
    return full_timeline, rebase_timeline(full_timeline, scenes), scenes


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


def _test_ai_model(model_type: str):
    """Gửi một request tối thiểu đến model đã cấu hình, không dùng dữ liệu người dùng."""
    is_vision = model_type == "vision"
    model = settings.DEFAULT_VISION_MODEL if is_vision else settings.DEFAULT_TEXT_MODEL
    api_key = settings.OPENAI_API_KEY
    base_url = settings.OPENAI_BASE_URL
    if not api_key:
        return {"ok": False, "model_type": model_type, "model": model,
                "message": "Chưa cấu hình OPENAI_API_KEY.", "elapsed_ms": None}

    started = time.perf_counter()
    try:
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=20.0)
        content = "Reply with a JSON object containing {\"ok\": true}."
        if is_vision:
            # Small valid 32x32 PNG test card; no user image or imaging dependency.
            def png_chunk(kind: bytes, data: bytes) -> bytes:
                body = kind + data
                return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

            width = height = 32
            scanline = b"\x00" + bytes((96, 152, 208)) * width
            image_data = zlib.compress(scanline * height)
            pixel = (
                b"\x89PNG\r\n\x1a\n"
                + png_chunk(b"IHDR", struct.pack(">2I5B", width, height, 8, 2, 0, 0, 0))
                + png_chunk(b"IDAT", image_data)
                + png_chunk(b"IEND", b"")
            )
            content = [
                {"type": "text", "text": "Describe the color in this image in one short phrase."},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(pixel).decode("ascii"), "detail": "low"}},
            ]
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content}],
            response_format={"type": "json_object"} if not is_vision else None,
            max_tokens=80,
            temperature=0,
        )
        if not response.choices or not response.choices[0].message.content:
            raise ValueError("empty model response")
        return {"ok": True, "model_type": model_type, "model": model,
                "message": "Model phản hồi thành công.",
                "elapsed_ms": round((time.perf_counter() - started) * 1000)}
    except Exception as exc:
        logger.warning("AI %s model test failed (%s)", model_type, type(exc).__name__)
        return {"ok": False, "model_type": model_type, "model": model,
                "message": "Không gọi được model. Kiểm tra API key, base URL, tên model và kết nối.",
                "elapsed_ms": round((time.perf_counter() - started) * 1000)}


@router.post("/ai/test/{model_type}")
def test_ai_model(model_type: str):
    if model_type not in ("text", "vision"):
        raise HTTPException(status_code=404, detail="Loại model không hợp lệ. Dùng text hoặc vision.")
    return _test_ai_model(model_type)

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

@router.post("/commentary/analyze", response_model=AnalyzeResponse)
def analyze_video(request: AnalyzeRequest):
    """Bước 1 của luồng 2 bước (Batch 2): tiền xử lý + Vision mù + gợi ý template.

    Không sinh kịch bản, không TTS, không export. Người dùng xem timeline và
    chốt template ở bước 2 rồi mới gọi /commentary/generate-script.
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
    logger.info(f"Analyzing video: {video_id} ({video_path})")

    try:
        contact_sheet_path, audio_hint, duration = preprocessor.process(video_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tiền xử lý video cục bộ: {str(e)}")

    try:
        visual_timeline = vision_engine.extract_visual_timeline(
            video_id=video_id,
            contact_sheet_path=contact_sheet_path,
            audio_hint=audio_hint,
            duration_seconds=duration,
        )
        db.save_visual_timeline(visual_timeline)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi phân tích thị giác Chặng 1: {str(e)}")

    recommendation = commentary_engine.recommend_template(visual_timeline)
    narrator_mode, target_feeling, _feeling_rule = commentary_engine.resolve_narrator_and_feeling(
        recommendation.template_id
    )
    visual_timeline.selected_template_id = recommendation.template_id
    visual_timeline.template_recommendation_reason = recommendation.reason
    visual_timeline.template_selection_source = recommendation.source
    db.save_visual_timeline(visual_timeline)
    # Gợi ý cảnh cho video dài: người dùng duyệt/sửa ở bước 2. Lưu kèm đường
    # dẫn video gốc để bước viết kịch bản ghép clip được.
    max_seconds = settings.MAX_SHORT_SECONDS
    scene_proposal = propose_scenes(visual_timeline, recommendation.template_id, max_seconds)
    needs_selection = needs_scene_selection(visual_timeline.duration_seconds, max_seconds)
    try:
        db.save_scene_selection(
            video_id, [scene.model_dump() for scene in scene_proposal],
            total_seconds(scene_proposal), source_video_path=str(video_path),
        )
    except Exception as err:
        logger.warning(f"Scene proposal not saved for {video_id}: {err}")
    return AnalyzeResponse(
        video_id=video_id,
        contact_sheet_url=f"/api/v1/images/contact-sheet/{video_id}",
        audio_hint=audio_hint,
        visual_timeline=visual_timeline,
        template_recommendation=recommendation,
        narrator_mode=narrator_mode,
        target_feeling=target_feeling,
        scene_proposal=scene_proposal,
        max_scene_seconds=max_seconds,
        needs_scene_selection=needs_selection,
    )


@router.post("/commentary/process-video", response_model=ProcessVideoResponse, deprecated=True)
def process_video(request: CommentaryRequest):
    """
    DEPRECATED (Batch 2): luồng 1 nút chạy hết (phân tích + kịch bản + TTS + export).
    Giao diện mới dùng 2 bước: POST /commentary/analyze rồi POST /commentary/generate-script.
    Endpoint này giữ lại để tương thích API cũ, không thêm tính năng mới.
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
    # Vision chạy mù: không nhận nhãn hay mô tả của người dùng.
    try:
        visual_timeline = vision_engine.extract_visual_timeline(
            video_id=video_id,
            contact_sheet_path=contact_sheet_path,
            audio_hint=audio_hint,
            duration_seconds=duration,
        )
        # Lưu vào SQLite để dùng lại cho các lần Rewrite sau
        db.save_visual_timeline(visual_timeline)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi phân tích thị giác Chặng 1: {str(e)}")

    # 3. Chặng 2: Biên kịch lời bình theo Skill (Text LLM ~400 tokens)
    # Video dài: tự áp dụng gợi ý cảnh (luồng cũ không có bước duyệt của
    # người dùng), để kịch bản và file xuất ra không vượt giới hạn Short.
    active_timeline = visual_timeline
    trimmed_path = None
    scenes_applied: List[SceneRange] = []
    scene_note = ""
    try:
        max_seconds = settings.MAX_SHORT_SECONDS
        scene_proposal = propose_scenes(visual_timeline, request.template_id, max_seconds)
        active_timeline, trimmed_path, scenes_applied, scene_note = _apply_scene_selection(
            video_id, visual_timeline, scene_proposal, max_seconds,
            source_path=str(video_path), build_media=True,
        )
        capcut_script = commentary_engine.generate_commentary(
            visual_timeline=active_timeline,
            skill_id=request.skill_id,
            language=request.language,
            target_duration=active_timeline.duration_seconds,
            template_id=request.template_id,
            description_subject=request.description_subject,
            description_activity=request.description_activity,
            description_focus=request.description_focus,
            narrator_mode=request.narrator_mode,
            scene_note=scene_note or None,
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

        # Lưu kịch bản vào DB và xuất file kèm contact sheet & thumbnail.
        # Khi có chọn cảnh, file video xuất ra phải là clip đã ghép để khớp
        # mốc giây trong JSON; bản gốc được giữ riêng trước khi dọn temp.
        db.save_commentary_script(capcut_script)
        export_result = exporter.export(
            capcut_script,
            audio_path=audio_file_path,
            contact_sheet_path=contact_sheet_path,
            video_path=trimmed_path or video_path
        )
        if trimmed_path:
            _preserve_original_video(video_id, video_path)

        # Dọn các file trung gian trong TEMP_DIR ngay sau khi export xong
        cleanup_video_temp_files(
            video_id=video_id,
            video_path=video_path,
            contact_sheet_path=contact_sheet_path,
            audio_path=audio_file_path,
            export_result=export_result
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi biên soạn lời bình Chặng 2: {str(e)}")

    template_recommendation = commentary_engine.recommend_template(
        visual_timeline, request.template_id
    )
    narrator_mode, target_feeling, _feeling_rule = commentary_engine.resolve_narrator_and_feeling(
        template_recommendation.template_id, request.narrator_mode
    )
    visual_timeline.selected_template_id = template_recommendation.template_id
    visual_timeline.template_recommendation_reason = template_recommendation.reason
    visual_timeline.template_selection_source = template_recommendation.source
    db.save_visual_timeline(visual_timeline)
    script_review_notes = commentary_engine.validate_generated_script(capcut_script)
    scene_review_notes = [scene_note] if scene_note else []
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
        },
        template_recommendation=template_recommendation,
        review_notes=scene_review_notes + script_review_notes + [
            f"Template: {template_recommendation.template_id} ({template_recommendation.source}). {template_recommendation.reason}",
            f"Ngôi kể: {narrator_mode}; cảm giác mục tiêu: {target_feeling}.",
            "Các phát biểu kỹ thuật hoặc nguyên nhân không thể xác nhận từ hình/âm thanh cần được người dùng kiểm tra.",
        ],
        story_angle=commentary_engine.derive_story_angle(active_timeline),
        narrator_mode=narrator_mode,
        target_feeling=target_feeling,
        scenes_applied=scenes_applied,
        qa_metadata={
            "template_id": template_recommendation.template_id,
            "template_source": template_recommendation.source,
            "template_version": "1.1.0",
            "narrator_mode": narrator_mode,
            "target_feeling": target_feeling,
            "prompt_version": "simplified-batch1-v1",
            "model": settings.DEFAULT_TEXT_MODEL,
            "warnings_count": len(script_review_notes),
            "scenes_applied": [scene.model_dump() for scene in scenes_applied],
            "original_duration_seconds": visual_timeline.duration_seconds,
        },
    )


@router.post("/commentary/generate-script", response_model=CommentaryGenerationResponse)
def generate_script_from_saved_analysis(request: GenerateCommentaryRequest):
    """Generate/re-generate script from a saved visual timeline without re-running Vision.

    Cảnh đã chốt (request.scenes, hoặc lựa chọn đã lưu) được áp dụng trước khi
    viết kịch bản: timeline dồn về clip ghép, và khi content_only=False thì
    clip ghép được tạo và xuất làm file video đi kèm JSON.
    """
    full_timeline = db.get_visual_timeline(request.video_id)
    if not full_timeline:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy phân tích cho video {request.video_id}.")
    recommendation = commentary_engine.recommend_template(
        full_timeline, request.template_id
    )
    narrator_mode, target_feeling, _feeling_rule = commentary_engine.resolve_narrator_and_feeling(
        recommendation.template_id, request.narrator_mode
    )
    full_timeline.selected_template_id = recommendation.template_id
    full_timeline.template_recommendation_reason = recommendation.reason
    full_timeline.template_selection_source = recommendation.source
    db.save_visual_timeline(full_timeline)

    max_seconds = request.max_seconds or settings.MAX_SHORT_SECONDS
    stored = db.get_scene_selection(request.video_id)
    scenes = request.scenes
    if scenes is None and stored:
        try:
            scenes = [SceneRange(**scene) for scene in stored["scenes"]]
        except Exception:
            scenes = None
    source_path = stored["source_video_path"] if stored else None
    try:
        if scenes is not None:
            active_timeline, trimmed_path, scenes_applied, scene_note = _apply_scene_selection(
                request.video_id, full_timeline, scenes, max_seconds, source_path,
                build_media=not request.content_only,
            )
        else:
            active_timeline, trimmed_path, scenes_applied, scene_note = full_timeline, None, [], ""
        script = commentary_engine.generate_commentary(
            visual_timeline=active_timeline,
            skill_id=request.skill_id,
            language=request.language,
            target_duration=active_timeline.duration_seconds,
            template_id=recommendation.template_id,
            description_subject=request.description_subject,
            description_activity=request.description_activity,
            description_focus=request.description_focus,
            narrator_mode=request.narrator_mode,
            scene_note=scene_note or None,
        )
        notes = commentary_engine.validate_generated_script(script)
        qa_metadata = {"template_id": recommendation.template_id, "template_source": recommendation.source, "template_version": "1.1.0", "narrator_mode": narrator_mode, "target_feeling": target_feeling, "prompt_version": "simplified-batch1-v1", "model": settings.DEFAULT_TEXT_MODEL, "warnings_count": len(notes), "scenes_applied": [scene.model_dump() for scene in scenes_applied], "original_duration_seconds": full_timeline.duration_seconds}
        if request.content_only:
            return CommentaryGenerationResponse(
                video_id=request.video_id,
                capcut_json=script,
                template_recommendation=recommendation,
                review_notes=notes,
                source=recommendation.source,
                story_angle=commentary_engine.derive_story_angle(active_timeline),
                narrator_mode=narrator_mode,
                target_feeling=target_feeling,
                qa_metadata=qa_metadata,
                scenes_applied=scenes_applied,
                original_duration_seconds=full_timeline.duration_seconds,
            )
        if request.enable_tts:
            tts_engine.synthesize_script(script=script, voice=request.tts_voice, speed=request.tts_speed)
        db.save_commentary_script(script)
        try:
            exporter.export(script, video_path=trimmed_path)
        except Exception as export_exc:
            logger.warning("Generated script saved but export failed for %s: %s", request.video_id, export_exc)
        if trimmed_path:
            refreshed = db.get_scene_selection(request.video_id)
            if refreshed and refreshed.get("source_video_path"):
                _preserve_original_video(request.video_id, refreshed["source_video_path"])
        return CommentaryGenerationResponse(
            video_id=request.video_id, capcut_json=script,
            template_recommendation=recommendation, review_notes=notes,
            source=recommendation.source,
            story_angle=commentary_engine.derive_story_angle(active_timeline),
            narrator_mode=narrator_mode,
            target_feeling=target_feeling,
            qa_metadata=qa_metadata,
            scenes_applied=scenes_applied,
            original_duration_seconds=full_timeline.duration_seconds,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Không thể tạo lời bình: {exc}")


@router.post("/commentary/rewrite-segment", response_model=PartialRewriteResponse)
def rewrite_one_segment(request: PartialRewriteRequest):
    script = db.get_latest_script(request.video_id)
    if not script:
        raise HTTPException(status_code=404, detail="Chưa có kịch bản đã lưu.")
    if request.segment_index >= len(script.segments):
        raise HTTPException(status_code=422, detail="segment_index nằm ngoài phạm vi kịch bản.")
    original = script.segments[request.segment_index]
    _full_timeline, timeline, _scenes = _get_active_timeline(request.video_id)
    evidence = timeline.action_timeline[request.segment_index] if timeline and request.segment_index < len(timeline.action_timeline) else None
    skill = registry.get(request.skill_id)
    prompt = (
        "Rewrite only this one narration segment. Return JSON with voiceover and voiceover_vi_translation. "
        "Do not add facts beyond the evidence. Keep the same beat and timing.\n"
        f"Beat: {original.beat}\nCurrent narration: {request.current_voiceover or original.voiceover}\n"
        f"Evidence: {evidence.model_dump_json() if evidence else 'unknown'}\n"
        f"User instruction: {request.instruction or 'Improve clarity and specificity.'}\nLanguage: {request.language}"
    )
    previous_script_json = script.model_dump_json()
    try:
        result = commentary_engine._call_text_llm(
            settings.OPENAI_API_KEY, settings.OPENAI_BASE_URL, settings.DEFAULT_TEXT_MODEL,
            skill.get_system_instructions(request.language), prompt,
        )
        original.voiceover = str(result.get("voiceover", original.voiceover))
        original.voiceover_vi_translation = str(result.get("voiceover_vi_translation", original.voiceover_vi_translation or ""))
        review_notes = commentary_engine.validate_generated_script(script)
        db.save_commentary_script(script)
        return PartialRewriteResponse(
            video_id=request.video_id,
            segment_index=request.segment_index,
            segment=original,
            review_note=" ".join(review_notes) if review_notes else "Đối chiếu nội dung mới với bằng chứng trước khi duyệt.",
        )
    except Exception as exc:
        script = CapCutCommentaryInterchange.model_validate_json(previous_script_json)
        raise HTTPException(status_code=500, detail=f"Không thể viết lại beat: {exc}")


@router.patch("/commentary/{video_id}/analysis")
def update_visual_analysis(video_id: str, request: VisualTimelineUpdate):
    """Apply user-reviewed event corrections to a saved analysis."""
    timeline = db.get_visual_timeline(video_id)
    if not timeline:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy phân tích cho video {video_id}.")
    for raw_index, changes in request.events.items():
        try:
            index = int(raw_index)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Chỉ số sự kiện không hợp lệ: {raw_index}.")
        if index < 0 or index >= len(timeline.action_timeline):
            raise HTTPException(status_code=422, detail=f"Chỉ số sự kiện không hợp lệ: {index}.")
        event = timeline.action_timeline[index]
        for field, value in changes.model_dump(exclude_unset=True).items():
            setattr(event, field, value)
    db.save_visual_timeline(timeline)
    return {"status": "SUCCESS", "video_id": video_id, "event_count": len(timeline.action_timeline)}

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

@router.post("/commentary/rewrite", response_model=RewriteResponse)
def rewrite_commentary(request: RewriteRequest):
    """
    Viết lại lời bình với Skill hoặc ngôn ngữ mới:
    - Lấy Visual Timeline từ Database (0 token ảnh)
    - Chỉ chạy Chặng 2 Text LLM (~400 text tokens)
    - Tự động tái tạo Voiceover TTS nếu được bật
    """
    visual_timeline, active_timeline, scenes_applied = _get_active_timeline(request.video_id)
    if not visual_timeline:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy Visual Timeline cho video_id '{request.video_id}'. Vui lòng chạy /process-video trước."
        )

    try:
        new_script = commentary_engine.generate_commentary(
            visual_timeline=active_timeline,
            skill_id=request.new_skill_id,
            language=request.language or "vi",
            template_id=request.template_id,
            description_subject=request.description_subject,
            description_activity=request.description_activity,
            description_focus=request.description_focus,
            narrator_mode=request.narrator_mode,
            scene_note=_build_scene_note(visual_timeline.duration_seconds, scenes_applied) or None,
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
        review_notes = commentary_engine.validate_generated_script(new_script)
        scene_note = _build_scene_note(visual_timeline.duration_seconds, scenes_applied)
        if scene_note:
            review_notes = [scene_note] + review_notes
        return RewriteResponse(video_id=request.video_id, capcut_json=new_script, review_notes=review_notes)
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
        # Preserve the approved script/timing if TTS/export fails; never let audio timing overwrite the draft.
        db.save_commentary_script(script)
        try:
            exporter.export(script, audio_path=audio_path)
        except Exception as export_exc:
            logger.warning("TTS generated but export failed for %s: %s", request.video_id, export_exc)

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

@router.post("/commentary/export")
async def export_by_request(request: ExportRequest):
    return await download_export(request.video_id, request.format)


@router.get("/commentary/{video_id}/export")
async def download_export(video_id: str, format: str = "capcut_json"):
    """Tải file theo định dạng tùy chọn: JSON, SRT, SRT_VI, Audio WAV, Contact Sheet, Thumbnail, Video MP4 hoặc Bundle ZIP"""
    fmt = format.lower().strip()
    try:
        video_id = ExportRequest(video_id=video_id, format=fmt).video_id
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"video_id không hợp lệ: {exc}")

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
