import json
from pathlib import Path
from src.models.schemas import (
    CapCutCommentaryInterchange,
    CapCutMetadata,
    CommentarySegment,
    TimeRange,
    TextOverlay,
    SFXCue
)
from src.exporter.capcut import CapCutExporter

def test_capcut_schema_and_exporter(tmp_path):
    exporter = CapCutExporter(exports_dir=tmp_path)

    sample_script = CapCutCommentaryInterchange(
        schema_version=3,
        format="youtube-story-commentary-capcut",
        video_metadata=CapCutMetadata(
            video_id="test_vid_01",
            title="Thí nghiệm áp suất nước",
            duration_seconds=45.0,
            skill_applied="curiosity-explainer",
            language="vi",
            total_words=92,
            average_wpm=122.7,
            template_id="shock-hook"
        ),
        segments=[
            CommentarySegment(
                beat="HOOK",
                time_range=TimeRange(start=0.0, end=4.5),
                voiceover="Bạn có tin nước có thể sôi ở nhiệt độ phòng?",
                text_overlay=TextOverlay(
                    text="NƯỚC SÔI KHÔNG CẦN NHIỆT?",
                    position="TOP_CENTER",
                    style="HIGHLIGHT_YELLOW"
                ),
                sfx_cue=SFXCue(
                    suggested_sfx="cinematic_sub_boom",
                    start_offset=0.1,
                    volume=0.85
                ),
                visual_hint="Zoom vào bình chân không"
            ),
            CommentarySegment(
                beat="PAYOFF",
                time_range=TimeRange(start=4.5, end=45.0),
                voiceover="Áp suất tụt dốc đã giải phóng các phân tử nước thành hơi.",
                text_overlay=TextOverlay(
                    text="ÁP SUẤT GIẢM SÂU",
                    position="CENTER",
                    style="CLEAN_WHITE"
                ),
                sfx_cue=SFXCue(
                    suggested_sfx="bell_ding",
                    start_offset=0.1,
                    volume=0.8
                ),
                visual_hint="Bọt nước sôi trào"
            )
        ]
    )

    dummy_cs = tmp_path / "dummy_contact_sheet_3x3.jpg"
    dummy_cs.write_text("fake_image_content")

    result = exporter.export(sample_script, contact_sheet_path=str(dummy_cs))
    json_path, srt_path = result.json_path, result.srt_path
    video_dir = tmp_path / "test_vid_01"
    assert Path(json_path) == video_dir / "test_vid_01_commentary.capcut.json"
    assert Path(srt_path) == video_dir / "test_vid_01_subtitles.srt"
    assert Path(json_path).exists()
    assert Path(srt_path).exists()
    assert (video_dir / "test_vid_01_subtitles_vi.srt").exists()
    assert (video_dir / "test_vid_01_contact_sheet_3x3.jpg").exists()

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["schema_version"] == 3
    assert len(data["segments"]) == 2
    assert data["video_metadata"]["template_id"] == "shock-hook"
    assert data["video_metadata"]["contact_sheet_file"] == "test_vid_01_contact_sheet_3x3.jpg"

    with open(srt_path, "r", encoding="utf-8") as f:
        srt_content = f.read()
    assert "00:00:00,000 --> 00:00:04,500" in srt_content
    assert "Bạn có tin nước có thể sôi ở nhiệt độ phòng?" in srt_content

    with open(video_dir / "test_vid_01_subtitles_vi.srt", "r", encoding="utf-8") as f:
        srt_vi_content = f.read()
    assert "Bạn có tin nước có thể sôi ở nhiệt độ phòng?" in srt_vi_content


def test_temp_cleanup_and_contact_sheet_serving(tmp_path):
    from fastapi.testclient import TestClient
    from main import app
    from src.core.config import settings
    from src.api.routes import cleanup_video_temp_files

    client = TestClient(app)
    video_id = "upload_cleanup_test_vid"

    # Tạo các file giả lập trong TEMP_DIR
    temp_video = settings.TEMP_DIR / f"{video_id}.mp4"
    temp_cs = settings.TEMP_DIR / f"{video_id}_contact_sheet_3x3.jpg"
    temp_clean_audio = settings.TEMP_DIR / f"{video_id}_clean_audio.wav"
    temp_seg = settings.TEMP_DIR / f"{video_id}_seg_HOOK_0.0.wav"
    temp_video.write_bytes(b"fake_mp4")
    temp_cs.write_bytes(b"fake_jpg")
    temp_clean_audio.write_bytes(b"fake_wav")
    temp_seg.write_bytes(b"fake_seg")

    # Tạo 1 file bên ngoài TEMP_DIR để đảm bảo KHÔNG bị xóa nhầm
    external_video = tmp_path / "external_keep.mp4"
    external_video.write_bytes(b"keep_me")

    sample_script = CapCutCommentaryInterchange(
        schema_version=3,
        format="youtube-story-commentary-capcut",
        video_metadata=CapCutMetadata(
            video_id=video_id,
            title="Cleanup Verification",
            duration_seconds=12.0,
            skill_applied="curiosity-explainer",
            language="vi",
            total_words=20,
            average_wpm=100.0
        ),
        segments=[
            CommentarySegment(
                beat="HOOK",
                time_range=TimeRange(start=0.0, end=4.0),
                voiceover="Kiểm tra dọn file tạm.",
                text_overlay=TextOverlay(text="KIỂM TRA DỌN TẠM"),
                sfx_cue=SFXCue(suggested_sfx="bell_ding")
            )
        ]
    )

    exporter = CapCutExporter()
    export_res = exporter.export(
        sample_script,
        contact_sheet_path=str(temp_cs),
        video_path=str(temp_video)
    )

    # Chạy dọn temp cho temp_video
    removed = cleanup_video_temp_files(
        video_id=video_id,
        video_path=str(temp_video),
        contact_sheet_path=str(temp_cs),
        export_result=export_res
    )
    assert len(removed) >= 4
    assert not temp_video.exists()
    assert not temp_cs.exists()
    assert not temp_clean_audio.exists()
    assert not temp_seg.exists()

    # File đã export trong thư mục con của video phải còn nguyên
    video_dir = settings.EXPORTS_DIR / video_id
    assert (video_dir / f"{video_id}.mp4").exists()
    assert (video_dir / f"{video_id}_contact_sheet_3x3.jpg").exists()

    # Contact sheet endpoint phải vẫn phục vụ được ảnh từ EXPORTS_DIR/<video_id>/ sau khi TEMP_DIR trống
    resp_cs = client.get(f"/api/v1/images/contact-sheet/{video_id}")
    assert resp_cs.status_code == 200
    assert resp_cs.content == b"fake_jpg"

    # Kiểm tra bảo vệ file ngoài TEMP_DIR
    cleanup_video_temp_files(
        video_id=video_id,
        video_path=str(external_video),
        export_result=export_res
    )
    assert external_video.exists()
