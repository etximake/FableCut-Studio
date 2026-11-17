"""Scene selection for videos longer than the Short limit.

Covers: proposal scoring/budget, validation, timeline rebase, FFmpeg
concat, engine scene note + forced duration, and the API wiring
(analyze proposal, generate-script with confirmed scenes, deprecated
process-video auto-apply, rewrite on the active timeline).
"""

import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import app
from src.analyzer.commentary_engine import CommentaryScriptEngine
from src.analyzer.scene_selector import (
    covers_full_video,
    describe_scenes,
    needs_scene_selection,
    propose_scenes,
    rebase_timeline,
    total_seconds,
    validate_scenes,
)
from src.models.schemas import (
    ActionBlock,
    AudioHint,
    CapCutCommentaryInterchange,
    EvidenceSignals,
    SceneRange,
    TimeRange,
    VisualActionTimeline,
)
from src.preprocessor.video_preprocessor import LocalVideoPreprocessor

client = TestClient(app)

FFMPEG = shutil.which("ffmpeg")


def make_block(start, end, action="Action", changes="", confidence=0.9, source="observed"):
    return ActionBlock(
        time_range=TimeRange(start=start, end=end),
        visual_action=action,
        observable_changes=changes,
        confidence=confidence,
        evidence_source=source,
    )


def make_timeline(duration=90.0, blocks=None):
    return VisualActionTimeline(
        video_id="vid_scenes",
        duration_seconds=duration,
        subject_matter="Brush cutter",
        initial_state="Thick brush everywhere",
        action_timeline=blocks if blocks is not None else [
            make_block(0.0, 15.0, "Machine starts", "Engine on", 0.9),
            make_block(15.0, 30.0, "Blade spins up", "Brush shakes", 0.8),
            make_block(30.0, 45.0, "Cutting thick stems", "Stems fall flat, dust rises, path appears", 0.95),
            make_block(45.0, 60.0, "Operator turns", "", 0.6, "inferred"),
            make_block(60.0, 75.0, "Second pass", "Remaining stems cut", 0.85),
            make_block(75.0, 90.0, "Clear path revealed", "Wide clear path", 0.9),
        ],
        final_outcome="A clear path",
        evidence_signals=EvidenceSignals(has_transformation=True, has_distinct_steps=True),
    )


def make_script(video_id="vid_scenes", duration=6.0):
    return CapCutCommentaryInterchange(
        video_metadata={
            "video_id": video_id,
            "title": "Test",
            "duration_seconds": duration,
            "skill_applied": "curiosity-explainer",
            "language": "en",
            "total_words": 10,
            "average_wpm": 100.0,
        },
        segments=[
            {
                "beat": "HOOK",
                "time_range": {"start": 0.0, "end": duration},
                "voiceover": "Watch this machine clear brush.",
                "voiceover_vi_translation": "Xem máy này dọn bụi.",
                "text_overlay": {"text": "CLEARS BRUSH", "position": "TOP_CENTER", "style": "HIGHLIGHT_YELLOW"},
                "sfx_cue": None,
            }
        ],
    )


# --- propose_scenes -------------------------------------------------------

def test_short_video_proposal_is_full_range():
    timeline = make_timeline(duration=44.0, blocks=[make_block(0.0, 44.0)])
    scenes = propose_scenes(timeline, "how-it-works", 60.0)
    assert scenes == [SceneRange(start=0.0, end=44.0, reason="Toàn bộ video.")]
    assert needs_scene_selection(44.0, 60.0) is False


def test_proposal_respects_budget():
    scenes = propose_scenes(make_timeline(), "how-it-works", 60.0)
    assert total_seconds(scenes) <= 60.0 + 0.01
    assert len(scenes) >= 1
    assert all(scene.end > scene.start for scene in scenes)


