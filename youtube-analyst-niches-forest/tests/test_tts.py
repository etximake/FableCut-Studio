import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from main import app
from src.tts.tts_engine import tts_engine
from src.models.schemas import CapCutCommentaryInterchange, CapCutMetadata, CommentarySegment, TimeRange, TextOverlay, SFXCue

client = TestClient(app)

def test_tts_voices_list():
    response = client.get("/api/v1/tts/voices")
    assert response.status_code == 200
    data = response.json()
    assert "voices" in data
    assert len(data["voices"]) > 0
    voice_ids = [v["id"] for v in data["voices"]]
    assert "am_adam" in voice_ids
    assert "bm_george" in voice_ids
    assert "en-US-ChristopherNeural" in voice_ids

def test_tts_synthesize_text_local(tmp_path):
    output_wav = str(tmp_path / "test_unit_tts.wav")
    path, dur = tts_engine.synthesize_text(
        text="Testing the English agricultural voiceover synthesis.",
        voice="am_adam",
        speed=1.0,
        output_path=output_wav
    )
    assert Path(path).exists()
    assert dur > 0.5
    assert Path(path).stat().st_size > 1000

def test_tts_synthesize_script(tmp_path):
    mock_script = CapCutCommentaryInterchange(
        video_metadata=CapCutMetadata(
            video_id="test_tts_video_123",
            title="Coffee Harvesting",
            duration_seconds=10.0,
            skill_applied="agri-practitioner",
            language="en",
            total_words=20,
            average_wpm=120.0
        ),
        segments=[
            CommentarySegment(
                beat="HOOK",
                time_range=TimeRange(start=0.0, end=3.5),
                voiceover="First year coffee yield showing dense clusters.",
                text_overlay=TextOverlay(text="FIRST YEAR COFFEE"),
                sfx_cue=SFXCue(suggested_sfx="cinematic_sub_boom", start_offset=0.1)
            ),
            CommentarySegment(
                beat="BUILD_UP",
                time_range=TimeRange(start=4.0, end=8.0),
                voiceover="Notice how closely packed these cherries are on each node.",
                text_overlay=TextOverlay(text="DENSE CHERRIES"),
                sfx_cue=SFXCue(suggested_sfx="whoosh_fast", start_offset=0.1)
            )
        ]
    )

    out_file, total_dur = tts_engine.synthesize_script(
        script=mock_script,
        voice="am_adam",
        speed=1.0,
        output_path=str(tmp_path / "test_tts_script_master.wav")
    )

    assert Path(out_file).exists()
    assert total_dur > 1.0
    assert mock_script.video_metadata.voiceover_audio_file is not None
    assert mock_script.video_metadata.voiceover_voice == "am_adam"

def test_tts_api_endpoints():
    from src.storage.db import db
    from src.exporter.capcut import CapCutExporter
    exporter = CapCutExporter()

    mock_script = CapCutCommentaryInterchange(
        video_metadata=CapCutMetadata(
            video_id="test_api_tts_vid",
            title="High Yield Farming",
            duration_seconds=6.0,
            skill_applied="agri-practitioner",
            language="en",
            total_words=12,
            average_wpm=120.0
        ),
        segments=[
            CommentarySegment(
                beat="HOOK",
                time_range=TimeRange(start=0.0, end=3.0),
                voiceover="Look at this incredible branch.",
                text_overlay=TextOverlay(text="INCREDIBLE BRANCH"),
                sfx_cue=SFXCue(suggested_sfx="cinematic_sub_boom", start_offset=0.1)
            )
        ]
    )
    db.save_commentary_script(mock_script)
    exporter.export(mock_script)

    # Test synthesize endpoint
    res_synth = client.post("/api/v1/tts/synthesize", json={
        "video_id": "test_api_tts_vid",
        "voice": "am_adam",
        "speed": 1.0
    })
    assert res_synth.status_code == 200
    data = res_synth.json()
    assert data["status"] == "SUCCESS"
    assert "audio_url" in data

    # Test audio playback endpoint
    res_audio = client.get(f"/api/v1/commentary/test_api_tts_vid/audio")
    assert res_audio.status_code == 200
    assert "audio" in res_audio.headers.get("content-type", "")

    # Test audio download export endpoint
    res_export = client.get("/api/v1/commentary/test_api_tts_vid/export?format=audio")
    assert res_export.status_code == 200
    assert "audio" in res_export.headers.get("content-type", "")

