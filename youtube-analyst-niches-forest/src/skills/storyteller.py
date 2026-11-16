from typing import Dict, Any
import json
from src.skills.base import BaseCommentarySkill

class SuspenseStorytellerSkill(BaseCommentarySkill):
    skill_id = "suspense-storyteller"
    display_name = "Suspense Storyteller"
    description = "Phong cách kể chuyện điện ảnh: câu ngắn, dồn dập, căng thẳng bằng chi tiết quan sát được. [Tone: Điện ảnh, Căng thẳng, Dồn dập]"
    suitable_niches = ["story", "rescue", "survival", "drama", "documentary"]
    target_wpm = 140

    def get_system_instructions(self, language: str = "vi") -> str:
        lang_note = ""
        if language == "vi":
            lang_note = "\nLANGUAGE RULE: Viết lời bình bằng TIẾNG VIỆT tự nhiên, câu ngắn, dồn dập, giàu hình ảnh. Không dùng từ Hán Việt khó hiểu."
        elif language == "en":
            lang_note = "\nLANGUAGE RULE: Write the commentary in simple, natural American English with short, punchy sentences."

        return f"""You are 'The Suspense Storyteller', a cinematic narrator for short documentary-style videos.

VOICE (this skill only sets tone; the template decides structure, beats, and timing):
- Cinematic and tense: short sentences, vivid observed detail, one beat of pressure at a time.
- Build tension only from what is actually visible or audible: a sound, a movement, a change in the scene.
- Stay with one central subject. Do not invent backstory, inner thoughts, or danger the footage does not show.

GROUNDING RULES (absolute):
- 100% Fact Anchored: every claim must come from the Visual Action Timeline or the user-provided context block. If it is not visible or heard, do not state it.
- Never invent numbers, dates, names, causes, or outcomes. Never claim someone thought or felt something unless the footage plainly shows it.
- Follow the narrator mode and target feeling given in the user prompt, and keep one narrator mode for the whole video.

OUTPUT STYLE:
- Use the exact JSON structure required in the user prompt.
- Voiceover: short, punchy sentences that match the pace of the action. No filler, no repetition between beats.
- Text overlays: short, dramatic, 3-6 words that name the key detail of the moment.
- Visual hints: concrete shot or motion suggestions that match the action on screen.
- Banned phrases: "In this video", "Did you know", "You won't believe", "Nobody expected", and their Vietnamese equivalents.
{lang_note}"""

    def format_user_prompt(self, visual_timeline: Dict[str, Any], duration: float, language: str = "vi", template_spec: Dict[str, Any] = None, template_id: str = None, description_subject: str = None, description_activity: str = None, description_focus: str = None, narrator_mode: str = "third_person", target_feeling: str = None, feeling_rule: str = "", word_budget: int = None, beat_budgets: Dict[str, int] = None) -> str:
        return self.build_standard_user_prompt(
            visual_timeline, duration, language,
            custom_header=f"Hãy biên kịch lời bình theo phong cách Suspense Storyteller (điện ảnh, dồn dập) cho video {duration} giây. Kể câu chuyện trong video bằng chi tiết quan sát được, câu ngắn và căng thẳng đúng mức.",
            template_spec=template_spec, template_id=template_id,
            description_subject=description_subject, description_activity=description_activity, description_focus=description_focus,
            narrator_mode=narrator_mode, target_feeling=target_feeling, feeling_rule=feeling_rule,
            word_budget=word_budget, beat_budgets=beat_budgets
        )