def test_proposal_stops_before_budget_when_remaining_blocks_are_weak():
    # Trần 60s không phải mục tiêu: chỉ 35s đầu có bằng chứng mạnh, phần còn
    # lại yếu thì gợi ý dừng ở 35s thay vì nhồi cho đủ 60s.
    blocks = [
        make_block(0.0, 20.0, "Machine clears thick brush", "Stems fall flat, dust rises, path appears", 0.95),
        make_block(20.0, 35.0, "Blade hits a thick stump", "Stump splits, chips fly", 0.9),
        make_block(35.0, 55.0, "Operator pauses", "", 0.3, "inferred"),
        make_block(55.0, 75.0, "Camera pans slowly", "", 0.3, "inferred"),
        make_block(75.0, 90.0, "Idle shot", "", 0.3, "inferred"),
    ]
    scenes = propose_scenes(make_timeline(duration=90.0, blocks=blocks), "how-it-works", 60.0)
    assert total_seconds(scenes) == 35.0
    assert scenes[0].start == 0.0 and scenes[-1].end == 35.0


def test_proposal_keeps_minimum_when_all_blocks_are_weak():
    blocks = [make_block(float(i * 15), float(i * 15 + 15), f"Vague {i}", "", 0.3, "inferred") for i in range(6)]
    scenes = propose_scenes(make_timeline(duration=90.0, blocks=blocks), "how-it-works", 60.0)
    assert total_seconds(scenes) == 15.0


def test_before_after_keeps_first_and_last_blocks():
    scenes = propose_scenes(make_timeline(), "before-after", 60.0)
    starts = [scene.start for scene in scenes]
    ends = [scene.end for scene in scenes]
    assert min(starts) == 0.0
    assert max(ends) == 90.0


def test_proposal_clips_last_block_to_fit_budget():
    timeline = make_timeline(duration=100.0, blocks=[make_block(0.0, 100.0, "One long take", "x" * 50, 0.95)])
    scenes = propose_scenes(timeline, "satisfying", 60.0)
    assert len(scenes) == 1
    assert scenes[0].start == 0.0
    assert scenes[0].end == 60.0


def test_proposal_without_blocks_falls_back_to_head():
    timeline = make_timeline(duration=120.0, blocks=[])
    scenes = propose_scenes(timeline, "how-it-works", 60.0)
    assert scenes == [SceneRange(start=0.0, end=60.0, reason="Không có timeline; lấy từ đầu video.")]


def test_adjacent_picks_merge_into_one_range():
    blocks = [make_block(float(i * 10), float(i * 10 + 10), f"Step {i}", "change", 0.95) for i in range(9)]
    scenes = propose_scenes(make_timeline(duration=90.0, blocks=blocks), "satisfying", 60.0)
    # All blocks score equally; greedy order + adjacency yields one merged run.
    assert len(scenes) == 1
    assert total_seconds(scenes) == 60.0


# --- validate_scenes / helpers --------------------------------------------

def test_validate_scenes_accepts_gaps_but_rejects_overlap_and_overrun():
    assert validate_scenes([SceneRange(start=0.0, end=20.0), SceneRange(start=50.0, end=70.0)], 90.0, 60.0) == []
    assert validate_scenes([SceneRange(start=0.0, end=30.0), SceneRange(start=25.0, end=50.0)], 90.0, 60.0)
    assert validate_scenes([SceneRange(start=0.0, end=61.0)], 90.0, 60.0)
    assert validate_scenes([SceneRange(start=80.0, end=95.0)], 90.0, 60.0)
    assert validate_scenes([], 90.0, 60.0)
    assert validate_scenes([SceneRange(start=10.0, end=10.0)], 90.0, 60.0)


def test_covers_full_video_and_describe():
    assert covers_full_video([SceneRange(start=0.0, end=90.0)], 90.0) is True
    assert covers_full_video([SceneRange(start=0.0, end=60.0)], 90.0) is False
    assert describe_scenes([SceneRange(start=1.5, end=4.0), SceneRange(start=9.0, end=12.0)]) == "1.5–4.0s, 9.0–12.0s"


# --- rebase_timeline ------------------------------------------------------

