import pytest

from src.analyzer.commentary_engine import CommentaryScriptEngine
from src.models.schemas import ActionBlock, EvidenceSignals, TimeRange, VisualActionTimeline, CommentaryRequest


def make_timeline(**signals):
    return VisualActionTimeline(
        video_id="vid_test",
        duration_seconds=30.0,
        subject_matter="Test subject",
        action_timeline=[
            ActionBlock(
                time_range=TimeRange(start=0.0, end=5.0),
                visual_action="Machine starts working",
                observable_changes="Material moves",
                confidence=0.9,
                evidence_source="observed",
            )
        ],
        final_outcome="Work complete",
        evidence_signals=EvidenceSignals(**signals),
    )


@pytest.mark.parametrize(
    "signals,expected_template",
    [
        ({"has_transformation": True}, "before-after"),
        ({"has_hazard_or_breakdown": True}, "hazard-rescue"),
        ({"has_surprising_fact": True}, "shock-hook"),
        ({"has_distinct_steps": True}, "how-it-works"),
        ({"process_is_main_appeal": True}, "satisfying"),
        ({"has_person_story": True}, "story"),
        ({}, "how-it-works"),  # No clear signal -> decision-tree default.
    ],
)
def test_template_recommendation_follows_evidence_signals(signals, expected_template):
    result = CommentaryScriptEngine().recommend_template(make_timeline(**signals))
    assert result.template_id == expected_template
    assert result.source == "recommended"


def test_decision_tree_order_transformation_beats_steps():
    result = CommentaryScriptEngine().recommend_template(
        make_timeline(has_transformation=True, has_distinct_steps=True, process_is_main_appeal=True)
    )
    assert result.template_id == "before-after"


def test_manual_template_has_priority_but_warns_on_contradiction():
    timeline = make_timeline(has_distinct_steps=True)
    result = CommentaryScriptEngine().recommend_template(timeline, "before-after")
    assert result.template_id == "before-after"
    assert result.source == "manual"
    assert "Lưu ý" in result.reason


def test_manual_template_matching_signals_has_no_warning():
    timeline = make_timeline(has_transformation=True)
    result = CommentaryScriptEngine().recommend_template(timeline, "before-after")
    assert result.template_id == "before-after"
    assert "Lưu ý" not in result.reason


def test_unknown_manual_template_is_rejected():
    with pytest.raises(ValueError):
        CommentaryScriptEngine().recommend_template(make_timeline(), "not-a-template")


def test_evidence_signals_default_all_false_and_request_accepts_description():
    timeline = VisualActionTimeline(
        video_id="vid_legacy",
        duration_seconds=20.0,
        subject_matter="Legacy timeline without signals",
        final_outcome="Done",
    )
    assert timeline.evidence_signals.has_transformation is False
    assert CommentaryScriptEngine().recommend_template(timeline).template_id == "how-it-works"

    request = CommentaryRequest(
        description_subject="Brush cutter",
        description_activity="Cutting thick brush in a field",
        description_focus="Blade swap in 30 seconds",
        narrator_mode="minimal_narrator",
    )
    assert request.description_subject == "Brush cutter"
    assert request.narrator_mode == "minimal_narrator"


def test_visual_timeline_rejects_confidence_out_of_range():
    with pytest.raises(Exception):
        VisualActionTimeline(
            video_id="vid_bad",
            duration_seconds=10.0,
            subject_matter="Bad confidence",
            action_timeline=[
                ActionBlock(
                    time_range=TimeRange(start=0.0, end=5.0),
                    visual_action="Action",
                    confidence=1.5,
                )
            ],
            final_outcome="Done",
        )


def test_script_validation_flags_timeline_and_unverified_claim():
    from src.models.schemas import CapCutCommentaryInterchange, CapCutMetadata, CommentarySegment, TextOverlay

    script = CapCutCommentaryInterchange(
        video_metadata=CapCutMetadata(
            video_id="vid_test",
            title="Test",
            duration_seconds=30.0,
            skill_applied="curiosity-explainer",
            language="vi",
            total_words=10,
            average_wpm=20.0,
        ),
        segments=[
            CommentarySegment(
                beat="HOOK",
                time_range=TimeRange(start=0.0, end=5.0),
                voiceover="Máy này tăng năng suất gấp đôi cho bà con.",
                text_overlay=TextOverlay(text="TEST OVERLAY"),
            )
        ],
    )
    notes = CommentaryScriptEngine().validate_generated_script(script)
    assert any("trước thời lượng" in note for note in notes)
    assert any("claim" in note for note in notes)
