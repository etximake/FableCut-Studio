from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator

# ==========================================
# 1. TIỀN XỬ LÝ ÂM THANH & CẢNH BÁO CÂU CỤT
# ==========================================

class AudioHint(BaseModel):
    """Thông tin bóc tách âm thanh và đánh giá độ tin cậy"""
    has_speech: bool = Field(default=False, description="Có phát hiện giọng nói người không")
    status: Literal["COMPLETE", "TRUNCATED_START", "TRUNCATED_END", "TRUNCATED_BOTH", "NO_MEANINGFUL_SPEECH"] = Field(
        default="NO_MEANINGFUL_SPEECH",
        description="Trạng thái câu thoại gốc"
    )
    clean_text: str = Field(default="", description="Nội dung lời thoại gốc đã lọc nhiễu")
    duration_seconds: float = Field(default=0.0, description="Thời lượng thực tế của file âm thanh")
    is_reliable: bool = Field(default=True, description="Đoạn thoại có đủ hoàn chỉnh để tin cậy không")
    guidance: str = Field(default="", description="Chỉ dẫn xử lý dành cho Vision AI")

# ==========================================
# 2. CHẶNG 1: BÓC TÁCH DIỄN BIẾN THỊ GIÁC (VISION TIMELINE)
# ==========================================

class TimeRange(BaseModel):
    start: float = Field(..., ge=0.0, description="Giây bắt đầu")
    end: float = Field(..., ge=0.0, description="Giây kết thúc")

class ActionBlock(BaseModel):
    time_range: TimeRange
    visual_action: str = Field(..., description="Mô tả hành động thực tế diễn ra trên màn hình")
    observable_changes: str = Field(default="", description="Biến đổi vật lý/thị giác quan sát được")
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)

class VisualActionTimeline(BaseModel):
    """Bản tường thuật sự thật khách quan của video theo mốc giây thực"""
    video_id: str
    duration_seconds: float
    subject_matter: str = Field(..., description="Chủ thể hoặc trọng tâm video")
    initial_state: str = Field(default="", description="Trạng thái bối cảnh ban đầu (0s - 5s)")
    action_timeline: List[ActionBlock] = Field(default_factory=list, description="Chuỗi hành động theo mốc giây")
    final_outcome: str = Field(..., description="Kết quả hoặc trạng thái cuối cùng của chủ thể")
    recommended_skill: Optional[str] = Field(default="curiosity-explainer", description="Skill phù hợp nhất do AI đề xuất")

# ==========================================
# 3. CHẶNG 2: KỊCH BẢN LỜI BÌNH & CAPCUT INTERCHANGE V3
# ==========================================

class TextOverlay(BaseModel):
    text: str = Field(..., description="Dòng chữ nổi 3-6 từ nổi bật trên màn hình")
    position: str = Field(default="TOP_CENTER", description="Vị trí hiển thị chữ")
    style: str = Field(default="HIGHLIGHT_YELLOW", description="Kiểu chữ")

    @field_validator("position", mode="before")
    def normalize_position(cls, v):
        if not isinstance(v, str):
            return "TOP_CENTER"
        s = v.upper().strip()
        if "LOW" in s or "BOT" in s:
            return "LOWER_THIRD"
        if "MID" in s or "CEN" in s:
            return "CENTER"
        return "TOP_CENTER"

    @field_validator("style", mode="before")
    def normalize_style(cls, v):
        if not isinstance(v, str):
            return "HIGHLIGHT_YELLOW"
        s = v.strip()
        allowed = {"HIGHLIGHT_YELLOW", "highlight-yellow", "IMPACT_RED", "BOLD_RED", "CLEAN_WHITE", "clean-white", "NEON_GLOW", "neon-glow", "BOLD_CONTRAST", "bold-contrast", "HANDWRITTEN_WARM", "handwritten-warm", "CLEAN_CYAN", "ELEGANT_GOLD"}
        return s if s in allowed else "HIGHLIGHT_YELLOW"

class SFXCue(BaseModel):
    suggested_sfx: str = Field(..., description="ID hiệu ứng âm thanh (ví dụ: cinematic_sub_boom, whoosh_fast)")
    start_offset: float = Field(default=0.1, description="Độ trễ giây so với điểm bắt đầu phân đoạn")
    volume: float = Field(default=0.85, ge=0.0, le=1.0)

