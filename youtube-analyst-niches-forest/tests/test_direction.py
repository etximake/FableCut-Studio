"""Bản Định hướng (Direction): LLM viết kế hoạch, kịch bản tuân theo.

Covers: engine generate_direction (LLM + fallback), binding prompt section,
validation of script against the direction, DB round-trip, and API wiring
(/direction endpoint + generate-script resolution order: request > stored >
auto-generate).
"""

import pytest
from fastapi.testclient import TestClient

from main import app
from src.analyzer.commentary_engine import CommentaryScriptEngine
from src.models.schemas import (
    ActionBlock,
    CapCutCommentaryInterchange,
    Direction,
    DirectionBeat,
    TimeRange,
    VisualActionTimeline,
)

client = TestClient(app)


def make_block(start, end, action="Action", changes="", confidence=0.9, source="observed"):
    return ActionBlock(
        time_range=TimeRange(start=start, end=end),
        visual_action=action,
        observable_changes=changes,
        confidence=confidence,
        evidence_source=source,
    )


def make_timeline(duration=30.0, blocks=None):
    return VisualActionTimeline(
        video_id="vid_dir",
        duration_seconds=duration,
        subject_matter="Brush cutter",
        initial_state="Thick brush everywhere",
        action_timeline=blocks if blocks is not None else [
            make_block(0.0, 10.0, "Machine starts", "Engine on", 0.9),
            make_block(10.0, 20.0, "Cutter bites thick brush", "Brush falls", 0.95),
            make_block(20.0, 30.0, "Clear path remains", "Ground visible", 0.9),
        ],
        final_outcome="Clear path",
    )


def make_direction(**overrides):
    data = {
        "video_id": "vid_dir",
        "template_id": "how-it-works",
        "promise": "This brush cutter clears thick brush in three steps.",
        "key_moment_start": 10.0,
        "key_moment_end": 20.0,
        "key_moment_reason": "Cutter bites thick brush",
        "beats": [
            {"beat": "QUESTION", "purpose": "State the brush problem.", "source_start": 0.0, "source_end": 4.0,
             "key_evidence": "Thick brush everywhere", "overlay_text": "THICK BRUSH", "sfx_cue": None, "pace": "normal"},
            {"beat": "STEP_1", "purpose": "Machine starts.", "source_start": 4.0, "source_end": 13.0,
             "key_evidence": "Engine on", "overlay_text": "STEP 1", "sfx_cue": "engine_start", "pace": "normal"},
            {"beat": "STEP_2", "purpose": "Cutter bites the brush.", "source_start": 13.0, "source_end": 22.0,
             "key_evidence": "Brush falls", "overlay_text": "", "sfx_cue": None, "pace": "slow"},
            {"beat": "STEP_3_RESULT", "purpose": "Clear path remains.", "source_start": 22.0, "source_end": 30.0,
             "key_evidence": "Ground visible", "overlay_text": "CLEAR PATH", "sfx_cue": None, "pace": "normal"},
        ],
        "sound_note": "Machine sound bed throughout.",
        "narrator_mode": "third_person",
        "target_feeling": "understanding",
        "source": "llm",
    }
    data.update(overrides)
    return Direction(**data)


def make_script(direction, hook="Watch this brush cutter clear the path.", sfx_on_step1=True, overlay_on_step1=True):
    segments = []
    for beat in direction.beats:
        segments.append({
            "beat": beat.beat,
            "time_range": {"start": beat.source_start, "end": beat.source_end},
            "voiceover": hook if beat.beat == "QUESTION" else f"Line for {beat.beat}.",
            "voiceover_vi_translation": "",
            "text_overlay": {
                "text": beat.overlay_text if (beat.beat != "STEP_1" or overlay_on_step1) else "",
                "position": "TOP_CENTER", "style": "HIGHLIGHT_YELLOW",
            },
            "sfx_cue": {"suggested_sfx": "engine_start"} if (beat.beat == "STEP_1" and sfx_on_step1) else None,
        })
    return CapCutCommentaryInterchange(
        video_metadata={
            "video_id": "vid_dir", "title": "Test", "duration_seconds": 30.0,
            "skill_applied": "curiosity-explainer", "language": "en",
            "total_words": 10, "average_wpm": 100.0,
        },
        segments=segments,
    )


# --- engine: generate_direction -------------------------------------------

