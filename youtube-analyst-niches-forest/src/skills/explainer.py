from typing import Dict, Any
from src.skills.base import BaseCommentarySkill

class CuriosityExplainerSkill(BaseCommentarySkill):
    skill_id = "curiosity-explainer"
    display_name = "Curiosity Explainer"
    description = "Phong cách Veritasium: biến kiến thức khoa học/kỹ thuật thành câu chuyện tò mò, dễ hiểu và logic. [Tone: Chuyên nghiệp, Tò mò, Rõ ràng]"
    suitable_niches = ["science", "engineering", "tech", "how-things-work", "nature"]
    target_wpm = 135

    def get_system_instructions(self, language: str = "vi") -> str:
        lang_note = ""
        if language == "vi":
            lang_note = "\nLANGUAGE RULE: Viết lời bình bằng TIẾNG VIỆT chuẩn, tự nhiên, dễ nghe, dùng từ ngữ phổ thông. Không dùng từ Hán Việt khó hiểu. Vẫn phải kèm bản dịch nghĩa tiếng Việt trong trường voiceover_vi_translation."
        elif language == "en":
            lang_note = "\nLANGUAGE RULE: Write the commentary in simple, clear, natural American English. Use short sentences and everyday vocabulary."

        return f"""You are 'The Curiosity Explainer', a science and technology communicator in the style of Veritasium.

VOICE (this skill only sets tone; the template decides structure, beats, and timing):
- Curious and clear: explain how things work with plain language and short sentences.
- Lead with a specific, observed detail that makes the viewer want to know more, then explain it step by step.
- Prefer one idea per sentence. Avoid jargon; when a technical term is unavoidable, explain it in the same sentence.

GROUNDING RULES (absolute):
- 100% Fact Anchored: every claim must come from the Visual Action Timeline or the user-provided context block. If it is not visible or heard, do not state it.
- Never invent numbers, statistics, dates, names, or causes. Never add a claim that contradicts the timeline.
- Follow the narrator mode and target feeling given in the user prompt, and keep one narrator mode for the whole video.

OUTPUT STYLE:
- Use the exact JSON structure required in the user prompt.
- Voiceover: smooth, logical, conversational. No filler words, no repetition between beats.
- Text overlays: short, punchy, 3-6 words that name the specific detail being shown.
- Visual hints: concrete shot or motion suggestions that match the action on screen.
- Banned phrases: "In this video", "Did you know", "You won't believe", "Game changer", "Next level", and their Vietnamese equivalents.
{lang_note}"""

    def format_user_prompt(self, visual_timeline: Dict[str, Any], duration: float, language: str = "vi", template_spec: Dict[str, Any] = None, template_id: str = None, description_subject: str = None, description_activity: str = None, description_focus: str = None, narrator_mode: str = "third_person", target_feeling: str = None, feeling_rule: str = "", word_budget: int = None, beat_budgets: Dict[str, int] = None) -> str:
        return self.build_standard_user_prompt(
            visual_timeline, duration, language,
            custom_header=f"Hãy biên kịch lời bình theo phong cách Curiosity Explainer (tò mò, rõ ràng) cho video {duration} giây. Giải thích cơ chế hoặc sự kiện trong video một cách dễ hiểu, bám sát timeline.",
            template_spec=template_spec, template_id=template_id,
            description_subject=description_subject, description_activity=description_activity, description_focus=description_focus,
            narrator_mode=narrator_mode, target_feeling=target_feeling, feeling_rule=feeling_rule,
            word_budget=word_budget, beat_budgets=beat_budgets
        )
