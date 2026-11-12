from abc import ABC, abstractmethod
from typing import Dict, Any
import json

class BaseCommentarySkill(ABC):
    """Lớp cơ sở cho mọi Skill biên kịch trong hệ thống"""
    
    skill_id: str
    display_name: str
    description: str
    suitable_niches: list
    target_wpm: int = 135  # Tốc độ đọc mục tiêu (từ/phút)

    @abstractmethod
    def get_system_instructions(self, language: str = "vi") -> str:
        """Trả về chỉ dẫn phong cách và Persona chuyên biệt cho LLM"""
        pass

    def build_standard_user_prompt(
        self,
        visual_timeline: Dict[str, Any],
        duration: float,
        language: str = "vi",
        custom_header: str = "",
        template_spec: Dict[str, Any] = None,
        template_id: str = None
    ) -> str:
        header = custom_header or f"Hãy biên kịch một kịch bản lời bình CapCut cho video có thời lượng {duration} giây."
        template_note = ""
        if template_spec:
            beats = [item.get("beat") for item in template_spec.get("structure", {}).get("beats", []) if item.get("beat")]
            template_note = f"\nTEMPLATE ĐÃ CHỌN ({template_id}): dùng đúng thứ tự beat {', '.join(beats)}; không đổi nội dung/voiceover để ép timeline vào template.\n"
        beat_template = ""
        if template_spec and beats:
            beat_template = ",\n".join(
                f'''    {{
      "beat": "{beat}",
      "time_range": {{ "start": <contiguous_start>, "end": <contiguous_end> }},
      "voiceover": "...",
      "voiceover_vi_translation": "...",
      "text_overlay": {{ "text": "...", "position": "TOP_CENTER", "style": "HIGHLIGHT_YELLOW" }},
      "sfx_cue": null,
      "visual_hint": "..."
    }}''' for beat in beats
            )
        else:
            beat_template = f'''    {{
      "beat": "HOOK",
      "time_range": {{ "start": 0.0, "end": {min(4.5, duration)} }},
      "voiceover": "...", "voiceover_vi_translation": "...",
      "text_overlay": {{ "text": "...", "position": "TOP_CENTER", "style": "HIGHLIGHT_YELLOW" }},
      "sfx_cue": null, "visual_hint": "..."
    }}'''
        return f"""{header}
{template_note}

NHẬT KÝ HÀNH ĐỘNG THỰC TẾ (VISUAL ACTION TIMELINE):
{json.dumps(visual_timeline, ensure_ascii=False, indent=2)}

QUY TẮC BẮT BUỘC VỀ DỊCH NGHĨA (voiceover_vi_translation):
- Với mỗi phân đoạn, ngoài câu lời bình chính 'voiceover' (bằng ngôn ngữ {language.upper()}), BẮT BUỘC cung cấp thêm trường 'voiceover_vi_translation' bằng TIẾNG VIỆT tự nhiên, chân chất, chính xác nghĩa của câu thoại để người dùng đọc hiểu rõ ràng.

Yêu cầu xuất ra JSON duy nhất theo đúng cấu trúc CapCut Interchange v3:
{{
  "schema_version": 3,
  "format": "youtube-story-commentary-capcut",
  "video_metadata": {{
    "video_id": "{visual_timeline.get('video_id', 'vid_shorts')}",
    "title": "{visual_timeline.get('subject_matter', 'Video shorts')}",
    "duration_seconds": {duration},
    "skill_applied": "{self.skill_id}",
    "language": "{language}",
    "total_words": 95,
    "average_wpm": {float(self.target_wpm)}
  }},
  "segments": [
{beat_template}
  ]
}}
"""

    def format_user_prompt(self, visual_timeline: Dict[str, Any], duration: float, language: str = "vi", template_spec: Dict[str, Any] = None, template_id: str = None) -> str:
        """Định dạng User Prompt cho Chặng 2 mặc định dùng standard template"""
        return self.build_standard_user_prompt(visual_timeline, duration, language, template_spec=template_spec, template_id=template_id)
