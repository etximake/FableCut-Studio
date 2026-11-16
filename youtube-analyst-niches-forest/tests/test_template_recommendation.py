import pytest

from src.analyzer.commentary_engine import CommentaryScriptEngine
from src.models.schemas import ActionBlock, TimeRange, VisualActionTimeline, CommentaryRequest


@pytest.mark.parametrize(("purpose", "expected"), [
    ("explain_mechanism", "how-it-works"),
    ("how_to", "how-it-works"),
    ("show_process", "satisfying"),
    ("before_after", "before-after"),
    ("troubleshoot", "hazard-rescue"),
])
def test_template_recommendation_follows_video_purpose(purpose, expected):
    result = CommentaryScriptEngine().recommend_template("curiosity-explainer", "mining", purpose)
    assert result.template_id == expected
    assert result.source == "recommended"
    assert result.reason


def test_manual_template_has_priority_over_purpose_and_skill():
    result = CommentaryScriptEngine().recommend_template(
        "agri-practitioner", "mining", "troubleshoot", "story"
    )
    assert result.template_id == "story"
    assert result.source == "manual"


def test_agriculture_process_does_not_default_to_satisfying():
    result = CommentaryScriptEngine().recommend_template(
        "satisfying-narrator", "agriculture_crops", "show_process"
    )
    assert result.template_id == "how-it-works"
    assert "cây trồng" in result.reason


def test_agricultural_machinery_process_prefers_explanation_over_satisfying():
    result = CommentaryScriptEngine().recommend_template(
        "satisfying-narrator", "agricultural_machinery", "show_process"
    )
    assert result.template_id == "how-it-works"


def test_unknown_manual_template_is_rejected():
    with pytest.raises(ValueError, match="Unknown template_id"):
        CommentaryScriptEngine().recommend_template(
            "curiosity-explainer", "other", "other", "made-up-template"
        )


def test_structured_other_values_and_evidence_defaults():
    request = CommentaryRequest(
        topic="other", topic_other="Renewable energy",
        video_purpose="other", video_purpose_other="Compare two methods",
    )
    assert request.topic_other == "Renewable energy"
    assert request.video_purpose_other == "Compare two methods"

    event = ActionBlock(
        time_range=TimeRange(start=0, end=1), visual_action="A visible action"
    )
    assert event.evidence_source == "unknown"


def test_visual_timeline_rejects_confidence_out_of_range():
    with pytest.raises(ValueError):
        ActionBlock(
            time_range=TimeRange(start=0, end=1),
            visual_action="Action", confidence=1.2,
        )


def test_script_validation_flags_timeline_and_unverified_claim():
    from src.models.schemas import CapCutCommentaryInterchange, CapCutMetadata, CommentarySegment, TextOverlay
    script = CapCutCommentaryInterchange(
        video_metadata=CapCutMetadata(
            video_id="test", title="test", duration_seconds=10,
            skill_applied="curiosity-explainer", language="vi", total_words=5, average_wpm=30,
        ),
        segments=[CommentarySegment(
            beat="HOOK", time_range=TimeRange(start=0, end=12),
            voiceover="Năng suất tăng gấp đôi", text_overlay=TextOverlay(text="Claim"),
        )],
    )
    notes = CommentaryScriptEngine().validate_generated_script(script)
    assert any("vượt thời lượng" in note for note in notes)
    assert any("claim" in note.lower() for note in notes)
