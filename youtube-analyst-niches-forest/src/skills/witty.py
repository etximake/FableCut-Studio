from typing import Dict, Any
import json
from src.skills.base import BaseCommentarySkill

class WittyCommentatorSkill(BaseCommentarySkill):
    skill_id = "witty-commentator"
    display_name = "The Witty Commentator (Châm Biếm & Bẻ Lái)"
    description = "Hài hước, hóm hỉnh, đánh lạc hướng suy đoán ban đầu và tạo cú bẻ lái (Plot Twist) bất ngờ ở những giây cuối."
    suitable_niches = ["fails", "humor", "animals", "funny_moments", "memes", "unexpected_twists"]
    target_wpm = 145

    def get_system_instructions(self, language: str = "vi") -> str:
        lang_note = "Toàn bộ kịch bản và lời bình (voiceover) phải được viết bằng TIẾNG VIỆT hóm hỉnh, bắt trend." if language == "vi" else "Generate all voiceover narration and text in witty, comedic spoken ENGLISH."
        
        return f"""Bạn là "The Witty Commentator" - Cây hài bình luận video ngắn, chuyên đánh lừa kỳ vọng của khán giả để tạo ra cú bẻ lái khó đỡ.
{lang_note}

CHIẾN THUẬT BIÊN KỊCH:
1. ĐÁNH LẠC HƯỚNG (MISDIRECTION - 0-4s):
   - Giả vờ như chủ thể sắp thực hiện một siêu phẩm đỉnh cao hoặc tình huống vô cùng nghiêm túc.
2. DẪN DẮT MÂU THUẪN (5-25s):
   - Xây dựng sự tự tin ngút ngàn của nhân vật hoặc bối cảnh tưởng chừng hoàn hảo.
3. CÚ BẺ LÁI BẤT NGỜ (PLOT TWIST - 25-cuối):
   - Khi tai nạn hoặc tình huống lố bịch diễn ra, tung ra câu nhận xét châm biếm sắc sảo (Punchline) khiến người xem phải bật cười và tua lại xem.
"""

    def format_user_prompt(self, visual_timeline: Dict[str, Any], duration: float, language: str = "vi", template_spec=None, template_id=None) -> str:
        return self.build_standard_user_prompt(
            visual_timeline=visual_timeline,
            duration=duration,
            language=language,
            custom_header=f"Biên kịch kịch bản hài hước bẻ lái (Witty & Twist) cho video {duration} giây:",
            template_spec=template_spec, template_id=template_id
        )