def test_rebase_shifts_clips_and_drops_blocks():
    timeline = make_timeline()
    scenes = [SceneRange(start=10.0, end=40.0), SceneRange(start=70.0, end=80.0)]
    rebased = rebase_timeline(timeline, scenes)
    assert rebased.duration_seconds == 40.0
    ranges = [(block.time_range.start, block.time_range.end) for block in rebased.action_timeline]
    # Block 0-15 clipped to 10-15 -> 0-5; 15-30 -> 5-20; 30-45 clipped to 30-40 -> 20-30;
    # 60-75 clipped to 70-75 -> 30-35; 75-90 clipped to 75-80 -> 35-40.
    assert ranges == [(0.0, 5.0), (5.0, 20.0), (20.0, 30.0), (30.0, 35.0), (35.0, 40.0)]
    # First scene does not start at 0 and last scene does not reach the end.
    assert rebased.initial_state == ""
    assert rebased.final_outcome == ""
    assert rebased.evidence_signals.has_transformation is True


def test_rebase_keeps_outcome_when_selection_covers_edges():
    timeline = make_timeline()
    rebased = rebase_timeline(timeline, [SceneRange(start=0.0, end=30.0), SceneRange(start=60.0, end=90.0)])
    assert rebased.initial_state == "Thick brush everywhere"
    assert rebased.final_outcome == "A clear path"


# --- FFmpeg concat --------------------------------------------------------

def _make_fixture_video(path, duration=12, with_audio=True):
    cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc2=duration={duration}:size=320x240:rate=30"]
    if with_audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}"]
    cmd += ["-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p"]
    if with_audio:
        cmd += ["-c:a", "aac"]
    cmd.append(str(path))
    subprocess.run(cmd, capture_output=True, check=True)


@pytest.mark.skipif(FFMPEG is None, reason="ffmpeg not available")
def test_concat_scenes_real_ffmpeg(tmp_path):
    source = tmp_path / "source.mp4"
    _make_fixture_video(source)
    preprocessor = LocalVideoPreprocessor(temp_dir=tmp_path)
    output = preprocessor.concat_scenes(str(source), [(1.0, 4.0), (8.0, 11.0)], str(tmp_path / "out.mp4"))
    info = preprocessor.get_video_info(output)
    assert 5.5 <= info["duration"] <= 6.5
    assert info["has_audio"] is True
    assert info["width"] == 320


@pytest.mark.skipif(FFMPEG is None, reason="ffmpeg not available")
def test_concat_scenes_silent_video(tmp_path):
    source = tmp_path / "silent.mp4"
    _make_fixture_video(source, with_audio=False)
    preprocessor = LocalVideoPreprocessor(temp_dir=tmp_path)
    output = preprocessor.concat_scenes(str(source), [(2.0, 5.0)], str(tmp_path / "out.mp4"))
    info = preprocessor.get_video_info(output)
    assert 2.5 <= info["duration"] <= 3.5
    assert info["has_audio"] is False


# --- engine: duration enforcement ------------------------------------------

def test_generate_commentary_clamps_segments_to_duration(monkeypatch):
    engine = CommentaryScriptEngine()

    def fake_llm(api_key, base_url, model, system_prompt, user_prompt, **kwargs):
        script = make_script(duration=30.0)
        dumped = script.model_dump()
        dumped["segments"] = [
            {
                "beat": "HOOK",
                "time_range": {"start": 0.0, "end": 20.0},
                "voiceover": "Watch this machine clear brush fast.",
                "voiceover_vi_translation": "",
                "text_overlay": {"text": "CLEARS BRUSH", "position": "TOP_CENTER", "style": "HIGHLIGHT_YELLOW"},
                "sfx_cue": None,
            },
            {
                "beat": "CLIMAX",
                "time_range": {"start": 20.0, "end": 45.0},
                "voiceover": "It keeps cutting beyond the limit.",
                "voiceover_vi_translation": "",
                "text_overlay": {"text": "KEEPS CUTTING", "position": "TOP_CENTER", "style": "HIGHLIGHT_YELLOW"},
                "sfx_cue": None,
            },
            {
                "beat": "PAYOFF",
                "time_range": {"start": 45.0, "end": 75.0},
                "voiceover": "This part should be dropped entirely.",
                "voiceover_vi_translation": "",
                "text_overlay": {"text": "DROPPED", "position": "TOP_CENTER", "style": "HIGHLIGHT_YELLOW"},
                "sfx_cue": None,
            },
        ]
        return dumped

    monkeypatch.setattr(engine, "_call_text_llm", fake_llm)
    result = engine.generate_commentary(
        make_timeline(duration=30.0, blocks=[make_block(0.0, 30.0)]),
        skill_id="curiosity-explainer",
        language="en",
        target_duration=30.0,
    )
    assert [(s.time_range.start, s.time_range.end) for s in result.segments] == [(0.0, 20.0), (20.0, 30.0)]
    assert any("đã cắt mốc kết thúc" in note for note in result.review_notes)
    assert any("đã bỏ" in note for note in result.review_notes)


