import pytest
from src.skills.registry import registry

def test_skill_registry_contents():
    skills = registry.list_skills()
    skill_ids = [s["skill_id"] for s in skills]
    
    assert "curiosity-explainer" in skill_ids
    assert "suspense-storyteller" in skill_ids
    assert "satisfying-narrator" in skill_ids
    assert "witty-commentator" in skill_ids
    assert "agri-practitioner" in skill_ids
    assert len(skill_ids) == 5

def test_skill_prompt_generation():
    explainer = registry.get("curiosity-explainer")
    system_inst = explainer.get_system_instructions(language="vi")
    assert "Curiosity Explainer" in system_inst
    assert "TIẾNG VIỆT" in system_inst

    agri = registry.get("agri-practitioner")
    agri_inst = agri.get_system_instructions(language="vi")
    assert "Agri-Practitioner" in agri_inst
    assert "nhà nông" in agri_inst.lower() or "canh tác" in agri_inst.lower()

    mock_timeline = {
        "video_id": "test_123",
        "subject_matter": "Cà phê cao sản năm đầu",
        "action_timeline": []
    }
    user_prompt = agri.format_user_prompt(mock_timeline, 30.0, language="vi")
    assert "youtube-story-commentary-capcut" in user_prompt
    assert "30.0" in user_prompt
    assert "agri-practitioner" in user_prompt