def test_generate_direction_parses_llm_json_and_sanitizes(monkeypatch):
    engine = CommentaryScriptEngine()

    def fake_llm(api_key, base_url, model, system_prompt, user_prompt, **kwargs):
        assert "Direction" in system_prompt or "director" in system_prompt.lower()
        return {
            "promise": "A brush cutter clears thick brush fast.",
            "key_moment_start": 10.0,
            "key_moment_end": 999.0,
            "key_moment_reason": "Cutter bites brush",
            "beats": [
                {"beat": "QUESTION", "purpose": "Problem.", "source_start": 0.0, "source_end": 4.0,
                 "key_evidence": "Thick brush", "overlay_text": "THICK BRUSH", "sfx_cue": None, "pace": "normal"},
                {"beat": "NOPE", "purpose": "Unknown beat.", "source_start": 4.0, "source_end": 9.0},
                {"beat": "STEP_1", "purpose": "Start.", "source_start": 4.0, "source_end": 13.0,
                 "key_evidence": "Engine on", "overlay_text": "", "sfx_cue": None, "pace": "brisk"},
            ],
            "sound_note": "Machine bed.",
        }

    monkeypatch.setattr(engine, "_call_text_llm", fake_llm)
    direction = engine.generate_direction(make_timeline(), template_id="how-it-works")
    assert direction.source == "llm"
    assert direction.template_id == "how-it-works"
    assert direction.promise == "A brush cutter clears thick brush fast."
    assert [b.beat for b in direction.beats] == ["QUESTION", "STEP_1"]
    assert direction.key_moment_end == 30.0
    assert direction.beats[1].pace == "brisk"


def test_generate_direction_fallback_on_llm_error(monkeypatch):
    engine = CommentaryScriptEngine()

    def broken_llm(*args, **kwargs):
        raise RuntimeError("no llm")

    monkeypatch.setattr(engine, "_call_text_llm", broken_llm)
    direction = engine.generate_direction(make_timeline(), template_id="how-it-works")
    assert direction.source == "fallback"
    assert direction.beats
    assert direction.beats[0].source_start == 0.0
    assert direction.beats[-1].source_end == 30.0
    # Khoảnh khắc chính là block tin cậy cao nhất.
    assert direction.key_moment_start == 10.0
    assert direction.key_moment_end == 20.0
    assert direction.promise