def test_validate_generated_script_warns_on_word_budget_overflow():
    engine = CommentaryScriptEngine()
    script = make_script(duration=30.0)
    script.segments[0].voiceover = " ".join(["word"] * 100)
    notes = engine.validate_generated_script(script, word_budget=60)
    assert any("vượt ngân sách 60 từ" in note for note in notes)
    assert engine.validate_generated_script(script, word_budget=200) == []


# --- engine: scene note + forced duration ---------------------------------

def test_generate_commentary_uses_scene_note_and_active_duration(monkeypatch):
    engine = CommentaryScriptEngine()
    captured = {}

    def fake_llm(api_key, base_url, model, system_prompt, user_prompt, **kwargs):
        captured["user"] = user_prompt
        script = make_script(duration=999.0)
        return script.model_dump()

    monkeypatch.setattr(engine, "_call_text_llm", fake_llm)
    result = engine.generate_commentary(
        make_timeline(duration=30.0, blocks=[make_block(0.0, 30.0)]),
        skill_id="curiosity-explainer",
        language="en",
        target_duration=30.0,
        scene_note="Video gốc 90.0s; đã chọn các cảnh 10.0–40.0s (tổng 30.0s).",
    )
    assert result.video_metadata.duration_seconds == 30.0
    assert "CẢNH ĐÃ CHỌN" in captured["user"]
    assert "10.0–40.0s" in captured["user"]


# --- API ------------------------------------------------------------------

@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    from src.api import routes
    from src.storage.db import DatabaseManager

    manager = DatabaseManager(tmp_path / "scenes.db")
    monkeypatch.setattr(routes, "db", manager)
    monkeypatch.setenv("MAX_SHORT_SECONDS", "60")
    return manager


def test_analyze_returns_scene_proposal_for_long_video(tmp_path, temp_db, monkeypatch):
    from src.api import routes

    video = tmp_path / "vid_scenes.mp4"
    video.write_bytes(b"fake")
    monkeypatch.setattr(
        routes.preprocessor, "process",
        lambda path: (str(tmp_path / "sheet.jpg"), AudioHint(status="NO_MEANINGFUL_SPEECH"), 90.0),
    )
    monkeypatch.setattr(
        routes.vision_engine, "extract_visual_timeline",
        lambda **kwargs: make_timeline(),
    )

    response = client.post("/api/v1/commentary/analyze", json={"video_path": str(video)})
    assert response.status_code == 200
    data = response.json()
    assert data["needs_scene_selection"] is True
    assert data["max_scene_seconds"] == 60.0
    proposal = data["scene_proposal"]
    assert proposal
    assert sum(scene["end"] - scene["start"] for scene in proposal) <= 60.01
    stored = temp_db.get_scene_selection("vid_scenes")
    assert stored is not None
    assert stored["source_video_path"] == str(video)


def test_generate_script_applies_confirmed_scenes_without_media(tmp_path, temp_db, monkeypatch):
    from src.api import routes

    temp_db.save_visual_timeline(make_timeline())
    captured = {}

    def fake_generate(**kwargs):
        captured["timeline"] = kwargs["visual_timeline"]
        captured["scene_note"] = kwargs.get("scene_note")
        captured["duration"] = kwargs.get("target_duration")
        return make_script(duration=kwargs["visual_timeline"].duration_seconds)

    monkeypatch.setattr(routes.commentary_engine, "generate_commentary", fake_generate)
    monkeypatch.setattr(
        routes.preprocessor, "concat_scenes",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("content_only must not concat")),
    )

    response = client.post("/api/v1/commentary/generate-script", json={
        "video_id": "vid_scenes",
        "skill_id": "curiosity-explainer",
        "scenes": [{"start": 10.0, "end": 40.0}, {"start": 70.0, "end": 80.0}],
        "content_only": True,
    })
    assert response.status_code == 200
    assert captured["duration"] == 40.0
    assert captured["timeline"].duration_seconds == 40.0
    assert captured["scene_note"]
    assert [(s["start"], s["end"]) for s in response.json()["scenes_applied"]] == [
        (10.0, 40.0),
        (70.0, 80.0),
    ]
    assert response.json()["original_duration_seconds"] == 90.0


