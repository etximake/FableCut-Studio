from typing import Dict, Any
import json
from src.skills.base import BaseCommentarySkill

class SuspenseStorytellerSkill(BaseCommentarySkill):
    skill_id = "suspense-storyteller"
    display_name = "The Suspense Storyteller (Nhà Kể Chuyện Điện Ảnh)"
    description = "Tạo không khí hồi hộp, nhịp thở dồn dập, đẩy cao mức độ rủi ro và cao trào nghẹt thở như phim hành động/tài liệu điện ảnh."
    suitable_niches = ["survival", "extreme_sports", "challenges", "incidents", "historical_moments", "rescue"]
    target_wpm = 140

    def get_system_instructions(self, language: str = "vi") -> str:
        lang_note = "Toàn bộ kịch bản và lời bình (voiceover) phải được viết bằng TIẾNG VIỆT tự nhiên, điện ảnh." if language == "vi" else "Generate all voiceover narration and text in cinematic, dramatic spoken ENGLISH."
        
        return f"""Bạn là "The Suspense Storyteller" - Biên kịch gia điện ảnh chuyên gia tăng nhịp tim của khán giả trong từng giây video.
{lang_note}

CHIẾN THUẬT BIÊN KỊCH:
1. MỞ ĐẦU NGUY CẤP (IN MEDIAS RES - 0-4s):
   - Đưa người xem thẳng vào thời khắc then chốt hoặc ranh giới giữa thành công và thảm họa.
2. TĂNG TIẾN ÁP LỰC (5-20s):
   - Nhấn mạnh các giới hạn vật lý, con số thời gian đếm ngược hoặc áp lực vô hình.
3. CAO TRÀO ĐIỆN ẢNH (20-35s):
   - Nhịp câu ngắn dồn dập, chèn khoảng lặng [PAUSE: 1s] ngay trước khoảnh khắc quyết định.
4. KẾT CỤC THỎA MÃN (35-cuối):
   - Cú hạ màn giải tỏa toàn bộ căng thẳng.

QUY TẮC NHỊP ĐỘ:
- 135 - 150 từ/phút (~2.3 từ/giây). Đan xen câu dài với cụm từ gãy gọn (2-4 từ: "Không còn đường lui.", "Một tích tắc.").
"""

    def format_user_prompt(self, visual_timeline: Dict[str, Any], duration: float, language: str = "vi", template_spec=None, template_id=None) -> str:
        return self.build_standard_user_prompt(
            visual_timeline=visual_timeline,
            duration=duration,
            language=language,
            custom_header=f"Biên kịch kịch bản điện ảnh kịch tính (Suspense Storyteller) cho video {duration} giây:",
            template_spec=template_spec, template_id=template_id
        )
