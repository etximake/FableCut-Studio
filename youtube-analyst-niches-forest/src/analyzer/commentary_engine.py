import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from openai import OpenAI
from src.core.config import settings
from src.core.utils import extract_json_from_response
from src.skills.registry import registry
from src.models.schemas import (
    CapCutCommentaryInterchange,
    Direction,
    DirectionBeat,
    TemplateRecommendation,
    VisualActionTimeline,
)

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
        user_prompt: str,
        temperature: float = 0.7,
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
            temperature=temperature
        )
        content = response.choices[0].message.content
        return extract_json_from_response(content)

    def _call_text_llm_with_backup(
        self, system_prompt: str, user_prompt: str, temperature: float = 0.7
    ) -> Dict[str, Any]:
        """Gọi LLM chính, hỏng thì thử backup; cả hai hỏng thì raise."""
        try:
            return self._call_text_llm(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
                model=settings.DEFAULT_TEXT_MODEL,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
            )
        except Exception as e:
            logger.warning(f"Primary Text LLM error: {e}")
            if settings.BACKUP_OPENAI_API_KEY:
                logger.info("Attempting Backup Text LLM...")
                return self._call_text_llm(
                    api_key=settings.BACKUP_OPENAI_API_KEY,
                    base_url=settings.BACKUP_OPENAI_BASE_URL,
                    model=settings.BACKUP_TEXT_MODEL,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                )
            raise RuntimeError(f"Commentary Script Generation failed: {e}")

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

    def _load_template_spec(self, template_id: str) -> Optional[Dict[str, Any]]:
        bundle_root = Path(__file__).resolve().parents[2].parent / "fablecut-bundle"
        template_path = bundle_root / "presets" / "templates" / f"{template_id}.json"
        if template_path.is_file():
            return json.loads(template_path.read_text(encoding="utf-8"))
        return None

    def _template_beats(self, template_spec: Optional[Dict[str, Any]]) -> list:
        if template_spec:
            beats = [
                b for b in template_spec.get("structure", {}).get("beats", [])
                if b.get("beat")
            ]
            if beats:
                return beats
        return [{"beat": beat} for beat in ("HOOK", "BUILD", "CLIMAX", "PAYOFF")]

    def generate_direction(
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
    ) -> Direction:
        """LLM viết bản Định hướng từ timeline + template (mẫu beats.json/storyboard.json).

        Bản này là kế hoạch duy nhất điều khiển kịch bản: promise, khoảnh
        khắc chính, từng beat gắn với vùng timeline, overlay và SFX dự kiến.
        LLM hỏng/trả JSON sai thì dùng bản fallback suy ra bằng quy tắc, để
        pipeline không chết; bản fallback ghi rõ source="fallback".
        """
        skill = registry.get(skill_id)
        duration = target_duration or visual_timeline.duration_seconds
        recommendation = self.recommend_template(visual_timeline, template_id)
        template_id = recommendation.template_id
        narrator_mode, target_feeling, feeling_rule = self.resolve_narrator_and_feeling(
            template_id, narrator_mode
        )
        template_spec = self._load_template_spec(template_id)
        template_beats = self._template_beats(template_spec)
        word_budget = compute_word_budget(duration, skill.target_wpm)

        beat_lines = []
        for beat in template_beats:
            target = beat.get("target_seconds")
            note = beat.get("note", "")
            beat_lines.append(f"- {beat['beat']}: mục tiêu {target}s. {note}")
        block_lines = []
        for block in visual_timeline.action_timeline or []:
            tr = block.time_range
            block_lines.append(
                f"- {tr.start:.1f}–{tr.end:.1f}s: {block.visual_action}"
                f" | thay đổi: {block.observable_changes or 'không rõ'}"
                f" | confidence {block.confidence:.2f} ({block.evidence_source})"
            )
        description_lines = []
        for label, value in (
            ("Chủ thể", description_subject),
            ("Hoạt động", description_activity),
            ("Điểm nhấn", description_focus),
        ):
            if value:
                description_lines.append(f"- {label} (người dùng mô tả, CHƯA kiểm chứng): {value}")

        system_prompt = (
            "You are the director of a short commentary video. Plan the video "
            "before any script is written. Reply with JSON only, matching the "
            "Direction schema: promise, key_moment_start, key_moment_end, "
            "key_moment_reason, beats (one per template beat, in order), "
            "sound_note. Rules: only claim what the timeline evidence supports; "
            "one promise sentence; the key moment is the single most notable "
            "observed block; each beat needs purpose (one sentence), "
            "source_start/source_end inside the video duration following the "
            "template beat order, key_evidence copied from observed changes, "
            "overlay_text of at most 6 words (empty when no text is needed), "
            "sfx_cue only at genuine sound moments (at most 3 beats, else null), "
            "and pace slow/normal/brisk. Do not invent numbers, names or facts "
            "absent from the timeline."
        )
        user_prompt = (
            f"Chủ thể video: {visual_timeline.subject_matter or 'không rõ'}.\n"
            f"Thời lượng: {duration:.1f}s. Ngôn ngữ kịch bản: {language}.\n"
            f"Template: {template_id}. Ngôi kể: {narrator_mode}. Cảm xúc mục tiêu: {target_feeling}. {feeling_rule}\n"
            f"Ngân sách từ cho kịch bản: {word_budget} từ.\n"
            f"Trạng thái đầu: {visual_timeline.initial_state or 'không rõ'}.\n"
            f"Kết quả cuối: {visual_timeline.final_outcome or 'không rõ'}.\n"
            "Beats của template (đúng thứ tự, mỗi beat 1 mục trong beats):\n"
            + "\n".join(beat_lines)
            + "\nTimeline quan sát:\n"
            + ("\n".join(block_lines) if block_lines else "- (không có block)")
            + ("\nMô tả của người dùng:\n" + "\n".join(description_lines) if description_lines else "")
            + (f"\nCẢNH ĐÃ CHỌN: {scene_note}\n" if scene_note else "")
        )
        try:
            raw = self._call_text_llm_with_backup(
                system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.3
            )
            raw["video_id"] = visual_timeline.video_id
            raw["template_id"] = template_id
            raw["narrator_mode"] = narrator_mode
            raw["target_feeling"] = target_feeling
            raw["source"] = "llm"
            direction = Direction(**raw)
            direction = self._sanitize_direction(direction, template_beats, duration)
            if direction.beats:
                return direction
            logger.warning("Direction LLM returned no usable beats; using fallback.")
        except Exception as e:
            logger.warning(f"Direction LLM failed ({e}); using fallback.")
        return self.fallback_direction(
            visual_timeline, template_id, template_beats, duration,
            narrator_mode, target_feeling,
        )

    def _sanitize_direction(
        self, direction: Direction, template_beats: list, duration: float
    ) -> Direction:
        """Ép bản Định hướng về đúng beat của template và trong thời lượng."""
        allowed = [b["beat"] for b in template_beats]
        kept = []
        for beat in direction.beats:
            if beat.beat not in allowed:
                continue
            beat.source_start = min(max(0.0, beat.source_start), duration)
            beat.source_end = min(max(beat.source_start, beat.source_end), duration)
            kept.append(beat)
        direction.beats = kept
        direction.key_moment_start = min(max(0.0, direction.key_moment_start), duration)
        direction.key_moment_end = min(max(direction.key_moment_start, direction.key_moment_end), duration)
        return direction

    def fallback_direction(
        self,
        visual_timeline: VisualActionTimeline,
        template_id: str,
        template_beats: list,
        duration: float,
        narrator_mode: str,
        target_feeling: str,
    ) -> Direction:
        """Bản Định hướng suy ra bằng quy tắc khi LLM hỏng: an toàn, không bịa."""
        blocks = visual_timeline.action_timeline or []
        peak = None
        if blocks:
            def _peak_key(block):
                observed_bonus = 1.0 if block.evidence_source == "observed" else 0.0
                return (block.confidence + observed_bonus, len(block.observable_changes or ""))

            peak = max(blocks, key=_peak_key)
        angle = self.derive_story_angle(visual_timeline)
        promise = angle.split(".")[0].strip() + "." if angle else (visual_timeline.subject_matter or "Video.")
        total_ref = sum(
            (b.get("target_seconds") or [0, 0])[1] - (b.get("target_seconds") or [0, 0])[0]
            for b in template_beats
        ) or duration
        beats = []
        cursor = 0.0
        for index, beat in enumerate(template_beats):
            target = beat.get("target_seconds") or [0, 0]
            span = (target[1] - target[0]) * duration / total_ref if total_ref else duration / len(template_beats)
            start = cursor
            end = duration if index == len(template_beats) - 1 else min(duration, cursor + span)
            nearest = None
            if blocks:
                mid = (start + end) / 2
                nearest = min(blocks, key=lambda b: abs((b.time_range.start + b.time_range.end) / 2 - mid))
            overlay = ""
            if nearest and nearest.visual_action:
                overlay = " ".join(nearest.visual_action.split()[:6])
            beats.append(DirectionBeat(
                beat=beat["beat"],
                purpose=beat.get("note", "") or (nearest.visual_action if nearest else ""),
                source_start=round(start, 3),
                source_end=round(end, 3),
                key_evidence=nearest.observable_changes if nearest else "",
                overlay_text=overlay,
                sfx_cue=None,
                pace="normal",
            ))
            cursor = end
        return Direction(
            video_id=visual_timeline.video_id,
            template_id=template_id,
            promise=promise,
            key_moment_start=peak.time_range.start if peak else 0.0,
            key_moment_end=peak.time_range.end if peak else 0.0,
            key_moment_reason=peak.visual_action if peak else "",
            beats=beats,
            sound_note="",
            narrator_mode=narrator_mode,
            target_feeling=target_feeling,
            source="fallback",
        )

    def validate_script_against_direction(
        self, script: CapCutCommentaryInterchange, direction: Direction
    ) -> list[str]:
        """Đối chiếu kịch bản với bản Định hướng; chỉ ghi chú, không sửa lặng lẽ."""
        notes = []
        segments = script.segments
        plan = direction.beats
        if not plan:
            return notes
        if len(segments) != len(plan):
            notes.append(
                f"Kịch bản có {len(segments)} segment nhưng Định hướng có {len(plan)} beat."
            )
        planned_ids = [b.beat for b in plan]
        actual_ids = [s.beat for s in segments]
        for index, (planned, actual) in enumerate(zip(planned_ids, actual_ids)):
            if planned != actual:
                notes.append(
                    f"Beat thứ {index + 1} trong kịch bản là {actual}, Định hướng yêu cầu {planned}."
                )
                break
        promise_words = self._content_words(direction.promise)
        if promise_words and segments:
            hook_words = self._content_words(segments[0].voiceover)
            if not (promise_words & hook_words):
                notes.append("Hook không nhắc tới từ khóa nào trong câu hứa hẹn của Định hướng.")
        by_beat = {s.beat: s for s in segments}
        for beat in plan:
            segment = by_beat.get(beat.beat)
            if segment is None:
                continue
            planned_sfx = (beat.sfx_cue or "").strip()
            actual_sfx = ""
            if segment.sfx_cue is not None:
                cue = segment.sfx_cue
                if isinstance(cue, dict):
                    actual_sfx = cue.get("suggested_sfx", "") or ""
                else:
                    actual_sfx = getattr(cue, "suggested_sfx", "") or ""
                actual_sfx = str(actual_sfx).strip()
            if planned_sfx and not actual_sfx:
                notes.append(f"Beat {beat.beat} đã định SFX ({planned_sfx}) nhưng kịch bản không có.")
            elif actual_sfx and not planned_sfx:
                notes.append(f"Beat {beat.beat} có SFX ({actual_sfx}) ngoài kế hoạch Định hướng.")
            planned_overlay = (beat.overlay_text or "").strip()
            actual_overlay = (segment.text_overlay.text or "").strip() if segment.text_overlay else ""
            if planned_overlay and not actual_overlay:
                notes.append(f"Beat {beat.beat} đã định chữ overlay nhưng kịch bản không có.")
        return notes

    _STOPWORDS = {
        "the", "and", "with", "that", "this", "from", "into", "over", "your",
        "when", "what", "have", "will", "just", "like", "then", "than",
        "much", "more", "most", "very", "really", "about", "after", "before",
        "cái", "của", "và", "là", "có", "trong", "với", "được", "một",
        "những", "này", "kia", "cho", "khi", "để", "như", "rất", "đã",
        "đang", "sẽ", "không", "cũng", "mà", "thì", "là",
    }

    @classmethod
    def _content_words(cls, text: str) -> set:
        words = set()
        for raw in text.lower().split():
            word = raw.strip(".,!?;:\"'()[]«»“”")
            if len(word) >= 4 and word not in cls._STOPWORDS:
                words.add(word)
        return words

    def enforce_script_duration(
        self, script: CapCutCommentaryInterchange, duration: float
    ) -> list[str]:
        """Clamp segment times to [0, duration]; never silently extend a Short.

        The LLM is told the duration and word budget, but it still overshoots
        segment ends. Anything past the duration is cut (last segment clipped,
        later segments dropped) and reported in a review note, so the exported
        JSON always fits the video instead of failing downstream or producing
        a longer video. Voiceover text is untouched; TTS re-times segments by
        actual speech when it runs.
        """
        notes: list[str] = []
        kept = []
        for segment in script.segments:
            start = max(0.0, segment.time_range.start)
            end = min(segment.time_range.end, duration)
            if start >= duration - 0.01 or end - start < 0.01:
                notes.append(
                    f"Beat {segment.beat} nằm ngoài thời lượng {duration:.1f}s nên đã bỏ."
                )
                continue
            if segment.time_range.end > duration + 0.01:
                notes.append(
                    f"Beat {segment.beat} vượt {duration:.1f}s nên đã cắt mốc kết thúc "
                    f"từ {segment.time_range.end:.1f}s về {duration:.1f}s."
                )
            segment.time_range.start = round(start, 3)
            segment.time_range.end = round(end, 3)
            kept.append(segment)
        script.segments = kept
        if not kept:
            notes.append("Kịch bản không còn beat nào trong thời lượng video; cần tạo lại.")
        return notes

    def validate_generated_script(
        self,
        script: CapCutCommentaryInterchange,
        word_budget: Optional[int] = None,
    ) -> list[str]:
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
        if word_budget:
            total_words = sum(len(s.voiceover.split()) for s in segments)
            if total_words > word_budget * 1.05:
                notes.append(
                    f"Lời bình dài {total_words} từ, vượt ngân sách {word_budget} từ cho "
                    f"{expected:.1f}s; giọng đọc có thể bị cắt cụt ở cuối. Hãy viết lại ngắn hơn."
                )
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
        direction: Optional[Direction] = None,
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
        if direction is not None:
            beat_lines = []
            for beat in direction.beats:
                beat_lines.append(
                    f"- {beat.beat} ({beat.source_start:.1f}–{beat.source_end:.1f}s): {beat.purpose}"
                    f" | bằng chứng: {beat.key_evidence or 'không rõ'}"
                    f" | overlay: {beat.overlay_text or 'không có'}"
                    f" | SFX: {beat.sfx_cue or 'không có'} | nhịp: {beat.pace}"
                )
            user_prompt += (
                "\nBẢN ĐỊNH HƯỚNG ĐÃ DUYỆT — BẮT BUỘC TUÂN THEO:\n"
                f"Câu hứa hẹn: {direction.promise}\n"
                f"Khoảnh khắc chính ({direction.key_moment_start:.1f}–{direction.key_moment_end:.1f}s): "
                f"{direction.key_moment_reason}\n"
                + "\n".join(beat_lines)
                + (f"\nChỉ đạo âm thanh: {direction.sound_note}" if direction.sound_note else "")
                + "\nViết đúng số beat, đúng thứ tự, đúng mục đích từng beat; hook phải giữ câu hứa hẹn; "
                "chỉ đặt SFX ở beat đã định; overlay theo đúng chữ đã định.\n"
            )

        raw_result = self._call_text_llm_with_backup(
            system_prompt=system_prompt, user_prompt=user_prompt
        )

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
        enforcement_notes = self.enforce_script_duration(result, duration)
        result.review_notes = enforcement_notes + self.validate_generated_script(
            result, word_budget=word_budget
        )
        return result