def test_generate_script_builds_media_and_exports_trimmed_clip(tmp_path, temp_db, monkeypatch):
    from src.api import routes

    source = tmp_path / "vid_scenes.mp4"
    source.write_bytes(b"fake")
    temp_db.save_visual_timeline(make_timeline())
    temp_db.save_scene_selection(
        "vid_scenes", [{"start": 0.0, "end": 90.0, "reason": ""}], 90.0,
        source_video_path=str(source),
    )
    calls = {}

    def fake_concat(video_path, scenes, output_path=None):
        calls["concat"] = (video_path, scenes)
        Path(output_path).write_bytes(b"trimmed")
        return output_path

    monkeypatch.setattr(routes.preprocessor, "concat_scenes", fake_concat)
    monkeypatch.setattr(
        routes.commentary_engine, "generate_commentary",
        lambda **kwargs: make_script(duration=kwargs["visual_timeline"].duration_seconds),
    )
    monkeypatch.setattr(
        routes.exporter, "export",
        lambda script, **kwargs: calls.setdefault("export", kwargs),
    )

    response = client.post("/api/v1/commentary/generate-script", json={
        "video_id": "vid_scenes",
        "skill_id": "curiosity-explainer",
        "scenes": [{"start": 30.0, "end": 60.0}],
        "content_only": False,
        "enable_tts": False,
    })
    assert response.status_code == 200
    assert calls["concat"][0] == str(source)
    assert calls["concat"][1] == [(30.0, 60.0)]
    assert calls["export"]["video_path"].endswith("_scenes.mp4")


def test_generate_script_rejects_over_budget_scenes(temp_db, monkeypatch):
    from src.api import routes

    temp_db.save_visual_timeline(make_timeline())
    response = client.post("/api/v1/commentary/generate-script", json={
        "video_id": "vid_scenes",
        "scenes": [{"start": 0.0, "end": 61.0}],
        "content_only": True,
    })
    assert response.status_code == 400
    assert "vượt giới hạn" in response.json()["detail"]


def test_generate_script_auto_applies_proposal_for_stale_analysis(temp_db, monkeypatch):
    """Phân tích lưu từ trước khi có chọn cảnh: không có lựa chọn nào được
    lưu, generate-script phải tự áp dụng gợi ý thay vì dùng toàn bộ video."""
    from src.api import routes

    temp_db.save_visual_timeline(make_timeline())
    assert temp_db.get_scene_selection("vid_scenes") is None
    monkeypatch.setattr(
        routes.commentary_engine, "generate_commentary",
        lambda **kwargs: make_script(duration=kwargs["visual_timeline"].duration_seconds),
    )
    monkeypatch.setattr(
        routes.preprocessor, "concat_scenes",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("content_only must not concat")),
    )
    response = client.post("/api/v1/commentary/generate-script", json={
        "video_id": "vid_scenes",
        "skill_id": "curiosity-explainer",
        "content_only": True,
    })
    assert response.status_code == 200
    body = response.json()
    assert body["capcut_json"]["video_metadata"]["duration_seconds"] <= 60.0
    assert body["capcut_json"]["video_metadata"]["duration_seconds"] > 0
    assert body["original_duration_seconds"] == 90.0
    assert sum(s["end"] - s["start"] for s in body["scenes_applied"]) <= 60.0
    assert any("tự áp dụng gợi ý chọn cảnh" in note for note in body["review_notes"])
    assert temp_db.get_scene_selection("vid_scenes") is not None


