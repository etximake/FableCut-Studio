"""Batch 1 (simplified flow): blind Vision, narrator/feeling defaults,
word budget, timeline-derived story angle, and voice-only skills."""

import pytest

from src.analyzer.commentary_engine import (
    CommentaryScriptEngine,
    compute_beat_budgets,
    compute_word_budget,
)
from src.analyzer.vision_engine import build_vision_user_prompt
from src.models.schemas import ActionBlock, AudioHint, EvidenceSignals, TimeRange, VisualActionTimeline
from src.skills.registry import registry


def make_timeline(**signals):
    return VisualActionTimeline(
        video_id="vid_flow",
        duration_seconds=30.0,
        subject_matter="Brush cutter clearing thick brush",
        action_timeline=[
            ActionBlock(
                time_range=TimeRange(start=0.0, end=10.0),
                visual_action="Operator starts the brush cutter",
                observable_changes="Blade spins up",
                confidence=0.8,
                evidence_source="observed",
            ),
            ActionBlock(
                time_range=TimeRange(start=10.0, end=25.0),
                visual_action="Cutter moves through thick brush",
                observable_changes="Brush falls flat behind the cutter",
                confidence=0.95,
                evidence_source="observed",
            ),
        ],
        final_outcome="A clear path through the brush",
        evidence_signals=EvidenceSignals(**signals),
    )


# --- H1: Vision is blind -------------------------------------------------

def test_vision_prompt_contains_no_user_labels_or_description():
    prompt = build_vision_user_prompt("vid_x", 15.0, AudioHint())
    assert "User-selected" not in prompt
    assert "topic" not in prompt.lower()
    assert "purpose" not in prompt.lower()
    assert "evidence_signals" in prompt
    for signal in (
        "has_transformation",
        "has_hazard_or_breakdown",
        "has_distinct_steps",
        "has_surprising_fact",
        "has_person_story",
        "process_is_main_appeal",
    ):
        assert signal in prompt


def test_vision_prompt_example_scales_to_real_duration():
    prompt = build_vision_user_prompt("vid_short", 15.0, AudioHint())
    # Example blocks must not assume a ~35s video.
    assert "35.0" not in prompt
    assert '"end": 15.0' in prompt


def test_vision_extract_keeps_signals_and_ignores_missing_ones(tmp_path, monkeypatch):
    from src.analyzer.vision_engine import VisionActionEngine

    image = tmp_path / "sheet.jpg"
    image.write_bytes(b"fake-jpg")
    engine = VisionActionEngine()

    def fake_call(**kwargs):
        return {
            "video_id": "vid_x",
            "duration_seconds": 15.0,
            "subject_matter": "Brush cutter",
            "action_timeline": [],
            "final_outcome": "Cleared",
            "evidence_signals": {"has_distinct_steps": True, "process_is_main_appeal": True},
        }

    monkeypatch.setattr(engine, "_call_openai_compatible_vision", fake_call)
    timeline = engine.extract_visual_timeline("vid_x", str(image), AudioHint(), 15.0)
    assert timeline.evidence_signals.has_distinct_steps is True
    assert timeline.evidence_signals.has_transformation is False


# --- H4: narrator mode + target feeling -----------------------------------

@pytest.mark.parametrize(
    "template_id,expected_mode,expected_feeling",
    [
        ("shock-hook", "second_person_hook", "curiosity"),
        ("how-it-works", "third_person", "understanding"),
        ("satisfying", "minimal_narrator", "satisfaction"),
        ("before-after", "third_person", "satisfaction"),
        ("story", "third_person", "curiosity"),
        ("hazard-rescue", "third_person", "curiosity"),
    ],
)
def test_narrator_and_feeling_defaults_per_template(template_id, expected_mode, expected_feeling):
    mode, feeling, rule = CommentaryScriptEngine().resolve_narrator_and_feeling(template_id)
    assert mode == expected_mode
    assert feeling == expected_feeling
    assert rule