class CommentarySegment(BaseModel):
    beat: str = Field(..., description="Nhịp kể chuyện")
    time_range: TimeRange
    voiceover: str = Field(..., description="Lời bình phát thanh mượt mà")
    voiceover_vi_translation: Optional[str] = Field(default="", description="Bản dịch nghĩa gợi ý tiếng Việt giúp người dùng đọc hiểu")
    text_overlay: TextOverlay
    sfx_cue: Optional[SFXCue] = None
    visual_hint: str = Field(default="", description="Gợi ý góc quay / hiệu ứng cho editor")
    style: Optional[dict] = None

    @field_validator("beat", mode="before")
    def normalize_beat(cls, v):
        if not isinstance(v, str):
            return "HOOK"
        s = v.upper().strip()
        # Cho phép các beat đặc thù của bộ template hoặc step
        known_beats = {
            "HOOK", "BUILD_UP", "CLIMAX", "PAYOFF",
            "SETUP", "WORK", "CLIMAX_SLOWMO", "END",
            "BEFORE", "AFTER", "PROBLEM", "TURN",
            "EMERGENCY", "DIAGNOSIS", "TREATMENT", "RELIEF", "QUESTION", "REVEAL", "PROOF", "TRANSITION", "VERDICT", "CHARACTER"
        }
        if s in known_beats or s.startswith("STEP_"):
            return s
        if "HOOK" in s:
            return "HOOK"
        if "BUILD" in s or "PROGRESS" in s:
            return "BUILD_UP"
        if "CLIMAX" in s or "PEAK" in s:
            return "CLIMAX"
        if "PAYOFF" in s or "OUTRO" in s:
            return "PAYOFF"
        return "BUILD_UP"

class CapCutMetadata(BaseModel):
    video_id: str
    title: str
    duration_seconds: float
    skill_applied: str
    language: str
    total_words: int
    average_wpm: float
    template_id: Optional[str] = Field(default=None, description="ID template (hazard-rescue, shock-hook, how-it-works, satisfying, before-after, story)")
    template_version: Optional[str] = Field(default="1.1.0", description="Phiên bản template áp dụng")
    contact_sheet_file: Optional[str] = Field(default=None, description="Tên file contact sheet 3x3 đã xuất")
    thumbnail_file: Optional[str] = Field(default=None, description="Tên file thumbnail poster đã xuất")
    voiceover_audio_file: Optional[str] = Field(default=None, description="Tên file audio voiceover đã sinh")
    voiceover_voice: Optional[str] = Field(default=None, description="ID giọng đọc đã áp dụng")

class CapCutCommentaryInterchange(BaseModel):
    """Đặc tả JSON xuất sang CapCut Schema Version 3"""
    schema_version: int = 3
    format: str = "youtube-story-commentary-capcut"
    template_id: Optional[str] = None
    template_version: Optional[str] = "1.1.0"
    note: Optional[str] = None
    video_metadata: CapCutMetadata
    segments: List[CommentarySegment]

# ==========================================
# 4. API REQUEST / RESPONSE MODELS
# ==========================================

class CommentaryRequest(BaseModel):
    video_url: Optional[str] = Field(default=None, description="URL video YouTube / TikTok")
    video_path: Optional[str] = Field(default=None, description="Đường dẫn file video cục bộ")
    skill_id: str = Field(default="curiosity-explainer", description="ID phong cách biên kịch")
    template_id: Optional[str] = None
    language: str = Field(default="vi", description="Ngôn ngữ lời bình (vi / en)")
    target_duration: Optional[float] = Field(default=None, description="Thời lượng mục tiêu")
    enable_tts: bool = Field(default=True, description="Tự động tạo giọng đọc Voiceover TTS")
    tts_voice: str = Field(default="am_adam", description="ID giọng đọc (am_adam, bm_george, af_bella, en-US-ChristopherNeural...)")
    tts_speed: float = Field(default=1.0, ge=0.5, le=2.0, description="Tốc độ đọc (0.8 - 1.3)")

class RewriteRequest(BaseModel):
    video_id: str = Field(..., description="ID video đã có sẵn Visual Timeline trong hệ thống")
    new_skill_id: str = Field(..., description="Skill mới muốn áp dụng")
    template_id: Optional[str] = None
    language: Optional[str] = Field(default="vi", description="Ngôn ngữ lời bình")
    enable_tts: bool = Field(default=True, description="Tự động tạo lại giọng đọc Voiceover TTS")
    tts_voice: str = Field(default="am_adam", description="ID giọng đọc")
    tts_speed: float = Field(default=1.0, ge=0.5, le=2.0, description="Tốc độ đọc")

class TTSSynthesizeRequest(BaseModel):
    video_id: str = Field(..., description="ID video cần tạo giọng đọc")
    voice: str = Field(default="am_adam", description="ID giọng đọc")
    speed: float = Field(default=1.0, ge=0.5, le=2.0, description="Tốc độ đọc")

class SaveScriptResponse(BaseModel):
    """SPEC-01: kết quả lưu bản kịch bản người dùng đã sửa trong giao diện"""
    status: str
    video_id: str
    saved_version: int = Field(description="ID dòng mới trong bảng commentary_scripts (cơ chế append, số càng lớn càng mới)")
    saved_at: str = Field(description="Thời điểm lưu theo giờ UTC, ISO-8601")
    segment_count: int

class ProcessVideoResponse(BaseModel):
    status: str
    video_id: str
    contact_sheet_url: Optional[str] = Field(default=None, description="URL ảnh lưới 3x3 xem trước")
    audio_hint: Optional[AudioHint] = Field(default=None, description="Thông tin bóc tách âm thanh")
    visual_timeline: VisualActionTimeline
    capcut_json: CapCutCommentaryInterchange
    voiceover_audio_url: Optional[str] = Field(default=None, description="URL file audio voiceover đã sinh")
    voiceover_audio_duration: Optional[float] = Field(default=None, description="Thời lượng file voiceover")
    token_usage: dict = Field(default_factory=dict)
