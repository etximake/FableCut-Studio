from fastapi.testclient import TestClient
import pytest
from main import app

client = TestClient(app)

def test_api_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "AI Video Commentary Studio" in response.text

def test_api_info():
    response = client.get("/api/info")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert "endpoints" in data

def test_list_skills_api():
    response = client.get("/api/v1/skills")
    assert response.status_code == 200
    data = response.json()
    assert "skills" in data
    assert len(data["skills"]) == 5
    skill_ids = [s["skill_id"] for s in data["skills"]]
    assert "agri-practitioner" in skill_ids

def test_templates_api_returns_registry_entries():
    response = client.get("/api/v1/templates")
    assert response.status_code == 200
    ids = {item["template_id"] for item in response.json()["templates"]}
    assert {"how-it-works", "satisfying", "before-after", "hazard-rescue"} <= ids


def test_export_request_rejects_path_like_video_ids():
    from pydantic import ValidationError
    from src.models.schemas import ExportRequest

    with pytest.raises(ValidationError):
        ExportRequest(video_id="../private", format="capcut_json")

def test_sfx_catalog_api():
    response = client.get("/api/v1/sfx/catalog")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) > 0

def test_ai_status_api():
    response = client.get("/api/v1/ai/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ONLINE"
    assert "primary_provider" in data

def test_ai_model_test_text_success(monkeypatch):
    from src.api import routes
    from src.core.config import settings

    values = {"OPENAI_API_KEY": "test-key", "DEFAULT_TEXT_MODEL": "test-text-model"}
    monkeypatch.setattr(settings, "get_var", lambda key, default="": values.get(key, default))

    class FakeCompletions:
        def create(self, **kwargs):
            assert kwargs["model"] == "test-text-model"
            return type("Response", (), {"choices": [type("Choice", (), {"message": type("Message", (), {"content": '{"ok":true}'})()})()]})()

    monkeypatch.setattr(routes, "OpenAI", lambda **kwargs: type("Client", (), {"chat": type("Chat", (), {"completions": FakeCompletions()})()})())
    response = client.post("/api/v1/ai/test/text")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["model"] == "test-text-model"

def test_ai_model_test_missing_key(monkeypatch):
    from src.api import routes
    from src.core.config import settings

    monkeypatch.setattr(settings, "get_var", lambda key, default="": "" if key == "OPENAI_API_KEY" else default)
    response = client.post("/api/v1/ai/test/vision")
    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert "OPENAI_API_KEY" in response.json()["message"]

def test_static_files_served():
    resp_css = client.get("/static/style.css")
    assert resp_css.status_code == 200
    assert "--bg-main" in resp_css.text

    resp_js = client.get("/static/app.js")
    assert resp_js.status_code == 200
    assert "Commentary Studio" in resp_js.text

def test_sfx_audio_endpoint():
    response = client.get("/api/v1/sfx/audio/sfx_impact_sub_boom")
    assert response.status_code == 200
    assert response.headers["content-type"] in ["audio/wav", "audio/x-wav"]

def test_canonical_sfx_catalog_ids_are_resolvable():
    catalog = client.get("/api/v1/sfx/catalog").json()["items"]
    ids = {item["sfx_id"] for item in catalog}
    assert {"soft_chime", "cinematic_sub_boom", "whoosh_fast", "bell_ding", "tension_riser_medium"} <= ids
    for sfx_id in ("soft_chime", "cinematic_sub_boom", "whoosh_fast", "bell_ding", "tension_riser_medium"):
        assert client.get(f"/api/v1/sfx/audio/{sfx_id}").status_code == 200

def test_upload_video_endpoint():
    file_bytes = b"fake video mp4 stream content"
    response = client.post(
        "/api/v1/commentary/upload-video",
        files={"file": ("sample_clip.mp4", file_bytes, "video/mp4")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert "upload_sample_clip" in data["video_id"]
    assert "video_path" in data

def test_download_export_endpoints(tmp_path):
    from src.models.schemas import CapCutCommentaryInterchange, CapCutMetadata, CommentarySegment, TimeRange, SFXCue, TextOverlay
    from src.exporter.capcut import CapCutExporter
    from src.core.config import settings

    video_id = "test_export_video"
    dummy_script = CapCutCommentaryInterchange(
        video_metadata=CapCutMetadata(
            video_id=video_id,
            title="Test Export Video",
            duration_seconds=30.0,
            skill_applied="curiosity-explainer",
            language="vi",
            total_words=45,
            average_wpm=90.0
        ),
        segments=[
            CommentarySegment(
                beat="HOOK",
                time_range=TimeRange(start=0.0, end=5.0),
                voiceover="Đây là câu hook mở đầu.",
                text_overlay=TextOverlay(text="CÂU HOOK MỞ ĐẦU"),
                sfx_cue=SFXCue(suggested_sfx="sfx_impact_sub_boom", volume=0.8),
                visual_hint="Cận cảnh"
            )
        ]
    )

    exporter = CapCutExporter()
    exporter.export(dummy_script)

    # Test download JSON
    resp_json = client.get(f"/api/v1/commentary/{video_id}/export?format=capcut_json")
    assert resp_json.status_code == 200
    assert "application/json" in resp_json.headers["content-type"]
    assert "Đây là câu hook" in resp_json.text

    # Test download SRT
    resp_srt = client.get(f"/api/v1/commentary/{video_id}/export?format=srt")
    assert resp_srt.status_code == 200
    assert "00:00:00,000 --> 00:00:05,000" in resp_srt.text

    # Test download SRT Tiếng Việt
    resp_srt_vi = client.get(f"/api/v1/commentary/{video_id}/export?format=srt_vi")
    assert resp_srt_vi.status_code == 200
    assert "00:00:00,000 --> 00:00:05,000" in resp_srt_vi.text

    # Test download Bundle ZIP
    resp_zip = client.get(f"/api/v1/commentary/{video_id}/export?format=bundle_zip")
    assert resp_zip.status_code == 200
    assert "application/zip" in resp_zip.headers["content-type"]
    assert len(resp_zip.content) > 0
