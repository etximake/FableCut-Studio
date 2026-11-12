import pytest
from unittest.mock import MagicMock, patch
from src.preprocessor.video_preprocessor import LocalVideoPreprocessor
from src.models.schemas import AudioHint

def test_audio_truncation_detection():
    preprocessor = LocalVideoPreprocessor()

    # Case 1: Silent / None
    hint_empty = preprocessor.analyze_audio_truncation(None, 45.0)
    assert hint_empty.has_speech is False
    assert hint_empty.status == "NO_MEANINGFUL_SPEECH"

    # Case 2: File doesn't exist
    hint_nonexist = preprocessor.analyze_audio_truncation("non_existent_audio.wav", 45.0)
    assert hint_nonexist.has_speech is False
    assert hint_nonexist.status == "NO_MEANINGFUL_SPEECH"

class MockSegment:
    def __init__(self, start, end, text, no_speech_prob=0.1):
        self.start = start
        self.end = end
        self.text = text
        self.no_speech_prob = no_speech_prob

def test_whisper_truncation_scenarios(tmp_path):
    preprocessor = LocalVideoPreprocessor()
    dummy_wav = tmp_path / "dummy.wav"
    dummy_wav.write_bytes(b"RIFFdummydata")

    mock_model = MagicMock()
    mock_module = MagicMock()
    mock_module.WhisperModel.return_value = mock_model

    # Scenario A: COMPLETE sentence
    mock_model.transcribe.return_value = (
        [MockSegment(1.2, 40.0, "Đây là hiện tượng nước sôi ở nhiệt độ phòng.")],
        MagicMock()
    )

    with patch.dict("sys.modules", {"faster_whisper": mock_module}):
        hint = preprocessor.analyze_audio_truncation(str(dummy_wav), 45.0)
        assert hint.has_speech is True
        assert hint.status == "COMPLETE"
        assert hint.is_reliable is True

    # Scenario B: TRUNCATED_START (bắt đầu bằng liên từ 'nhưng' ở giây 0.2)
    mock_model.transcribe.return_value = (
        [MockSegment(0.2, 35.0, "Nhưng khi áp suất giảm xuống thì nước bắt đầu sôi.")],
        MagicMock()
    )
    with patch.dict("sys.modules", {"faster_whisper": mock_module}):
        hint = preprocessor.analyze_audio_truncation(str(dummy_wav), 45.0)
        assert hint.status == "TRUNCATED_START"
        assert hint.is_reliable is False

    # Scenario C: TRUNCATED_END (câu nói dở dang sát cuối video không có dấu kết thúc)
    mock_model.transcribe.return_value = (
        [MockSegment(1.0, 44.8, "Điều này có nghĩa là mọi thứ bên trong")],
        MagicMock()
    )
    with patch.dict("sys.modules", {"faster_whisper": mock_module}):
        hint = preprocessor.analyze_audio_truncation(str(dummy_wav), 45.0)
        assert hint.status == "TRUNCATED_END"
        assert hint.is_reliable is False

    # Scenario D: TRUNCATED_BOTH
    mock_model.transcribe.return_value = (
        [MockSegment(0.1, 44.7, "và hiện tượng này sẽ khiến cho")],
        MagicMock()
    )
    with patch.dict("sys.modules", {"faster_whisper": mock_module}):
        hint = preprocessor.analyze_audio_truncation(str(dummy_wav), 45.0)
        assert hint.status == "TRUNCATED_BOTH"
        assert hint.is_reliable is False
