from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import json

# Chỉ các trường quan sát được mới đưa vào prompt chặng 2. Metadata gợi ý
# (selected_template_id, ...) không bao giờ được đưa vào prompt.
_TIMELINE_PROMPT_FIELDS = (
    "video_id",
    "duration_seconds",
    "subject_matter",
    "initial_state",
    "action_timeline",
    "final_outcome",
    "evidence_signals",
)

_NARRATOR_RULES = {
    "third_person": "Ngôi 3 khách quan: gọi chủ thể bằng tên/loại của nó, không dùng 'tôi', 'chúng ta', 'bạn' (tiếng Anh: không dùng 'I', 'we', 'you').",
    "second_person_hook": "Ngôi 2 CHỈ ở beat đầu tiên (tối đa 1 câu gọi trực tiếp người xem); các beat còn lại dùng ngôi 3 khách quan.",
    "minimal_narrator": "Tường thuật tối thiểu: mỗi beat tối đa 1 câu ngắn, không đặt câu hỏi, không bình luận cảm xúc thay người xem, để hình ảnh và tiếng hiện trường lên tiếng.",
}

_FEELING_LABELS = {
    "curiosity": "Thu hút / tò mò",
    "satisfaction": "Thỏa mãn",
    "understanding": "Hiểu ra",
}


