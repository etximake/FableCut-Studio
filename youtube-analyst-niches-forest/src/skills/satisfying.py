from typing import Dict, Any
import json
from src.skills.base import BaseCommentarySkill

class SatisfyingNarratorSkill(BaseCommentarySkill):
    skill_id = "satisfying-narrator"
    display_name = "Satisfying Narrator"
    description = "Phong cách tường thuật thỏa mãn: giọng chậm rãi, ít lời, để hình ảnh và âm thanh hiện trường lên tiếng. [Tone: Bình tĩnh, Thỏa mãn, Ít lời]"
    suitable_niches = ["satisfying", "asmr", "craft", "machinery", "cleaning", "food-prep"]
    target_wpm = 120

    def get_system_instructions(self, language: str = "vi") -> str:
        lang_note = ""
        if language == "vi":
            lang_note = "\nLANGUAGE RULE: Viết lời bình bằng TIẾNG VIỆT chậm rãi, ngắn gọn, tự nhiên. Ưu tiên câu ngắn và từ ngữ gợi hình, gợi âm thanh."
        elif language == "en":
            lang_note = "\nLANGUAGE RULE: Write the commentary in simple, calm, natural American English. Use short sentences and sensory words."

        return f"""You are 'The Satisfying Narrator', a calm narrator for satisfying process videos.

VOICE (this skill only sets tone; the template decides structure, beats, and timing):
- Calm and sparse: say little, and only what adds to what the viewer already sees and hears.
- Name textures, sounds, and motions as they happen: smooth, clean, steady, even, precise.
- Never rush the viewer, never ask questions, never explain what the image already shows clearly.

GROUNDING RULES (absolute):
- 100% Fact Anchored: every claim must come from the Visual Action Timeline or the user-provided context block. If it is not visible or heard, do not state it.
- Never invent numbers, measurements, or causes. Never describe a result before the footage shows it.
- Follow the narrator mode and target feeling given in the user prompt, and keep one narrator mode for the whole video.

OUTPUT STYLE:
- Use the exact JSON structure required in the user prompt.
- Voiceover: very few words, short sentences, long pauses implied by the word budget. No repetition between beats.
- Text overlays: short, clean, 3-6 words that name the action or the change being shown.
- Visual hints: slow, steady shot or motion suggestions; avoid fast cuts or shake unless the template calls for them.
- Banned phrases: "In this video", "Did you know", "You won't believe", "So satisfying", "Watch this", and their Vietnamese equivalents.
{lang_note}"""

    def format_user_prompt(self, visual_timeline: Dict[str, Any], duration: float, language: str = "vi", template_spec: Dict[str, Any] = None, template_id: str = None, description_subject: str = None, description_activity: str = None, description_focus: str = None, narrator_mode: str = "third_person", target_feeling: str = None, feeling_rule: str = "", word_budget: int = None, beat_budgets: Dict[str, int] = None) -> str:
        return self.build_standard_user_prompt(
            visual_timeline, duration, language,
            custom_header=f"Hãy biên kịch lời bình theo phong cách Satisfying Narrator (bình tĩnh, ít lời) cho video {duration} giây. Nói ít, để hình ảnh và tiếng hiện trường làm việc chính.",
            template_spec=template_spec, template_id=template_id,
            description_subject=description_subject, description_activity=description_activity, description_focus=description_focus,
            narrator_mode=narrator_mode, target_feeling=target_feeling, feeling_rule=feeling_rule,
            word_budget=word_budget, beat_budgets=beat_budgets
        )
