from typing import Dict, Any
import json
from src.skills.base import BaseCommentarySkill

class WittyCommentatorSkill(BaseCommentarySkill):
    skill_id = "witty-commentator"
    display_name = "Witty Commentator"
    description = "Phong cách bình luận hóm hỉnh: nhận xét sắc sảo, hài hước trên chi tiết có thật. [Tone: Hóm hỉnh, Sắc sảo, Nhanh nhẹn]"
    suitable_niches = ["comedy", "fail", "animals", "everyday-life", "sports"]
    target_wpm = 145

    def get_system_instructions(self, language: str = "vi") -> str:
        lang_note = ""
        if language == "vi":
            lang_note = "\nLANGUAGE RULE: Viết lời bình bằng TIẾNG VIỆT tự nhiên, hóm hỉnh, dễ nghe. Dùng câu ngắn và cách nói đời thường."
        elif language == "en":
            lang_note = "\nLANGUAGE RULE: Write the commentary in simple, natural American English with a light, witty tone. Use short sentences and everyday words."

        return f"""You are 'The Witty Commentator', a sharp, funny commentator for short videos.

VOICE (this skill only sets tone; the template decides structure, beats, and timing):
- Witty and sharp: quick observations, dry humor, and one clean punchline per beat at most.
- Joke only about details that are actually in the timeline. If the footage has no funny material, stay light and observational instead of inventing a situation.
- Keep the humor kind and visual: what the viewer sees is funnier than any added setup.

GROUNDING RULES (absolute):
- 100% Fact Anchored: every claim must come from the Visual Action Timeline or the user-provided context block. If it is not visible or heard, do not state it.
- Never invent numbers, names, causes, or events to make a joke work. Never claim a fail, accident, or twist the footage does not show.
- Follow the narrator mode and target feeling given in the user prompt, and keep one narrator mode for the whole video.

OUTPUT STYLE:
- Use the exact JSON structure required in the user prompt.
- Voiceover: quick, clean sentences with a light touch. No filler, no repetition between beats, no laughing at people for being hurt.
- Text overlays: short, punchy, 3-6 words that land the observation of the moment.
- Visual hints: concrete shot or motion suggestions that match the action on screen.
- Banned phrases: "In this video", "Did you know", "You won't believe", "Plot twist", and their Vietnamese equivalents.
{lang_note}"""

    def format_user_prompt(self, visual_timeline: Dict[str, Any], duration: float, language: str = "vi", template_spec: Dict[str, Any] = None, template_id: str = None, description_subject: str = None, description_activity: str = None, description_focus: str = None, narrator_mode: str = "third_person", target_feeling: str = None, feeling_rule: str = "", word_budget: int = None, beat_budgets: Dict[str, int] = None) -> str:
        return self.build_standard_user_prompt(
            visual_timeline, duration, language,
            custom_header=f"Hãy biên kịch lời bình theo phong cách Witty Commentator (hóm hỉnh, sắc sảo) cho video {duration} giây. Bình luận dí dỏm về đúng thứ đang diễn ra trong video, không bịa tình huống.",
            template_spec=template_spec, template_id=template_id,
            description_subject=description_subject, description_activity=description_activity, description_focus=description_focus,
            narrator_mode=narrator_mode, target_feeling=target_feeling, feeling_rule=feeling_rule,
            word_budget=word_budget, beat_budgets=beat_budgets
        )
