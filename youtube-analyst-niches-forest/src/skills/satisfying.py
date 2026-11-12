from typing import Dict, Any
import json
from src.skills.base import BaseCommentarySkill

class SatisfyingNarratorSkill(BaseCommentarySkill):
    skill_id = "satisfying-narrator"
    display_name = "The Satisfying Narrator (Dẫn Dắt Thư Giãn & Trầm Trồ)"
    description = "Tôn vinh vẻ đẹp của sự tỉ mỉ, quá trình chế tác, phục chế đồ cũ, thủ công mỹ nghệ và ẩm thực với nhịp điệu êm dịu, tinh tế."
    suitable_niches = ["restoration", "woodworking", "crafts", "asmr", "cooking", "makeover", "art"]
    target_wpm = 120

    def get_system_instructions(self, language: str = "vi") -> str:
        lang_note = "Toàn bộ kịch bản và lời bình (voiceover) phải được viết bằng TIẾNG VIỆT êm dịu, tinh tế." if language == "vi" else "Generate all voiceover narration and text in soothing, articulate spoken ENGLISH."
        
        return f"""Bạn là "The Satisfying Narrator" - Người dẫn dắt video mang lại cảm giác thỏa mãn giác quan và sự trầm trồ (phong cách phục chế/thủ công mỹ nghệ đỉnh cao).
{lang_note}

CHIẾN THUẬT BIÊN KỊCH:
1. ĐỐI LẬP MỞ ĐẦU (0-4s):
   - Làm nổi bật sự cũ kỹ, thô ráp hoặc trạng thái ban đầu để gợi mở tiềm năng biến hình.
2. TÔN VINH ĐỘ CHUẨN XÁC & GIÁC QUAN (5-30s):
   - Ngôn từ giàu tính xúc giác và thị giác (mịn màng, sắc sảo, bóng bẩy, chính xác từng micromet).
   - Chừa khoảng thở cho âm thanh thực tế (SFX) của video (tiếng máy cắt, tiếng mài, tiếng giọt nước).
3. ĐIỂM CHẠM HOÀN MỸ (Cuối video):
   - Chiêm ngưỡng vẻ đẹp của tác phẩm hoàn thiện hoàn hảo.

QUY TẮC NHỊP ĐỘ:
- 115 - 125 từ/phút (~2.0 từ/giây). Lời bình ngắn gọn, thanh lịch, không nói quá nhiều để người xem tận hưởng hình ảnh.
"""

    def format_user_prompt(self, visual_timeline: Dict[str, Any], duration: float, language: str = "vi", template_spec=None, template_id=None) -> str:
        return self.build_standard_user_prompt(
            visual_timeline=visual_timeline,
            duration=duration,
            language=language,
            custom_header=f"Biên kịch kịch bản mang cảm giác thỏa mãn giác quan (Satisfying Narrator) cho video {duration} giây:",
            template_spec=template_spec, template_id=template_id
        )
