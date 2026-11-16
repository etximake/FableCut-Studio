import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from openai import OpenAI
from src.core.config import settings
from src.core.utils import extract_json_from_response
from src.skills.registry import registry
from src.models.schemas import VisualActionTimeline, CapCutCommentaryInterchange, TemplateRecommendation

logger = logging.getLogger(__name__)

ALLOWED_TEMPLATES = {"hazard-rescue", "shock-hook", "how-it-works", "satisfying", "before-after", "story"}

# Decision tree from fablecut-bundle/presets/templates/index.json, in order.
# Each entry: (evidence signal, template_id, reason naming the observed signal).
_DECISION_TREE = [
    ("has_transformation", "before-after",
     "Timeline cho thấy khác biệt trước–sau nhìn thấy rõ, nên chọn before-after."),
    ("has_hazard_or_breakdown", "hazard-rescue",
     "Timeline cho thấy sự cố/hỏng hóc/nguy hiểm, nên chọn hazard-rescue."),
    ("has_surprising_fact", "shock-hook",
     "Timeline có con số/sự thật gây ngạc nhiên thể hiện rõ, nên chọn shock-hook."),
    ("has_distinct_steps", "how-it-works",
     "Timeline có các bước/thao tác phân biệt được, nên chọn how-it-works."),
    ("process_is_main_appeal", "satisfying",
     "Bản thân quy trình là điểm hấp dẫn chính, nên chọn satisfying."),
    ("has_person_story", "story",
     "Timeline xoay quanh 1 nhân vật và câu chuyện của người đó, nên chọn story."),
]

# Signal each template needs; used to warn when a manual choice contradicts
# the observed signals. how-it-works needs none: it is the safe default.
_TEMPLATE_REQUIRED_SIGNAL = {
    "before-after": "has_transformation",
    "hazard-rescue": "has_hazard_or_breakdown",
    "shock-hook": "has_surprising_fact",
    "satisfying": "process_is_main_appeal",
    "story": "has_person_story",
}

_SIGNAL_LABELS = {
    "has_transformation": "khác biệt trước–sau rõ rệt",
    "has_hazard_or_breakdown": "sự cố/hỏng hóc/nguy hiểm",
    "has_surprising_fact": "con số/sự thật gây ngạc nhiên",
    "has_distinct_steps": "các bước/thao tác phân biệt được",
    "has_person_story": "nhân vật trung tâm và câu chuyện của người đó",
    "process_is_main_appeal": "quy trình tự thân đã hấp dẫn",
}

# Default narrator mode + target feeling per template (Batch 1 plan, H4).
# (narrator_mode, target_feeling, feeling rule given to the LLM)
TEMPLATE_VOICE_DEFAULTS = {
    "shock-hook": (
        "second_person_hook",
        "curiosity",
        "Hook phải chứa 1 chi tiết ngạc nhiên cụ thể lấy từ timeline; các beat sau trả lời đúng chi tiết đó, không mở thêm chi tiết mới.",
    ),
    "how-it-works": (
        "third_person",
        "understanding",
        "Mỗi beat giải thích 1 bước hoặc 1 bộ phận; kết thúc bằng kết quả quan sát được, để người xem hiểu cơ chế.",
    ),
    "satisfying": (
        "minimal_narrator",
        "satisfaction",
        "Lời bình ít nhất có thể để hình ảnh và tiếng hiện trường lên tiếng; không đặt câu hỏi, không bình luận cảm xúc thay người xem.",
    ),
    "before-after": (
        "third_person",
        "satisfaction",
        "Chỉ mô tả khác biệt nhìn thấy được giữa trạng thái trước và sau; beat VERDICT chỉ 1 câu kết luận.",
    ),
    "story": (
        "third_person",
        "curiosity",
        "Xoay quanh 1 nhân vật và vấn đề của người đó; không gán suy nghĩ hay cảm xúc không thể hiện trên hình.",
    ),
    "hazard-rescue": (
        "third_person",
        "curiosity",
        "Nêu dấu hiệu nhìn/nghe thấy, thao tác xử lý quan sát được và kết quả; không tự kết luận nguyên nhân sự cố.",
    ),
}