def test_generate_direction_fallback_empty_timeline(monkeypatch):
    engine = CommentaryScriptEngine()
    monkeypatch.setattr(engine, "_call_text_llm", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no llm")))
    timeline = make_timeline(blocks=[])
    direction = engine.generate_direction(timeline, template_id="how-it-works")
    assert direction.source == "fallback"
    assert direction.beats
    assert direction.promise == "Chủ thể: Brush cutter."


def test_generate_commentary_includes_direction_prompt(monkeypatch):
    engine = CommentaryScriptEngine()
    captured = {}

    def fake_llm(api_key, base_url, model, system_prompt, user_prompt, **kwargs):
        captured["user"] = user_prompt
        return make_script(make_direction()).model_dump()

    monkeypatch.setattr(engine, "_call_text_llm", fake_llm)
    engine.generate_commentary(
        make_timeline(), skill_id="curiosity-explainer", language="en",
        template_id="how-it-works", direction=make_direction(),
    )
    assert "BẢN ĐỊNH HƯỚNG ĐÃ DUYỆT" in captured["user"]
    assert "clears thick brush in three steps" in captured["user"]
    assert "Cutter bites the brush" in captured["user"]


# --- engine: validate_script_against_direction -----------------------------

def test_validate_direction_match_has_no_notes():
    engine = CommentaryScriptEngine()
    notes = engine.validate_script_against_direction(make_script(make_direction()), make_direction())
    assert notes == []


def test_validate_direction_reports_mismatches():
    engine = CommentaryScriptEngine()
    direction = make_direction()
    script = make_script(direction, hook="Something completely different happens here.",
                         sfx_on_step1=False, overlay_on_step1=False)
    # Đổi thứ tự 2 beat đầu của phần thân: beat vẫn đủ nhưng sai vị trí.
    script.segments[1].beat, script.segments[2].beat = script.segments[2].beat, script.segments[1].beat
    notes = engine.validate_script_against_direction(script, direction)
    joined = " ".join(notes)
    assert "STEP_1" in joined
    assert "câu hứa hẹn" in joined
    assert "SFX" in joined
    assert "overlay" in joined


def test_validate_direction_flags_unplanned_sfx():
    engine = CommentaryScriptEngine()
    direction = make_direction()
    script = make_script(direction)
    script.segments[2].sfx_cue = {"suggested_sfx": "whoosh_fast"}
    notes = engine.validate_script_against_direction(script, direction)
    assert any("ngoài kế hoạch" in note for note in notes)


def test_validate_direction_empty_plan_is_quiet():
    engine = CommentaryScriptEngine()
    direction = make_direction(beats=[])
    assert engine.validate_script_against_direction(make_script(make_direction()), direction) == []


# --- DB round-trip ----------------------------------------------------------

@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    from src.api import routes
    from src.storage.db import DatabaseManager

    manager = DatabaseManager(tmp_path / "directions.db")
    monkeypatch.setattr(routes, "db", manager)
    return manager


def test_direction_db_roundtrip(temp_db):
    direction = make_direction()
    temp_db.save_direction("vid_dir", direction.model_dump())
    stored = temp_db.get_direction("vid_dir")
    assert stored is not None
    assert Direction(**stored).promise == direction.promise
    assert temp_db.get_direction("missing") is None


# --- API --------------------------------------------------------------------

def test_direction_endpoint_creates_and_saves(temp_db, monkeypatch):
    from src.api import routes

    temp_db.save_visual_timeline(make_timeline())
    expected = make_direction()
    monkeypatch.setattr(routes.commentary_engine, "generate_direction", lambda **kwargs: expected)

    response = client.post("/api/v1/commentary/direction", json={"video_id": "vid_dir"})
    assert response.status_code == 200
    data = response.json()
    assert data["direction"]["promise"] == expected.promise
    assert data["template_recommendation"]["template_id"] == "how-it-works"
    assert Direction(**temp_db.get_direction("vid_dir")).promise == expected.promise


def test_direction_endpoint_404_without_analysis(temp_db):
    response = client.post("/api/v1/commentary/direction", json={"video_id": "nope"})
    assert response.status_code == 404


def test_generate_script_uses_request_direction(temp_db, monkeypatch):
    from src.api import routes

    temp_db.save_visual_timeline(make_timeline())
    captured = {}

    def fake_generate(**kwargs):
        captured["direction"] = kwargs.get("direction")
        return make_script(make_direction())

    monkeypatch.setattr(routes.commentary_engine, "generate_commentary", fake_generate)
    monkeypatch.setattr(
        routes.commentary_engine, "generate_direction",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not auto-generate")),
    )
    direction = make_direction()
    direction.promise = "User edited promise about brush."

    response = client.post("/api/v1/commentary/generate-script", json={
        "video_id": "vid_dir",
        "skill_id": "curiosity-explainer",
        "direction": direction.model_dump(),
        "content_only": True,
    })
    assert response.status_code == 200
    assert captured["direction"].promise == "User edited promise about brush."
    assert captured["direction"].source == "user"
    assert response.json()["direction"]["source"] == "user"
    assert Direction(**temp_db.get_direction("vid_dir")).source == "user"


def test_generate_script_auto_generates_direction_when_missing(temp_db, monkeypatch):
    from src.api import routes

    temp_db.save_visual_timeline(make_timeline())
    expected = make_direction()
    calls = []
    monkeypatch.setattr(routes.commentary_engine, "generate_direction", lambda **kwargs: (calls.append(1), expected)[1])
    monkeypatch.setattr(routes.commentary_engine, "generate_commentary", lambda **kwargs: make_script(expected))

    response = client.post("/api/v1/commentary/generate-script", json={
        "video_id": "vid_dir",
        "skill_id": "curiosity-explainer",
        "content_only": True,
    })
    assert response.status_code == 200
    assert len(calls) == 1
    assert response.json()["direction"]["promise"] == expected.promise
    assert any("tự sinh" in note for note in response.json()["review_notes"])
    assert temp_db.get_direction("vid_dir") is not None


def test_generate_script_uses_stored_direction(temp_db, monkeypatch):
    from src.api import routes

    temp_db.save_visual_timeline(make_timeline())
    stored = make_direction(promise="Stored promise about brush.")
    temp_db.save_direction("vid_dir", stored.model_dump())
    captured = {}
    monkeypatch.setattr(
        routes.commentary_engine, "generate_direction",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("must use stored direction")),
    )

    def fake_generate(**kwargs):
        captured["direction"] = kwargs.get("direction")
        return make_script(stored)

    monkeypatch.setattr(routes.commentary_engine, "generate_commentary", fake_generate)

    response = client.post("/api/v1/commentary/generate-script", json={
        "video_id": "vid_dir",
        "skill_id": "curiosity-explainer",
        "content_only": True,
    })
    assert response.status_code == 200
    assert captured["direction"].promise == "Stored promise about brush."
    assert response.json()["direction"]["promise"] == "Stored promise about brush."
