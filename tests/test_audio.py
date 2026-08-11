"""Tests for audio_recorder.py — audio capture logic with mocked sounddevice."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src import constants as C
from src.audio_recorder import AudioRecorder


class TestAudioRecorderInit:
    """Test construction and default parameters."""

    def test_defaults(self) -> None:
        rec = AudioRecorder()
        assert rec.is_recording is False
        assert rec._sample_rate == C.SAMPLE_RATE
        assert rec._channels == C.CHANNELS

    def test_is_recording_starts_false(self) -> None:
        rec = AudioRecorder()
        assert rec.is_recording is False


class TestStartStop:
    """Test the start/stop lifecycle with mocked sounddevice."""

    def test_start_sets_recording_flag(self) -> None:
        rec = AudioRecorder()
        mock_sd = MagicMock()
        mock_stream = MagicMock()
        mock_sd.InputStream.return_value = mock_stream

        with patch("sounddevice.InputStream", mock_sd.InputStream):
            rec._import_sounddevice = lambda: mock_sd
            rec.start()

        assert rec.is_recording is True
        mock_stream.start.assert_called_once()

    def test_stop_returns_none_when_not_recording(self) -> None:
        rec = AudioRecorder()
        assert rec.stop() is None

    def test_double_start_raises(self) -> None:
        rec = AudioRecorder()
        mock_sd = MagicMock()
        mock_stream = MagicMock()
        mock_sd.InputStream.return_value = mock_stream

        with patch("sounddevice.InputStream", mock_sd.InputStream):
            rec._import_sounddevice = lambda: mock_sd
            rec.start()

        with pytest.raises(RuntimeError, match="already in progress"):
            rec.start()

    def test_stop_returns_concatenated_audio(self) -> None:
        rec = AudioRecorder()
        mock_sd = MagicMock()
        mock_stream = MagicMock()
        mock_sd.InputStream.return_value = mock_stream

        with patch("sounddevice.InputStream", mock_sd.InputStream):
            rec._import_sounddevice = lambda: mock_sd
            rec.start()

            # Simulate two chunks of audio arriving via callback
            chunk1 = np.ones((100, 1), dtype=np.float32) * 0.5
            chunk2 = np.ones((50, 1), dtype=np.float32) * 0.8
            rec._audio_callback(chunk1, 100, None, None)
            rec._audio_callback(chunk2, 50, None, None)

            audio = rec.stop()

        assert audio is not None
        assert len(audio) == 150
        assert rec.is_recording is False
        mock_stream.stop.assert_called_once()
        mock_stream.close.assert_called_once()

    def test_stop_with_no_data_returns_none(self) -> None:
        rec = AudioRecorder()
        mock_sd = MagicMock()
        mock_stream = MagicMock()
        mock_sd.InputStream.return_value = mock_stream

        with patch("sounddevice.InputStream", mock_sd.InputStream):
            rec._import_sounddevice = lambda: mock_sd
            rec.start()
            audio = rec.stop()

        assert audio is None


class TestRMS:
    """Test the get_rms() utility method."""

    def test_zero_signal(self) -> None:
        rec = AudioRecorder()
        signal = np.zeros(1000, dtype=np.float32)
        assert rec.get_rms(signal) == 0.0

    def test_constant_signal(self) -> None:
        rec = AudioRecorder()
        signal = np.ones(100, dtype=np.float32)
        assert rec.get_rms(signal) == pytest.approx(1.0)

    def test_empty_array(self) -> None:
        rec = AudioRecorder()
        assert rec.get_rms(np.array([], dtype=np.float32)) == 0.0

    def test_none_input(self) -> None:
        rec = AudioRecorder()
        assert rec.get_rms(None) == 0.0

    def test_scaled_signal(self) -> None:
        rec = AudioRecorder()
        signal = np.full(100, 0.5, dtype=np.float32)
        assert rec.get_rms(signal) == pytest.approx(0.5)
