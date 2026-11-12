from typing import Dict, List, Optional
from src.skills.base import BaseCommentarySkill
from src.skills.explainer import CuriosityExplainerSkill
from src.skills.storyteller import SuspenseStorytellerSkill
from src.skills.satisfying import SatisfyingNarratorSkill
from src.skills.witty import WittyCommentatorSkill
from src.skills.agri_practitioner import AgriPractitionerSkill

class SkillRegistry:
    """Kho quản lý và phân phối các Skill biên kịch trong hệ thống"""
    
    def __init__(self):
        self._skills: Dict[str, BaseCommentarySkill] = {}
        self.register(CuriosityExplainerSkill())
        self.register(SuspenseStorytellerSkill())
        self.register(SatisfyingNarratorSkill())
        self.register(WittyCommentatorSkill())
        self.register(AgriPractitionerSkill())

    def register(self, skill: BaseCommentarySkill):
        self._skills[skill.skill_id] = skill

    def get(self, skill_id: str) -> BaseCommentarySkill:
        if skill_id in self._skills:
            return self._skills[skill_id]
        # Fallback về mặc định
        return self._skills.get("curiosity-explainer")

    def list_skills(self) -> List[Dict[str, str]]:
        return [
            {
                "skill_id": s.skill_id,
                "display_name": s.display_name,
                "description": s.description,
                "suitable_niches": s.suitable_niches,
                "target_wpm": s.target_wpm
            }
            for s in self._skills.values()
        ]

registry = SkillRegistry()
