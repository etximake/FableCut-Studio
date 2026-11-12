import base64
import json
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
4. Output Schema: Return strictly valid JSON matching the requested structure without any markdown wrap.
"""

class VisionActionEngine:
    """
    Chặng 1: Bóc tách sự thật thị giác từ 1 ảnh Contact Sheet 3x3 duy nhất.
    Hỗ trợ Provider chính và Provider dự phòng (Failover).
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
        """
        image_b64 = self._encode_image_to_base64(contact_sheet_path)
        
        user_prompt = f"""Analyze this 3x3 contact sheet for video ID: {video_id}
Total Duration: {duration_seconds}s

AUDIO HINT DATA:
{audio_hint.model_dump_json(indent=2)}

Return strictly valid JSON matching:
{{
  "video_id": "{video_id}",
  "duration_seconds": {duration_seconds},
  "subject_matter": "Brief summary of who/what is the focus",
  "initial_state": "Description of frame 1 [00:02] setup and environment",
  "action_timeline": [
    {{
      "time_range": {{"start": 0.0, "end": 8.0}},
      "visual_action": "Clear description of action in frames 1-2",
      "observable_changes": "Visible changes observed",
      "confidence": 0.95
    }},
    {{
      "time_range": {{"start": 8.0, "end": 22.0}},
      "visual_action": "Action in frames 3-5",
      "observable_changes": "Visible changes",
      "confidence": 0.95
    }},
    {{
      "time_range": {{"start": 22.0, "end": 35.0}},
      "visual_action": "Action in frames 6-7",
      "observable_changes": "Visible changes",
      "confidence": 0.95
    }},
    {{
      "time_range": {{"start": 35.0, "end": {duration_seconds}}},
      "visual_action": "Action in frames 8-9",
      "observable_changes": "Outcome shown in last frame",
      "confidence": 0.95
    }}
  ],
  "final_outcome": "Definitive result shown in the final frame",
  "recommended_skill": "curiosity-explainer"
}}
"""

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
