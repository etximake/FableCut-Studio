import pytest
from src.analyzer.scene_selector import build_edit_plan
from src.analyzer.commentary_engine import CommentaryScriptEngine
from src.models.schemas import (
    ActionBlock,
    CapCutCommentaryInterchange,
    CapCutMetadata,
    CommentarySegment,
    SceneRange,
    TextOverlay,
    TimeRange,
    VisualActionTimeline,
)


def make_timeline(duration: float = 30.0, blocks=None) -> VisualActionTimeline:
    if blocks is None:
        blocks = [
            ActionBlock(
                time_range=TimeRange(start=0.0, end=10.0),
                visual_action="Máy bắt đầu chạy lưỡi dao",
                confidence=0.9,
                evidence_source="observed",
                observable_changes="Đất bắt đầu bị cày xới",
            ),
            ActionBlock(
                time_range=TimeRange(start=10.0, end=20.0),
                visual_action="Lưỡi xới quay mạnh ở tốc độ 540 rpm",
                confidence=0.95,
                evidence_source="observed",
                observable_changes="Đất vỡ mịn bắn ra hai bên",
            ),
            ActionBlock(
                time_range=TimeRange(start=20.0, end=duration),
                visual_action="Bề mặt đất sau xới phẳng phiu",
                confidence=0.88,
                evidence_source="observed",
                observable_changes="Đường xới thẳng tắp hoàn tất",
            ),
        ]
    return VisualActionTimeline(
        video_id="test_vid",
        duration_seconds=duration,
        subject_matter="Máy xới đất",
        action_timeline=blocks,
        final_outcome="Đất tơi xốp sau xới",
    )


def test_build_edit_plan_short_video():
    timeline = make_timeline(duration=28.7)
    plan = build_edit_plan(timeline, scenes=[], template_id="how-it-works")
    assert plan.target_duration_seconds == 28.7
    assert plan.original_duration_seconds == 28.7
    assert len(plan.cuts) == 3
    assert plan.cuts[0].role == "hook"
    assert plan.cuts[0].source_start == 0.0
    assert plan.cuts[0].output_start == 0.0
    assert plan.cuts[-1].role == "payoff"
    assert plan.cuts[-1].source_end == 28.7
    assert plan.cuts[-1].output_end == 28.7
    assert "tối ưu" in plan.trimmed_sections_note or "trọn vẹn" in plan.trimmed_sections_note


def test_build_edit_plan_long_video_with_selected_scenes():
    timeline = make_timeline(duration=120.0)
    scenes = [
        SceneRange(start=10.0, end=25.0, reason="Mở đầu cơ chế"),
        SceneRange(start=60.0, end=80.0, reason="Cao trào xới đất"),
    ]
    plan = build_edit_plan(timeline, scenes=scenes, template_id="how-it-works")
    assert plan.target_duration_seconds == 35.0
    assert plan.original_duration_seconds == 120.0
    assert len(plan.cuts) == 2

    cut1 = plan.cuts[0]
    assert cut1.source_start == 10.0
    assert cut1.source_end == 25.0
    assert cut1.output_start == 0.0
    assert cut1.output_end == 15.0
    assert cut1.duration == 15.0

    cut2 = plan.cuts[1]
    assert cut2.source_start == 60.0
    assert cut2.source_end == 80.0
    assert cut2.output_start == 15.0
    assert cut2.output_end == 35.0
    assert cut2.duration == 20.0
    assert cut2.suggested_transition in ("dissolve", "whip_pan")
    assert "85.0s" in plan.trimmed_sections_note


def test_map_to_source_range():
    engine = CommentaryScriptEngine()
    # 1. No scenes -> 1:1 mapping
    tr1 = engine._map_to_source_range(5.0, 15.0, scenes=[])
    assert tr1.start == 5.0 and tr1.end == 15.0

    # 2. With scenes: [10, 25] (dur 15) and [60, 80] (dur 20)
    scenes = [
        SceneRange(start=10.0, end=25.0),
        SceneRange(start=60.0, end=80.0),
    ]
    # The range spans a splice; map to the largest contiguous source portion.
    tr2 = engine._map_to_source_range(2.0, 17.0, scenes=scenes)
    assert tr2.start == 12.0 and tr2.end == 25.0

    # Slice within second scene (output 17.0 to 27.0 -> offset 2.0 to 12.0 -> source 62.0 to 72.0)
    tr3 = engine._map_to_source_range(17.0, 27.0, scenes=scenes)
    assert tr3.start == 62.0 and tr3.end == 72.0