class BaseCommentarySkill(ABC):
    """Lớp cơ sở cho mọi Skill biên kịch trong hệ thống.

    Skill chỉ quyết định GIỌNG ĐIỆU. Cấu trúc beat do template quyết định,
    ngôi kể và cảm giác mục tiêu là tham số riêng của prompt.
    """

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
        template_id: str = None,
        description_subject: str = None,
        description_activity: str = None,
        description_focus: str = None,
        narrator_mode: str = "third_person",
        target_feeling: str = None,
        feeling_rule: str = "",
        word_budget: int = None,
        beat_budgets: Dict[str, int] = None
    ) -> str:
        header = custom_header or f"Hãy biên kịch một kịch bản lời bình CapCut cho video có thời lượng {duration} giây."
        if word_budget is None:
            word_budget = max(8, round(duration * self.target_wpm / 60))

        template_note = ""
        beats = []
        if template_spec:
            beats = [item.get("beat") for item in template_spec.get("structure", {}).get("beats", []) if item.get("beat")]
            purpose = template_spec.get("purpose", "")
            target_total = template_spec.get("structure", {}).get("target_total_seconds") or []
            beat_lines = []
            for item in template_spec.get("structure", {}).get("beats", []):
                if not item.get("beat"):
                    continue
                note = item.get("note", "")
                target = item.get("target_seconds") or []
                timing = f" (mốc gợi ý {target[0]}–{target[1]}s)" if len(target) == 2 else ""
                beat_lines.append(f"- {item['beat']}{timing}: {note}")
            use_when = "; ".join(template_spec.get("use_when", []) or [])
            avoid_when = "; ".join(template_spec.get("avoid_when", []) or [])
            target_line = (
                f"Thời lượng khuyến nghị của template: {target_total[0]}–{target_total[1]}s; video này dài {duration}s."
                if len(target_total) == 2 else ""
            )
            template_note = (
                f"\nTEMPLATE ĐÃ CHỌN ({template_id}): {purpose}\n"
                f"Dùng đúng thứ tự beat sau:\n" + "\n".join(beat_lines) + "\n"
                f"{target_line}\n"
                f"Dùng khi: {use_when}\nTránh khi: {avoid_when}\n"
                "Viết lời bình theo đúng beat trên. Nếu 1 beat không có chất liệu trong timeline thì viết ngắn lại, không bịa chất liệu.\n"
            )

        narrator_rule = _NARRATOR_RULES.get(narrator_mode, _NARRATOR_RULES["third_person"])
        feeling_label = _FEELING_LABELS.get(target_feeling, target_feeling or "")
        narrator_block = f"\nNGÔI KỂ: {narrator_rule}\nGiữ đúng 1 ngôi kể trong toàn bộ video; bản dịch tiếng Việt giữ cùng ngôi kể.\n"
        if feeling_label:
            narrator_block += f"CẢM GIÁC MỤC TIÊU: {feeling_label}. {feeling_rule}\n"

        description_lines = []
        if description_subject:
            description_lines.append(f"- Máy/vật chính: {description_subject}")
        if description_activity:
            description_lines.append(f"- Đang làm gì, ở đâu: {description_activity}")
        if description_focus:
            description_lines.append(f"- Điểm quan trọng nhất: {description_focus}")
        description_block = ""
        if description_lines:
            description_block = (
                "\nTHÔNG TIN NGƯỜI DÙNG CUNG CẤP (CHƯA XÁC MINH TỪ HÌNH ẢNH):\n"
                + "\n".join(description_lines)
                + "\nChỉ dùng để bổ sung bối cảnh không nhìn thấy được (tên máy, địa điểm, mục đích công việc). "
                "Nếu mâu thuẫn với timeline quan sát được, ưu tiên timeline và không đưa thông tin mâu thuẫn vào lời bình.\n"
            )

        timeline_for_prompt = {k: visual_timeline.get(k) for k in _TIMELINE_PROMPT_FIELDS if k in visual_timeline}

        beat_template = ""
        if template_spec and beats:
            beat_template = ",\n".join(
                f'''    {{
      "beat": "{beat}",
      "time_range": {{ "start": <contiguous_start>, "end": <contiguous_end> }},
      "voiceover": "...",
      "voiceover_vi_translation": "...",
      "text_overlay": {{ "text": "TIT_LE_NGAN", "position": "TOP_CENTER", "style": "HIGHLIGHT_YELLOW" }},
      "sfx_cue": null,
      "visual_hint": "...",
      "edit_guidance": "Chỉ dẫn góc máy và điểm cắt dựng cho editor"
    }}''' for beat in beats
            )
        else:
            beat_template = f'''    {{
      "beat": "HOOK",
      "time_range": {{ "start": 0.0, "end": {min(4.5, duration)} }},
      "voiceover": "...", "voiceover_vi_translation": "...",
      "text_overlay": {{ "text": "TIT_LE_NGAN", "position": "TOP_CENTER", "style": "HIGHLIGHT_YELLOW" }},
      "sfx_cue": null, "visual_hint": "...",
      "edit_guidance": "Chỉ dẫn góc máy và điểm cắt dựng cho editor"
    }}'''

        budget_lines = ""
        if beat_budgets:
            budget_lines = "\nNgân sách từng beat: " + ", ".join(
                f"{beat} khoảng {words} từ" for beat, words in beat_budgets.items()
            ) + "."

        return f"""{header}
{template_note}
{narrator_block}
{description_block}
NHẬT KÝ HÀNH ĐỘNG THỰC TẾ (VISUAL ACTION TIMELINE):
{json.dumps(timeline_for_prompt, ensure_ascii=False, indent=2)}

NGÂN SÁCH TỪ: tổng khoảng {word_budget} từ cho video {duration} giây (tốc độ mục tiêu {float(self.target_wpm)} từ/phút).{budget_lines}

QUY TẮC BẮT BUỘC VỀ BIÊN KỊCH & DỰNG PHIM:
1. KHÔNG THUẬT LẠI HÌNH ẢNH HIỂN NHIÊN (NO LITERAL NARRATION):
   - Người xem tự thấy máy đang chạy, người đang làm. Lời bình PHẢI giải thích cơ chế, lý do, sự bất ngờ, áp lực vật lý hoặc giá trị thực tế thay vì tường thuật suông.
   - Beat đầu tiên (Hook/Question) phải tạo ngay sự tò mò, nghịch lý hoặc ấn tượng mạnh.
   - Beat cuối cùng (Payoff/Result) phải đúc kết chân thực dựa trên sự thật thị giác quan sát được, tuyệt đối không bịa đặt số liệu hay kết quả chưa được kiểm chứng.

2. QUY TẮC CHẶT CHẼ VỀ TEXT OVERLAY (Chữ nổi trên màn hình):
   - 'text': Là TIÊU ĐỀ HOẶC CỤM TỪ KHÓA NGẮN (2-5 từ), súc tích, viết HOA hoặc chữ cái đầu. Ví dụ: "XỚI ĐẤT KHÔ CỨNG", "LƯỠI DAO 540 RPM", "ĐẤT TƠI XỐP MỊN".
   - TUYỆT ĐỐI KHÔNG viết câu văn dài bị ngắt lửng hoặc kết thúc bằng liên từ/giới từ (như 'as', 'and', 'the', 'with', 'toward', dấu phẩy, dấu gạch ngang).
   - Text overlay KHÔNG phải phụ đề lặp lại lời bình.

3. QUY TẮC THỜI LƯỢNG & TÍNH LIỀN MẠCH:
   - Segment đầu tiên PHẢI bắt đầu ở 0.0s.
   - Segment cuối cùng PHẢI kết thúc CHÍNH XÁC ở mốc {duration:.1f}s (không được dừng sớm hơn).
   - Mọi segment liền kề nhau không có khoảng trống (start của segment sau bằng end của segment trước).

4. QUY TẮC BẮT BUỘC VỀ DỊCH NGHĨA (voiceover_vi_translation):
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
    "total_words": {word_budget},
    "average_wpm": {float(self.target_wpm)}
  }},
  "segments": [
{beat_template}
  ]
}}
"""

    def format_user_prompt(self, visual_timeline: Dict[str, Any], duration: float, language: str = "vi", template_spec: Dict[str, Any] = None, template_id: str = None, description_subject: str = None, description_activity: str = None, description_focus: str = None, narrator_mode: str = "third_person", target_feeling: str = None, feeling_rule: str = "", word_budget: int = None, beat_budgets: Dict[str, int] = None) -> str:
        """Định dạng User Prompt cho Chặng 2 mặc định dùng standard template"""
        return self.build_standard_user_prompt(visual_timeline, duration, language, template_spec=template_spec, template_id=template_id, description_subject=description_subject, description_activity=description_activity, description_focus=description_focus, narrator_mode=narrator_mode, target_feeling=target_feeling, feeling_rule=feeling_rule, word_budget=word_budget, beat_budgets=beat_budgets)