def test_explicit_narrator_mode_overrides_template_default():
    mode, feeling, _ = CommentaryScriptEngine().resolve_narrator_and_feeling(
        "satisfying", narrator_mode="third_person"
    )
    assert mode == "third_person"
    # Feeling still comes from the template.
    assert feeling == "satisfaction"


# --- H5: word budget ------------------------------------------------------

def test_word_budget_scales_with_duration_and_pace():
    assert compute_word_budget(15.0, 135) == 34
    assert compute_word_budget(44.882, 135) == 101
    assert compute_word_budget(30.0, 120) == 60
    assert compute_word_budget(2.0, 135) == 8  # Floor, never zero.


def test_beat_budgets_sum_to_total_and_follow_template_timing():
    spec = {
        "structure": {
            "beats": [
                {"beat": "QUESTION", "target_seconds": [0, 3]},
                {"beat": "STEP_1", "target_seconds": [3, 15]},
                {"beat": "STEP_2", "target_seconds": [15, 27]},
                {"beat": "STEP_3_RESULT", "target_seconds": [27, 40]},
            ]
        }
    }
    budgets = compute_beat_budgets(spec, 40.0, 90)
    assert sum(budgets.values()) == 90
    assert budgets["QUESTION"] < budgets["STEP_1"]
    assert set(budgets) == {"QUESTION", "STEP_1", "STEP_2", "STEP_3_RESULT"}


# --- Story angle from timeline -------------------------------------------

def test_story_angle_comes_from_timeline_peak_block():
    angle = CommentaryScriptEngine().derive_story_angle(make_timeline())
    assert "Brush cutter" in angle
    assert "Cutter moves through thick brush" in angle  # Highest-confidence block.
    assert "clear path" in angle


def test_story_angle_empty_when_no_content():
    timeline = VisualActionTimeline(
        video_id="vid_empty", duration_seconds=10.0, subject_matter="", final_outcome=""
    )
    assert CommentaryScriptEngine().derive_story_angle(timeline) == ""


# --- H5: skills are voice-only -------------------------------------------

@pytest.mark.parametrize("skill_id", [
    "curiosity-explainer", "agri-practitioner", "satisfying-narrator",
    "suspense-storyteller", "witty-commentator",
])
def test_skill_system_prompt_has_no_fixed_beat_arc_or_word_count(skill_id):
    instructions = registry.get(skill_id).get_system_instructions(language="en")
    for forbidden in ("18-35", "18–35", "35s", "85 - 110", "85-110", "65 - 95", "65-95", "CLIMAX (18"):
        assert forbidden not in instructions


def test_user_prompt_carries_budget_narrator_description_and_template():
    skill = registry.get("curiosity-explainer")
    timeline = make_timeline(has_distinct_steps=True)
    prompt = skill.format_user_prompt(
        timeline.model_dump(),
        30.0,
        language="en",
        template_spec={
            "purpose": "Explain a mechanism",
            "structure": {
                "target_total_seconds": [30, 50],
                "beats": [
                    {"beat": "QUESTION", "note": "Ask", "target_seconds": [0, 3]},
                    {"beat": "STEP_1", "note": "First step", "target_seconds": [3, 15]},
                ],
            },
            "use_when": ["mechanism visible"],
            "avoid_when": ["no mechanism"],
        },
        template_id="how-it-works",
        description_subject="Brush cutter",
        description_activity="Clearing brush in a field",
        narrator_mode="third_person",
        target_feeling="understanding",
        feeling_rule="End with the observed result.",
        word_budget=68,
        beat_budgets={"QUESTION": 8, "STEP_1": 60},
    )
    assert "Explain a mechanism" in prompt
    assert "NGÔI KỂ" in prompt
    assert "CẢM GIÁC MỤC TIÊU" in prompt
    assert "CHƯA XÁC MINH" in prompt
    assert "Brush cutter" in prompt
    assert "68" in prompt
    assert '"total_words": 68' in prompt
    assert '"total_words": 95' not in prompt
    # Deprecated labels must not leak into the prompt via the timeline dump.
    assert "video_purpose" not in prompt
    assert "agriculture_crops" not in prompt