def compute_word_budget(duration_seconds: float, target_wpm: int) -> int:
    """Total voiceover words that fit the video at the skill's reading pace."""
    return max(8, round(duration_seconds * target_wpm / 60))


def compute_beat_budgets(template_spec: Optional[Dict[str, Any]], duration_seconds: float, total_words: int) -> Dict[str, int]:
    """Split the word budget across template beats, proportional to each beat's
    target_seconds share (normalized to the real duration). Falls back to an
    equal split when the template has no usable timing info."""
    beats = []
    if template_spec:
        beats = [b for b in template_spec.get("structure", {}).get("beats", []) if b.get("beat")]
    if not beats:
        return {}
    shares = []
    for beat in beats:
        target = beat.get("target_seconds") or []
        if len(target) == 2 and float(target[1]) > float(target[0]):
            shares.append(float(target[1]) - float(target[0]))
        else:
            shares.append(0.0)
    if sum(shares) <= 0:
        shares = [1.0] * len(beats)
    total_share = sum(shares)
    budgets = {}
    assigned = 0
    for beat, share in zip(beats, shares):
        words = max(1, round(total_words * share / total_share))
        budgets[beat["beat"]] = words
        assigned += words
    # Fix rounding drift on the largest beat so budgets sum to the total.
    largest = max(budgets, key=lambda name: budgets[name])
    budgets[largest] += total_words - assigned
    return budgets


