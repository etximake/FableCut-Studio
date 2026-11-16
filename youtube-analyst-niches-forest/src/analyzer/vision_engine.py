import base64
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from openai import OpenAI
from src.core.config import settings
from src.core.utils import extract_json_from_response
from src.models.schemas import VisualActionTimeline, AudioHint

logger = logging.getLogger(__name__)

STAGE1_SYSTEM_PROMPT = """You are a precision video timeline analyzer. Your mission is to observe a 3x3 filmstrip contact sheet (9 chronological frames) extracted from a short video, where each frame has a visible timestamp badge [MM:SS] in the top-left corner.

Your task is to produce an accurate, objective, second-by-second narrative timeline of what physically happens on screen.

Core Rules:
1. Ground Truth First: Rely strictly on what is visually verifiable in the 9 frames. Never invent actions, objects, or results not visible in the images.
2. Timestamp Accuracy: Use the timestamp badges printed on each cell to anchor events to exact seconds.
3. Audio Integration:
   - If audio_hint has speech and status is 'COMPLETE', use key technical terms or numbers mentioned to enrich the description.
   - If audio status indicates truncation (TRUNCATED_START or TRUNCATED_END), do NOT try to continue the cut sentence; focus on visual action.
   - If audio is noise or irrelevant chatter, ignore it completely.
4. Evidence labels: each action must include evidence_source. Use observed only for visible evidence; heard only for information explicitly present in audio_hint; inferred for a cautious inference; unknown when evidence is insufficient. Do not treat audio statements as visually observed facts.
5. Evidence signals: set each evidence_signals flag to true ONLY when the pattern is directly visible in the frames. A clear visible before/after difference sets has_transformation. A visible breakdown, jam, injury, or distress sets has_hazard_or_breakdown. Two to four visually distinct steps or operations set has_distinct_steps. A surprising number or fact plainly shown on screen sets has_surprising_fact; never invent a number to set it. One central person whose problem or job drives the footage sets has_person_story. When the process itself is the main appeal and needs little explanation, set process_is_main_appeal. When unsure, leave the flag false.
6. Output Schema: Return strictly valid JSON matching the requested structure without any markdown wrap.
"""


def build_vision_user_prompt(video_id: str, duration_seconds: float, audio_hint: AudioHint) -> str:
    """Build the Stage-1 user prompt from observation inputs only.

    Pure function (no user labels, no user description): Vision must observe
    blind so its timeline cannot be primed by a wrong user selection.
    Example action blocks are scaled to the real duration instead of
    assuming a ~35s video.
    """
    quarters = [round(duration_seconds * f, 2) for f in (0.0, 0.25, 0.5, 0.75, 1.0)]
    return f"""Analyze this 3x3 contact sheet for video ID: {video_id}
Total Duration: {duration_seconds}s

AUDIO HINT DATA:
{audio_hint.model_dump_json(indent=2)}

Return strictly valid JSON matching:
{{
  "video_id": "{video_id}",
  "duration_seconds": {duration_seconds},
  "subject_matter": "Brief summary of who/what is the focus",
  "initial_state": "Description of frame 1 setup and environment",
  "action_timeline": [
    {{
      "time_range": {{"start": {quarters[0]}, "end": {quarters[1]}}},
      "visual_action": "Clear description of action in frames 1-2",
      "observable_changes": "Visible changes observed",
      "confidence": 0.8,
      "evidence_source": "observed"
    }},
    {{
      "time_range": {{"start": {quarters[1]}, "end": {quarters[2]}}},
      "visual_action": "Action in frames 3-5",
      "observable_changes": "Visible changes",
      "confidence": 0.8,
      "evidence_source": "observed"
    }},
    {{
      "time_range": {{"start": {quarters[2]}, "end": {quarters[3]}}},
      "visual_action": "Action in frames 6-7",
      "observable_changes": "Visible changes",
      "confidence": 0.8,
      "evidence_source": "observed"
    }},
    {{
      "time_range": {{"start": {quarters[3]}, "end": {quarters[4]}}},
      "visual_action": "Action in frames 8-9",
      "observable_changes": "Outcome shown in last frame",
      "confidence": 0.8,
      "evidence_source": "observed"
    }}
  ],
  "final_outcome": "Definitive result shown in the final frame",
  "evidence_signals": {{
    "has_transformation": false,
    "has_hazard_or_breakdown": false,
    "has_distinct_steps": false,
    "has_surprising_fact": false,
    "has_person_story": false,
    "process_is_main_appeal": false
  }}
}}
"""


class VisionActionEngine:
    """
    Chặng 1: Bóc tách sự thật thị giác từ 1 ảnh Contact Sheet 3x3 duy nhất.
    Hỗ trợ Provider chính và Provider dự phòng (Failover).
    Vision chạy mù: không nhận nhãn hay mô tả của người dùng.
    """

    def _encode_image_to_base64(self, image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def _call_openai_compatible_vision(
        self,
        api_key: str,
        base_url: Optional[str],
        model: str,
        image_base64: str,
        user_prompt: str
    ) -> Dict[str, Any]:
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=90.0)

        messages = [
            {"role": "system", "content": STAGE1_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}",
                            "detail": "high"
                        }
                    }
                ]
            }
        ]

        logger.info(f"Calling Vision API with model {model} (base_url: {base_url})...")
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2
        )
        content = response.choices[0].message.content
        return extract_json_from_response(content)

    def extract_visual_timeline(
        self,
        video_id: str,
        contact_sheet_path: str,
        audio_hint: AudioHint,
        duration_seconds: float
    ) -> VisualActionTimeline:
        """
        Gửi ảnh lưới 3x3 + audio hint lên Vision LLM để sinh VisualActionTimeline.
        Không nhận bất kỳ nhãn/mô tả nào của người dùng (Vision mù).
        """
        image_b64 = self._encode_image_to_base64(contact_sheet_path)
        user_prompt = build_vision_user_prompt(video_id, duration_seconds, audio_hint)

        # 1. Thử gọi Primary Provider
        try:
            raw_result = self._call_openai_compatible_vision(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
                model=settings.DEFAULT_VISION_MODEL,
                image_base64=image_b64,
                user_prompt=user_prompt
            )
            return VisualActionTimeline(**raw_result)
        except Exception as e:
            logger.warning(f"Primary Vision Provider error: {e}")

            # 2. Thử Backup Provider nếu có cấu hình
            if settings.BACKUP_OPENAI_API_KEY:
                logger.info("Attempting Backup Vision Provider...")
                raw_result = self._call_openai_compatible_vision(
                    api_key=settings.BACKUP_OPENAI_API_KEY,
                    base_url=settings.BACKUP_OPENAI_BASE_URL,
                    model=settings.BACKUP_VISION_MODEL,
                    image_base64=image_b64,
                    user_prompt=user_prompt
                )
                return VisualActionTimeline(**raw_result)
            raise RuntimeError(f"Vision Analysis failed: {e}")