# --- generate_commentary end-to-end with a mocked LLM --------------------

def test_generate_commentary_uses_evidence_template_and_budget(monkeypatch):
    engine = CommentaryScriptEngine()
    captured = {}

    def fake_llm(api_key, base_url, model, system_prompt, user_prompt, **kwargs):
        captured["system"] = system_prompt
        captured["user"] = user_prompt
        return {
            "schema_version": 3,
            "format": "youtube-story-commentary-capcut",
            "video_metadata": {
                "video_id": "vid_flow",
                "title": "Brush cutter",
                "duration_seconds": 30.0,
                "skill_applied": "curiosity-explainer",
                "language": "en",
                "total_words": 0,
                "average_wpm": 0.0,
            },
            "segments": [
                {
                    "beat": "QUESTION",
                    "time_range": {"start": 0.0, "end": 3.0},
                    "voiceover": "What clears thick brush this fast?",
                    "voiceover_vi_translation": "Cái gì dọn bụi rậm nhanh thế?",
                    "text_overlay": {"text": "CLEARS THICK BRUSH", "position": "TOP_CENTER", "style": "HIGHLIGHT_YELLOW"},
                    "sfx_cue": None,
                    "visual_hint": "Close-up of blade",
                },
                {
                    "beat": "STEP_1",
                    "time_range": {"start": 3.0, "end": 15.0},
                    "voiceover": "The spinning blade cuts the stems at ground level.",
                    "voiceover_vi_translation": "Lưỡi quay cắt thân cây sát mặt đất.",
                    "text_overlay": {"text": "CUTS AT GROUND LEVEL", "position": "TOP_CENTER", "style": "HIGHLIGHT_YELLOW"},
                    "sfx_cue": None,
                    "visual_hint": "Follow the cut line",
                },
                {
                    "beat": "STEP_2",
                    "time_range": {"start": 15.0, "end": 27.0},
                    "voiceover": "The cut brush falls flat behind the machine.",
                    "voiceover_vi_translation": "Bụi đã cắt ngã rạp phía sau máy.",
                    "text_overlay": {"text": "FALLS FLAT BEHIND", "position": "TOP_CENTER", "style": "HIGHLIGHT_YELLOW"},
                    "sfx_cue": None,
                    "visual_hint": "Wide shot of cleared path",
                },
                {
                    "beat": "STEP_3_RESULT",
                    "time_range": {"start": 27.0, "end": 30.0},
                    "voiceover": "A clear path remains.",
                    "voiceover_vi_translation": "Một lối đi sạch sẽ còn lại.",
                    "text_overlay": {"text": "CLEAR PATH", "position": "TOP_CENTER", "style": "HIGHLIGHT_YELLOW"},
                    "sfx_cue": None,
                    "visual_hint": "Final wide shot",
                },
            ],
        }

    monkeypatch.setattr(engine, "_call_text_llm", fake_llm)
    result = engine.generate_commentary(
        make_timeline(has_distinct_steps=True),
        skill_id="curiosity-explainer",
        language="en",
        description_subject="Brush cutter",
    )
    assert result.video_metadata.template_id == "how-it-works"
    assert result.video_metadata.template_version == "1.1.0"
    assert [s.beat for s in result.segments] == ["QUESTION", "STEP_1", "STEP_2", "STEP_3_RESULT"]
    assert result.video_metadata.total_words > 0
    # Prompt carried the new parameters and no user labels.
    assert "GÓC KỂ TỪ TIMELINE" in captured["user"]
    assert "Brush cutter" in captured["user"]
    assert "NGÔI KỂ" in captured["user"]
    assert "video_purpose" not in captured["user"]
    assert "CHỦ ĐỀ DO NGƯỜI DÙNG" not in captured["user"]
    # Voice-only system prompt: no fixed beat arc.
    assert "18-35" not in captured["system"]