def test_generate_script_requires_source_video_for_media(temp_db, monkeypatch):
    from src.api import routes

    # video_id riêng để không dính file _original do test khác để lại trong
    # EXPORTS_DIR dùng chung của session.
    timeline = make_timeline()
    timeline.video_id = "vid_missing_source"
    temp_db.save_visual_timeline(timeline)
    temp_db.save_scene_selection(
        "vid_missing_source", [{"start": 0.0, "end": 90.0, "reason": ""}], 90.0,
        source_video_path="/nonexistent/original.mp4",
    )
    monkeypatch.setattr(
        routes.commentary_engine, "generate_commentary",
        lambda **kwargs: make_script(),
    )
    response = client.post("/api/v1/commentary/generate-script", json={
        "video_id": "vid_missing_source",
        "scenes": [{"start": 0.0, "end": 30.0}],
        "content_only": False,
        "enable_tts": False,
    })
    assert response.status_code == 400
    assert "video gốc" in response.json()["detail"]


def test_process_video_auto_applies_scene_proposal(tmp_path, temp_db, monkeypatch):
    from src.api import routes

    video = tmp_path / "vid_scenes.mp4"
    video.write_bytes(b"fake")
    monkeypatch.setattr(
        routes.preprocessor, "process",
        lambda path: (str(tmp_path / "sheet.jpg"), AudioHint(status="NO_MEANINGFUL_SPEECH"), 90.0),
    )
    monkeypatch.setattr(
        routes.vision_engine, "extract_visual_timeline",
        lambda **kwargs: make_timeline(),
    )
    calls = {}

    def fake_concat(video_path, scenes, output_path=None):
        calls["concat"] = scenes
        Path(output_path).write_bytes(b"trimmed")
        return output_path

    monkeypatch.setattr(routes.preprocessor, "concat_scenes", fake_concat)
    monkeypatch.setattr(
        routes.commentary_engine, "generate_commentary",
        lambda **kwargs: make_script(duration=kwargs["visual_timeline"].duration_seconds),
    )
    monkeypatch.setattr(routes.exporter, "export", lambda script, **kwargs: calls.setdefault("export", kwargs))
    monkeypatch.setattr(routes, "cleanup_video_temp_files", lambda **kwargs: [])

    response = client.post("/api/v1/commentary/process-video", json={
        "video_path": str(video),
        "enable_tts": False,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["visual_timeline"]["duration_seconds"] == 90.0
    assert data["scenes_applied"]
    assert sum(s["end"] - s["start"] for s in data["scenes_applied"]) <= 60.01
    assert calls["concat"]
    assert calls["export"]["video_path"].endswith("_scenes.mp4")


def test_rewrite_uses_stored_scene_selection(temp_db, monkeypatch):
    from src.api import routes

    temp_db.save_visual_timeline(make_timeline())
    temp_db.save_scene_selection(
        "vid_scenes", [{"start": 30.0, "end": 60.0, "reason": ""}], 30.0,
        source_video_path="/nonexistent/original.mp4",
    )
    captured = {}

    def fake_generate(**kwargs):
        captured["timeline"] = kwargs["visual_timeline"]
        return make_script(duration=30.0)

    monkeypatch.setattr(routes.commentary_engine, "generate_commentary", fake_generate)
    monkeypatch.setattr(routes.exporter, "export", lambda script, **kwargs: None)
    monkeypatch.setattr(routes, "cleanup_video_temp_files", lambda *args, **kwargs: [])

    response = client.post("/api/v1/commentary/rewrite", json={
        "video_id": "vid_scenes",
        "new_skill_id": "curiosity-explainer",
        "enable_tts": False,
    })
    assert response.status_code == 200
    assert captured["timeline"].duration_seconds == 30.0
    assert captured["timeline"].action_timeline[0].time_range.start == 0.0


def test_scene_selection_db_round_trip(temp_db):
    temp_db.save_scene_selection(
        "vid_x", [{"start": 1.0, "end": 5.0, "reason": "r"}], 4.0,
        source_video_path="/tmp/a.mp4", trimmed_video_path="/tmp/b.mp4",
    )
    stored = temp_db.get_scene_selection("vid_x")
    assert stored["scenes"] == [{"start": 1.0, "end": 5.0, "reason": "r"}]
    assert stored["total_seconds"] == 4.0
    assert stored["trimmed_video_path"] == "/tmp/b.mp4"
    assert temp_db.get_scene_selection("missing") is None