def test_enforce_script_duration_extends_last_segment():
    engine = CommentaryScriptEngine()
    script = CapCutCommentaryInterchange(
        video_metadata=CapCutMetadata(
            video_id="v1",
            title="Kubota Test",
            duration_seconds=28.7,
            skill_applied="curiosity-explainer",
            language="vi",
            total_words=40,
            average_wpm=120,
        ),
        segments=[
            CommentarySegment(
                beat="HOOK",
                time_range=TimeRange(start=0.0, end=10.0),
                voiceover="Câu hook ấn tượng",
                text_overlay=TextOverlay(text="MÁY XỚI ĐẤT", style="HIGHLIGHT_YELLOW"),
            ),
            CommentarySegment(
                beat="PAYOFF",
                time_range=TimeRange(start=10.0, end=24.47),  # dừng sớm 4.23s
                voiceover="Kết quả hoàn hảo",
                text_overlay=TextOverlay(text="ĐẤT TƠI XỐP", style="HIGHLIGHT_YELLOW"),
            ),
        ],
    )
    notes = engine.enforce_script_duration(script, duration=28.7)
    assert script.segments[-1].time_range.end == 28.7
    assert any("kéo dài" in note for note in notes)


def test_enforce_script_duration_closes_initial_and_internal_gaps():
    engine = CommentaryScriptEngine()
    script = CapCutCommentaryInterchange(
        video_metadata=CapCutMetadata(
            video_id="v1", title="Gap test", duration_seconds=20.0,
            skill_applied="curiosity-explainer", language="vi",
            total_words=10, average_wpm=100,
        ),
        segments=[
            CommentarySegment(
                beat="HOOK", time_range=TimeRange(start=1.0, end=8.0),
                voiceover="Hook mở đầu", text_overlay=TextOverlay(text="MỞ ĐẦU", style="HIGHLIGHT_YELLOW"),
            ),
            CommentarySegment(
                beat="PAYOFF", time_range=TimeRange(start=9.0, end=18.0),
                voiceover="Kết quả cuối", text_overlay=TextOverlay(text="KẾT QUẢ", style="HIGHLIGHT_YELLOW"),
            ),
        ],
    )
    notes = engine.enforce_script_duration(script, 20.0)
    assert script.segments[0].time_range.start == 0.0
    assert script.segments[1].time_range.start == script.segments[0].time_range.end
    assert script.segments[-1].time_range.end == 20.0
    assert any("Beat đầu" in note for note in notes)


def test_validate_generated_script_catches_bad_overlays_and_narration():
    engine = CommentaryScriptEngine()
    script = CapCutCommentaryInterchange(
        video_metadata=CapCutMetadata(
            video_id="v1",
            title="Test",
            duration_seconds=20.0,
            skill_applied="curiosity-explainer",
            language="vi",
            total_words=30,
            average_wpm=120,
        ),
        segments=[
            CommentarySegment(
                beat="HOOK",
                time_range=TimeRange(start=0.0, end=10.0),
                voiceover="In this video we can see the tractor working.",  # literal narration
                text_overlay=TextOverlay(text="The blades spin as", style="HIGHLIGHT_YELLOW"),  # ends with 'as'
            ),
            CommentarySegment(
                beat="STEP_1",
                time_range=TimeRange(start=10.0, end=20.0),
                voiceover="Động cơ truyền lực qua trục PTO của máy kéo.",
                text_overlay=TextOverlay(
                    text="Đây là một dòng text overlay quá dài không hợp lệ cho màn hình dọc",  # > 7 words
                    style="HIGHLIGHT_YELLOW",
                ),
            ),
        ],
    )
    notes = engine.validate_generated_script(script)
    assert any("ngắt lửng" in note or "câu cụt" in note for note in notes)
    assert any("quá dài" in note for note in notes)
    assert any("tường thuật hình thức" in note for note in notes)
