"""Batch 2: /commentary/analyze endpoint, deprecated process-video,
and template registry enrichment (narrator + feeling per template)."""

from fastapi.testclient import TestClient

from main import app
from src.models.schemas import ActionBlock, AudioHint, EvidenceSignals, TimeRange, VisualActionTimeline

client = TestClient(app)


def _fake_timeline():
    return VisualActionTimeline(
        video_id="vid_analyze",
        duration_seconds=30.0,
        subject_matter="Brush cutter clearing thick brush",
        action_timeline=[
            ActionBlock(
                time_range=TimeRange(start=0.0, end=15.0),
                visual_action="Cutter moves through thick brush",
                observable_changes="Brush falls flat",
                confidence=0.95,
                evidence_source="observed",
            )
        ],
        final_outcome="A clear path",
        evidence_signals=EvidenceSignals(has_distinct_steps=True),
    )


def test_analyze_returns_timeline_recommendation_and_narrator(tmp_path, monkeypatch):
    from src.api import routes

    video = tmp_path / "vid_analyze.mp4"
    video.write_bytes(b"fake")
    saved = []
    monkeypatch.setattr(
        routes.preprocessor, "process",
        lambda path: (str(tmp_path / "sheet.jpg"), AudioHint(status="NO_MEANINGFUL_SPEECH"), 30.0),
    )
    monkeypatch.setattr(
        routes.vision_engine, "extract_visual_timeline",
        lambda **kwargs: _fake_timeline(),
    )
    monkeypatch.setattr(routes.db, "save_visual_timeline", lambda timeline: saved.append(timeline.video_id))

    def _no_script(*args, **kwargs):
        raise AssertionError("analyze must not generate a script")

    monkeypatch.setattr(routes.commentary_engine, "generate_commentary", _no_script)

    response = client.post("/api/v1/commentary/analyze", json={"video_path": str(video)})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["video_id"] == "vid_analyze"
    assert data["template_recommendation"]["template_id"] == "how-it-works"
    assert data["template_recommendation"]["source"] == "recommended"
    assert data["narrator_mode"] == "third_person"
    assert data["target_feeling"] == "understanding"
    assert data["visual_timeline"]["evidence_signals"]["has_distinct_steps"] is True
    assert data["contact_sheet_url"] == "/api/v1/images/contact-sheet/vid_analyze"
    assert saved == ["vid_analyze", "vid_analyze"]  # Saved before and after recommendation.


def test_analyze_rejects_missing_video():
    response = client.post("/api/v1/commentary/analyze", json={})
    assert response.status_code == 400


def test_process_video_route_is_deprecated():
    from src.api.routes import router

    by_path = {route.path: route for route in router.routes if hasattr(route, "path")}
    assert by_path["/api/v1/commentary/process-video"].deprecated is True
    assert by_path["/api/v1/commentary/analyze"].deprecated in (None, False)


def test_templates_api_includes_narrator_and_feeling():
    response = client.get("/api/v1/templates")
    assert response.status_code == 200
    templates = {item["template_id"]: item for item in response.json()["templates"]}
    assert templates["shock-hook"]["narrator_mode"] == "second_person_hook"
    assert templates["shock-hook"]["target_feeling"] == "curiosity"
    assert templates["satisfying"]["narrator_mode"] == "minimal_narrator"
    assert templates["satisfying"]["target_feeling"] == "satisfaction"
    assert templates["how-it-works"]["narrator_mode"] == "third_person"
    assert templates["how-it-works"]["target_feeling"] == "understanding"
