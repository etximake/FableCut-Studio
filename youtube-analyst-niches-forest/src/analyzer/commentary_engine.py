import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from openai import OpenAI
from src.core.config import settings
from src.core.utils import extract_json_from_response
from src.skills.registry import registry
from src.models.schemas import VisualActionTimeline, CapCutCommentaryInterchange

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

    def generate_commentary(
        self,
        visual_timeline: VisualActionTimeline,
        skill_id: str = "curiosity-explainer",
        language: str = "vi",
        target_duration: Optional[float] = None,
        template_id: Optional[str] = None
    ) -> CapCutCommentaryInterchange:
        """
        Tạo kịch bản lời bình đồng bộ với dòng thời gian thị giác.
        """
        skill = registry.get(skill_id)
        duration = target_duration or visual_timeline.duration_seconds
        
        system_prompt = skill.get_system_instructions(language=language)
        template_id = template_id
        if not template_id:
            template_map = {
                "curiosity-explainer": "shock-hook",
                "agri-practitioner": "how-it-works",
                "satisfying-narrator": "satisfying",
                "suspense-storyteller": "story",
                "witty-commentator": "shock-hook",
            }
            timeline_data = visual_timeline.model_dump()
            actions = " ".join([
                str(timeline_data.get("subject_matter", "")),
                str(timeline_data.get("initial_state", "")),
                str(timeline_data.get("final_outcome", "")),
                *[f"{item.visual_action} {item.observable_changes}" for item in visual_timeline.action_timeline],
            ]).lower()
            if any(token in actions for token in ("before", "after", "transformation", "before-after", "old", "new")):
                template_id = "before-after"
            elif any(token in actions for token in ("rescue", "emergency", "breakdown", "limping", "injury", "hazard")):
                template_id = "hazard-rescue"
            else:
                template_id = template_map.get(skill.skill_id, "how-it-works")
        bundle_root = Path(__file__).resolve().parents[2].parent / "fablecut-bundle"
        template_path = bundle_root / "presets" / "templates" / f"{template_id}.json"
        template_spec = json.loads(template_path.read_text(encoding="utf-8")) if template_path.is_file() else None
        user_prompt = skill.format_user_prompt(
            visual_timeline=visual_timeline.model_dump(),
            duration=duration,
            language=language,
            template_spec=template_spec,
            template_id=template_id,
        )
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
        raw_result["template_version"] = template_spec.get("version", "1.1.0") if template_spec else "1.1.0"
        if "video_metadata" in raw_result:
            raw_result["video_metadata"]["template_version"] = raw_result["template_version"]

        return CapCutCommentaryInterchange(**raw_result)