class CommentaryScriptEngine:
    """
    Chặng 2: Biên soạn kịch bản lời bình CapCut Interchange v3 theo Skill.
    Hoàn toàn xử lý dạng Text-to-Text (~400 tokens), chạy siêu tốc.

    Batch 1: template được gợi ý từ tín hiệu bằng chứng của timeline (không
    từ lựa chọn chủ đề/mục đích của người dùng); skill chỉ quyết định giọng
    điệu; ngôi kể và cảm giác mục tiêu là tham số bắt buộc của prompt.
    """

    def _call_text_llm(
        self,
        api_key: str,
        base_url: Optional[str],
        model: str,
        system_prompt: str,
        user_prompt: str
    ) -> Dict[str, Any]:
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=60.0)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        logger.info(f"Calling Commentary Text LLM with model {model} (base_url: {base_url})...")
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.7
        )
        content = response.choices[0].message.content
        return extract_json_from_response(content)

    def recommend_template(
        self,
        visual_timeline: VisualActionTimeline,
        manual_template_id: Optional[str] = None,
    ) -> TemplateRecommendation:
        """Suggest a template from observed evidence signals, in decision-tree
        order. A manual choice always wins, but if it contradicts the observed
        signals the reason carries an explicit warning."""
        if manual_template_id:
            if manual_template_id not in ALLOWED_TEMPLATES:
                raise ValueError(f"Unknown template_id: {manual_template_id}")
            reason = f"Đang dùng template {manual_template_id} theo lựa chọn thủ công của bạn."
            required = _TEMPLATE_REQUIRED_SIGNAL.get(manual_template_id)
            if required and not getattr(visual_timeline.evidence_signals, required, False):
                reason += (
                    f" Lưu ý: timeline chưa cho thấy {_SIGNAL_LABELS[required]}"
                    f" mà template này cần; hãy kiểm tra trước khi duyệt."
                )
            return TemplateRecommendation(
                template_id=manual_template_id,
                reason=reason,
                source="manual",
            )

        signals = visual_timeline.evidence_signals
        for signal_name, template_id, reason in _DECISION_TREE:
            if getattr(signals, signal_name, False):
                return TemplateRecommendation(template_id=template_id, reason=reason, source="recommended")
        return TemplateRecommendation(
            template_id="how-it-works",
            reason="Không có tín hiệu cấu trúc rõ rệt trong timeline; dùng how-it-works làm mặc định theo decision tree.",
            source="recommended",
        )

    def resolve_narrator_and_feeling(
        self,
        template_id: str,
        narrator_mode: Optional[str] = None,
    ) -> Tuple[str, str, str]:
        """Return (narrator_mode, target_feeling, feeling_rule) for a template.

        The feeling always comes from the template. The narrator mode comes
        from the template default unless the caller explicitly overrides it.
        """
        default_mode, feeling, rule = TEMPLATE_VOICE_DEFAULTS.get(
            template_id, ("third_person", "understanding", "")
        )
        return narrator_mode or default_mode, feeling, rule

    def derive_story_angle(self, timeline: VisualActionTimeline) -> str:
        """Derive one factual story angle from the timeline itself.

        Picks the most confident observed action block as the notable moment.
        Returns "" when the timeline has no usable content, so no generic
        angle sentence is ever injected into the prompt.
        """
        blocks = timeline.action_timeline or []
        if not blocks and not timeline.subject_matter:
            return ""
        peak = None
        if blocks:
            def _peak_key(block):
                observed_bonus = 1.0 if block.evidence_source == "observed" else 0.0
                return (block.confidence + observed_bonus, len(block.observable_changes or ""))

            peak = max(blocks, key=_peak_key)
        parts = []
        if timeline.subject_matter:
            parts.append(f"Chủ thể: {timeline.subject_matter}.")
        if peak is not None:
            start = peak.time_range.start
            end = peak.time_range.end
            moment = f"Khoảnh khắc đáng chú ý nhất ({start:.1f}–{end:.1f}s): {peak.visual_action}"
            if peak.observable_changes:
                moment += f" — {peak.observable_changes}"
            parts.append(moment + ".")
        if timeline.final_outcome:
            parts.append(f"Kết quả cuối: {timeline.final_outcome}.")
        return " ".join(parts)

    def validate_generated_script(self, script: CapCutCommentaryInterchange) -> list[str]:
        """Return review notes for deterministic issues; never silently rewrite generated copy."""
        notes = []
        segments = script.segments
        if not segments:
            return ["Kịch bản không có beat; cần tạo lại hoặc kiểm tra thủ công."]
        expected = script.video_metadata.duration_seconds
        previous_end = 0.0
        for index, segment in enumerate(segments):
            start, end = segment.time_range.start, segment.time_range.end
            if start > previous_end + 0.01:
                notes.append(f"Beat {index + 1} có khoảng trống timeline trước {start:.2f}s.")
            if start < previous_end - 0.01:
                notes.append(f"Beat {index + 1} chồng timeline với beat trước.")
            if end > expected + 0.01:
                notes.append(f"Beat {index + 1} vượt thời lượng video ({expected:.2f}s).")
            if not segment.voiceover.strip():
                notes.append(f"Beat {index + 1} ({segment.beat}) chưa có lời bình.")
            previous_end = end
        if previous_end < expected - 0.25:
            notes.append(f"Timeline lời bình kết thúc ở {previous_end:.2f}s, trước thời lượng video {expected:.2f}s.")
        if segments and len(segments[0].voiceover.split()) < 3:
            notes.append("Hook rất ngắn; hãy kiểm tra xem có đủ cụ thể với video hay không.")
        normalized = [" ".join(s.voiceover.lower().split()) for s in segments]
        if len(normalized) != len(set(normalized)):
            notes.append("Có câu lời bình trùng lặp giữa các beat.")
        unsupported_claim_markers = ("năng suất", "tăng gấp", "tăng trưởng", "khoảng cách", "nguyên nhân", "giúp tiết kiệm", "lợi nhuận", "%")
        for index, segment in enumerate(segments):
            text = segment.voiceover.lower()
            if any(marker in text for marker in unsupported_claim_markers):
                notes.append(f"Beat {index + 1} có thể chứa claim kỹ thuật/định lượng; hãy đối chiếu với bằng chứng trước khi duyệt.")
        return notes

    def generate_commentary(
        self,
        visual_timeline: VisualActionTimeline,
        skill_id: str = "curiosity-explainer",
        language: str = "vi",
        target_duration: Optional[float] = None,
        template_id: Optional[str] = None,
        description_subject: Optional[str] = None,
        description_activity: Optional[str] = None,
        description_focus: Optional[str] = None,
        narrator_mode: Optional[str] = None,
        scene_note: Optional[str] = None,
    ) -> CapCutCommentaryInterchange:
        """
        Tạo kịch bản lời bình đồng bộ với dòng thời gian thị giác.
        """
        skill = registry.get(skill_id)
        duration = target_duration or visual_timeline.duration_seconds

        system_prompt = skill.get_system_instructions(language=language)
        recommendation = self.recommend_template(visual_timeline, template_id)
        template_id = recommendation.template_id
        narrator_mode, target_feeling, feeling_rule = self.resolve_narrator_and_feeling(
            template_id, narrator_mode
        )
        bundle_root = Path(__file__).resolve().parents[2].parent / "fablecut-bundle"
        template_path = bundle_root / "presets" / "templates" / f"{template_id}.json"
        template_spec = json.loads(template_path.read_text(encoding="utf-8")) if template_path.is_file() else None
        word_budget = compute_word_budget(duration, skill.target_wpm)
        beat_budgets = compute_beat_budgets(template_spec, duration, word_budget)
        user_prompt = skill.format_user_prompt(
            visual_timeline=visual_timeline.model_dump(),
            duration=duration,
            language=language,
            template_spec=template_spec,
            template_id=template_id,
            description_subject=description_subject,
            description_activity=description_activity,
            description_focus=description_focus,
            narrator_mode=narrator_mode,
            target_feeling=target_feeling,
            feeling_rule=feeling_rule,
            word_budget=word_budget,
            beat_budgets=beat_budgets,
        )
        story_angle = self.derive_story_angle(visual_timeline)
        if story_angle:
            user_prompt += (
                f"\nGÓC KỂ TỪ TIMELINE: {story_angle}\n"
                "Viết lời bình bám góc kể này; chỉ khẳng định nội dung được hỗ trợ bởi evidence_source/confidence.\n"
            )
        if scene_note:
            user_prompt += (
                f"\nCẢNH ĐÃ CHỌN: {scene_note}\n"
                "Timeline trên đã dồn mốc giây về 0 theo clip đã ghép; viết lời bình liền mạch "
                "như một video liên tục, mốc giây của segment tính theo clip đã ghép.\n"
            )

        raw_result = None
        # 1. Gọi Primary Text Provider
        try:
            raw_result = self._call_text_llm(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
                model=settings.DEFAULT_TEXT_MODEL,
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
        except Exception as e:
            logger.warning(f"Primary Text LLM error: {e}")
            if settings.BACKUP_OPENAI_API_KEY:
                logger.info("Attempting Backup Text LLM...")
                raw_result = self._call_text_llm(
                    api_key=settings.BACKUP_OPENAI_API_KEY,
                    base_url=settings.BACKUP_OPENAI_BASE_URL,
                    model=settings.BACKUP_TEXT_MODEL,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt
                )
            else:
                raise RuntimeError(f"Commentary Script Generation failed: {e}")

        # Tính toán WPM thực tế để kiểm tra chất lượng
        segments = raw_result.get("segments", [])
        total_words = sum(len(seg.get("voiceover", "").split()) for seg in segments)
        average_wpm = round((total_words / max(duration, 1.0)) * 60, 1)

        # Quyết định template_id theo cây quyết định nếu chưa chỉ định
        selected_template = template_id

        # Cập nhật metadata chính xác
        if "video_metadata" in raw_result:
            raw_result["video_metadata"]["duration_seconds"] = duration
            raw_result["video_metadata"]["total_words"] = total_words
            raw_result["video_metadata"]["average_wpm"] = average_wpm
            raw_result["video_metadata"]["skill_applied"] = skill.skill_id
            raw_result["video_metadata"]["language"] = language
            raw_result["video_metadata"]["template_id"] = selected_template
            raw_result["video_metadata"]["template_version"] = "1.1.0"

        raw_result["template_id"] = selected_template
        raw_result["template_recommendation"] = recommendation.model_dump()
        raw_result["story_angle"] = story_angle
        raw_result["narrator_mode"] = narrator_mode
        raw_result["target_feeling"] = target_feeling
        raw_result["review_notes"] = []
        raw_result["template_version"] = template_spec.get("version", "1.1.0") if template_spec else "1.1.0"
        if "video_metadata" in raw_result:
            raw_result["video_metadata"]["template_version"] = raw_result["template_version"]

        result = CapCutCommentaryInterchange(**raw_result)
        result.review_notes = self.validate_generated_script(result)
        return result
