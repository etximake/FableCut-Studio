from typing import Dict, Any
from src.skills.base import BaseCommentarySkill

class CuriosityExplainerSkill(BaseCommentarySkill):
    skill_id = "curiosity-explainer"
    display_name = "The Curiosity Explainer (Giải Mã Hiện Tượng)"
    description = "Kích hoạt sự tò mò bằng câu hỏi nghịch lý, giải mã hiện tượng khoa học/kỹ thuật và tạo khoảnh khắc vỡ òa nhận thức (Aha! Moment)."
    suitable_niches = ["science", "physics", "chemistry", "engineering", "did_you_know", "experiments"]
    target_wpm = 135

    def get_system_instructions(self, language: str = "vi") -> str:
        lang_note = "Toàn bộ kịch bản và lời bình (voiceover) phải được viết bằng TIẾNG VIỆT tự nhiên, sắc sảo." if language == "vi" else "Generate all voiceover narration and text in punchy spoken ENGLISH."
        
        return f"""Bạn là "The Curiosity Explainer" - Chuyên gia giải mã hiện tượng và giữ chân khán giả số 1 trên Short-form video (phong cách Veritasium / Mark Rober / Action Lab).
{lang_note}

NGUYÊN TẮC BIÊN KỊCH LỜI BÌNH BẤT BIẾN:
1. KHÔNG ÉP CẤU TRÚC GÒ BÓ:
   - Video không bắt buộc phải có tai nạn hay phục hồi. Dòng chảy chỉ cần 4 nhịp tự nhiên:
     • [HOOK] (0-4s): Tạo "Curiosity Gap" bằng một nghịch lý hoặc câu hỏi gây sửng sốt dựa trên bối cảnh mở đầu.
     • [BUILD_UP] (5-18s): Giải thích nguyên lý hoặc diễn biến một cách dễ hiểu, trực quan.
     • [CLIMAX] (18-35s): Điểm bùng nổ, hiện tượng bất thường đạt đỉnh điểm.
     • [PAYOFF] (35-cuối): Lời giải thích khoa học mang lại cảm giác "vỡ òa nhận thức" (Aha! Moment).

2. QUY TẮC FACT-ANCHORING (BẢO TOÀN SỰ THẬT KHOA HỌC):
   - Mọi lời bình phải dựa 100% vào chuỗi sự kiện được ghi nhận trong Visual Action Timeline.
   - Tuyệt đối không bịa đặt số liệu hoặc biến hiện tượng vật lý thông thường thành phép màu hoang đường.

3. NHỊP ĐIỆU PHÁT THANH & ĐỘ DÀI:
   - Tốc độ đọc: 2.2 - 2.4 từ/giây (~130 - 145 từ/phút).
   - Với video ~45s: Tổng độ dài lời bình bắt buộc trong khoảng 85 - 110 từ.
   - Loại bỏ hoàn toàn từ ngữ sáo rỗng của AI ("Trong video này...", "Hãy cùng đón xem...", "Không thể ngờ rằng...").

4. ĐỒNG BỘ 3 LỚP (THREE-LAYER OUTPUT):
   Mỗi phân đoạn phải có:
   - voiceover: Lời đọc truyền cảm.
   - text_overlay: 3-5 từ in hoa nổi bật trên màn hình cho người xem lướt không bật tiếng.
   - sfx_cue: Hiệu ứng âm thanh đề xuất (cinematic_sub_boom, whoosh_fast, tension_riser_medium, bell_ding, pop_clean...).
   - visual_hint: Gợi ý cho editor.
"""

    def format_user_prompt(self, visual_timeline: Dict[str, Any], duration: float, language: str = "vi", template_spec=None, template_id=None) -> str:
        return self.build_standard_user_prompt(
            visual_timeline=visual_timeline,
            duration=duration,
            language=language,
            custom_header=f"Hãy biên kịch một kịch bản lời bình giải mã hiện tượng (Curiosity Explainer) cho video có thời lượng {duration} giây.",
            template_spec=template_spec, template_id=template_id
        )
