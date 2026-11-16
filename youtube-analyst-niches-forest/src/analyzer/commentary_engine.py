import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from openai import OpenAI
from src.core.config import settings
from src.core.utils import extract_json_from_response
from src.skills.registry import registry
from src.models.schemas import VisualActionTimeline, CapCutCommentaryInterchange, TemplateRecommendation

logger = logging.getLogger(__name__)

class CommentaryScriptEngine:
    """
    Chặng 2: Biên soạn kịch bản lời bình CapCut Interchange v3 theo Skill.
    Hoàn toàn xử lý dạng Text-to-Text (~400 tokens), chạy siêu tốc.
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
        skill_id: str,
        topic: str,
        video_purpose: str,
        manual_template_id: Optional[str] = None,
        topic_other: Optional[str] = None,
        video_purpose_other: Optional[str] = None,
    ) -> TemplateRecommendation:
        """Resolve the template from explicit user intent; a manual choice always wins."""
        allowed = {"hazard-rescue", "shock-hook", "how-it-works", "satisfying", "before-after", "story"}
        if manual_template_id:
            if manual_template_id not in allowed:
                raise ValueError(f"Unknown template_id: {manual_template_id}")
            return TemplateRecommendation(
                template_id=manual_template_id,
                reason=f"Đang dùng template {manual_template_id} theo lựa chọn thủ công của bạn.",
                source="manual",
            )

        purpose_templates = {
            "explain_mechanism": ("how-it-works", "Mục đích là giải thích cơ chế, nên ưu tiên trình bày theo từng bước."),
            "how_to": ("how-it-works", "Mục đích là hướng dẫn thực hành, nên ưu tiên cấu trúc giải thích theo từng bước."),
            "show_process": ("satisfying", "Mục đích là xem quy trình vận hành, nên ưu tiên nhịp dựng tập trung vào quá trình."),
            "before_after": ("before-after", "Mục đích là so sánh kết quả trước–sau, nên chọn template chuyển đổi."),
            "troubleshoot": ("hazard-rescue", "Mục đích là xử lý sự cố, nên chọn cấu trúc vấn đề–chẩn đoán–xử lý."),
        }
        if video_purpose in purpose_templates:
            template_id, reason = purpose_templates[video_purpose]
            if topic == "agriculture_crops" and video_purpose == "show_process":
                template_id = "how-it-works"
                reason = "Quy trình cây trồng cần giữ các thao tác và điều kiện rõ ràng; ưu tiên how-it-works thay vì giả định chỉ cần dựng thỏa mãn."
            elif topic == "agricultural_machinery" and video_purpose == "show_process":
                template_id = "how-it-works"
                reason = "Quy trình máy móc cần giữ thao tác và bộ phận có căn cứ; ưu tiên how-it-works thay vì mặc định dựng thỏa mãn."
            if topic == "mining" and video_purpose == "show_process":
                reason += " Nội dung đào mỏ vẫn cần giữ quy trình và vật liệu có căn cứ; kiểm tra note trước khi duyệt."
            if topic == "other" and topic_other:
                reason += f" Chủ đề bạn nhập: {topic_other}."
            return TemplateRecommendation(template_id=template_id, reason=reason, source="recommended")

        skill_templates = {
            "satisfying-narrator": "satisfying",
            "suspense-storyteller": "story",
            "agri-practitioner": "how-it-works",
            "witty-commentator": "shock-hook",
            "curiosity-explainer": "how-it-works",
        }
        template_id = skill_templates.get(skill_id, "how-it-works")
        label = video_purpose_other or "chưa xác định rõ mục đích"
        topic_label = topic_other if topic == "other" and topic_other else topic.replace("_", " ")
        return TemplateRecommendation(
            template_id=template_id,
            reason=f"Chưa có mục đích chuẩn hóa cho '{label}'; tạm đề xuất {template_id} theo skill và chủ đề {topic_label}.",
            source="recommended",
        )

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

    def choose_story_angle(self, timeline: VisualActionTimeline, topic: str, video_purpose: str) -> str:
        if video_purpose == "before_after":
            return "Tập trung mô tả khác biệt quan sát được giữa trạng thái trước và sau."
        if video_purpose == "troubleshoot":
            return "Nêu dấu hiệu nhìn/nghe thấy, thao tác xử lý quan sát được và kết quả; không tự kết luận nguyên nhân."
        if video_purpose in {"how_to", "explain_mechanism"}:
            return "Giải thích từng thao tác hoặc bộ phận chỉ trong phạm vi timeline xác nhận."
        if video_purpose == "show_process":
            return "Tường thuật trình tự vận hành, ưu tiên hình ảnh và âm thanh hiện trường."
        if topic == "agriculture_crops":
            return "Mô tả thao tác và kết quả nhìn thấy; không đưa lời khuyên canh tác chưa có nguồn."
        if topic == "mining":
            return "Mô tả thiết bị, vật liệu và quy trình chỉ khi được thể hiện rõ trong bằng chứng."
        return f"Chọn một luận điểm cụ thể từ các sự kiện đã xác minh: {timeline.subject_matter}."

    def generate_commentary(
        self,
        visual_timeline: VisualActionTimeline,
        skill_id: str = "curiosity-explainer",
        language: str = "vi",
        target_duration: Optional[float] = None,
        template_id: Optional[str] = None,
        topic: str = "other",
        video_purpose: str = "other",
        topic_other: Optional[str] = None,
        video_purpose_other: Optional[str] = None,
    ) -> CapCutCommentaryInterchange:
        """
        Tạo kịch bản lời bình đồng bộ với dòng thời gian thị giác.
        """
        skill = registry.get(skill_id)
        duration = target_duration or visual_timeline.duration_seconds
        
        system_prompt = skill.get_system_instructions(language=language)
        recommendation = self.recommend_template(
            skill.skill_id, topic, video_purpose, template_id, topic_other, video_purpose_other
        )
        template_id = recommendation.template_id
        bundle_root = Path(__file__).resolve().parents[2].parent / "fablecut-bundle"
        template_path = bundle_root / "presets" / "templates" / f"{template_id}.json"
        template_spec = json.loads(template_path.read_text(encoding="utf-8")) if template_path.is_file() else None
        user_prompt = skill.format_user_prompt(
            visual_timeline=visual_timeline.model_dump(),
            duration=duration,
            language=language,
            template_spec=template_spec,
            template_id=template_id,
            topic=topic,
            topic_other=topic_other,
            video_purpose=video_purpose,
            video_purpose_other=video_purpose_other,
        )
        story_angle = self.choose_story_angle(visual_timeline, topic, video_purpose)
        user_prompt += f"\nGÓC KỂ ĐÃ CHỐT: {story_angle}\nTạo lời bình từ góc kể này, nhưng chỉ khẳng định nội dung được hỗ trợ bởi evidence_source/confidence.\n"
        if template_spec and template_id not in user_prompt:
            beats = [b.get("beat") for b in template_spec.get("structure", {}).get("beats", [])]
            user_prompt += f"\nChosen template {template_id} v{template_spec.get('version')}; use beat order: {', '.join(filter(None, beats))}. Preserve the original facts and narration."

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
            raw_result["video_metadata"]["total_words"] = total_words
            raw_result["video_metadata"]["average_wpm"] = average_wpm
            raw_result["video_metadata"]["skill_applied"] = skill.skill_id
            raw_result["video_metadata"]["language"] = language
            raw_result["video_metadata"]["template_id"] = selected_template
            raw_result["video_metadata"]["template_version"] = "1.1.0"

        raw_result["template_id"] = selected_template
        raw_result["template_recommendation"] = recommendation.model_dump()
        raw_result["story_angle"] = story_angle
        raw_result["review_notes"] = []
        raw_result["template_version"] = template_spec.get("version", "1.1.0") if template_spec else "1.1.0"
        if "video_metadata" in raw_result:
            raw_result["video_metadata"]["template_version"] = raw_result["template_version"]

        result = CapCutCommentaryInterchange(**raw_result)
        result.review_notes = self.validate_generated_script(result)
        return result
