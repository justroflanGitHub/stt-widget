"""Tests for transcriber.py — model loading, device selection and transcription.

All tests mock ``faster_whisper`` so no model download is needed.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src import constants as C
from src.transcriber import Transcriber, resolve_device


def _wait_for(results: list) -> None:
    """Block briefly until a background-thread callback has fired."""
    import time

    for _ in range(50):
        if results:
            return
        time.sleep(0.05)


class TestTranscriberInit:
    """Test construction and default values."""

    def test_defaults(self) -> None:
        t = Transcriber()
        assert t.model_size == C.DEFAULT_MODEL_SIZE
        assert t.is_loaded is False

    def test_custom_model_size(self) -> None:
        t = Transcriber(model_size="small")
        assert t.model_size == "small"
        assert t.is_loaded is False


class TestModelLoading:
    """Test the asynchronous model loading path."""

    def test_load_model_success(self) -> None:
        """Verify that a successful import sets is_loaded = True."""
        t = Transcriber()

        mock_model = MagicMock()
        results = []

        with patch("faster_whisper.WhisperModel", return_value=mock_model):
            t.load_model(callback=lambda ok: results.append(ok))
            # Wait for background thread (synchronous in mock context)
            import time
            for _ in range(50):
                if results:
                    break
                time.sleep(0.05)

        assert t.is_loaded is True
        assert results == [True]

    def test_load_model_failure(self) -> None:
        """Verify that a failed import calls callback(False) and keeps is_loaded = False."""
        t = Transcriber()
        results = []

        with patch("faster_whisper.WhisperModel", side_effect=RuntimeError("download failed")):
            t.load_model(callback=lambda ok: results.append(ok))
            import time
            for _ in range(50):
                if results:
                    break
                time.sleep(0.05)

        assert t.is_loaded is False
        assert results == [False]


class TestDeviceSelection:
    """Test auto/CPU/CUDA device resolution and compute-type pairing."""

    def test_auto_resolves_to_cpu_without_cuda(self) -> None:
        with patch("ctranslate2.get_cuda_device_count", return_value=0):
            assert resolve_device(C.DEVICE_AUTO) == C.DEVICE_CPU

    def test_auto_resolves_to_cuda_with_gpu(self) -> None:
        with patch("ctranslate2.get_cuda_device_count", return_value=1):
            assert resolve_device(C.DEVICE_AUTO) == C.DEVICE_CUDA

    def test_explicit_devices_pass_through(self) -> None:
        assert resolve_device(C.DEVICE_CPU) == C.DEVICE_CPU
        assert resolve_device(C.DEVICE_CUDA) == C.DEVICE_CUDA

    def test_cuda_load_uses_float16(self) -> None:
        """auto + GPU present → model built with device='cuda', compute='float16'."""
        t = Transcriber(device=C.DEVICE_AUTO)
        results: list = []

        with patch("ctranslate2.get_cuda_device_count", return_value=1), \
             patch("faster_whisper.WhisperModel", return_value=MagicMock()) as wm:
            t.load_model(callback=lambda ok: results.append(ok))
            _wait_for(results)

        assert results == [True]
        assert t.effective_device == C.DEVICE_CUDA
        assert wm.call_args.kwargs["device"] == C.DEVICE_CUDA
        assert wm.call_args.kwargs["compute_type"] == C.COMPUTE_TYPE_CUDA

    def test_cpu_load_uses_int8(self) -> None:
        t = Transcriber(device=C.DEVICE_CPU)
        results: list = []

        with patch("faster_whisper.WhisperModel", return_value=MagicMock()) as wm:
            t.load_model(callback=lambda ok: results.append(ok))
            _wait_for(results)

        assert results == [True]
        assert t.effective_device == C.DEVICE_CPU
        assert wm.call_args.kwargs["device"] == C.DEVICE_CPU
        assert wm.call_args.kwargs["compute_type"] == C.COMPUTE_TYPE_CPU

    def test_cuda_failure_falls_back_to_cpu(self) -> None:
        """A CUDA load error (e.g. missing cuDNN) retries once on CPU."""
        t = Transcriber(device=C.DEVICE_CUDA)
        results: list = []

        def side_effect(size, device=None, compute_type=None):
            if device == C.DEVICE_CUDA:
                raise RuntimeError("cuDNN not found")
            return MagicMock()

        with patch("faster_whisper.WhisperModel", side_effect=side_effect) as wm:
            t.load_model(callback=lambda ok: results.append(ok))
            _wait_for(results)

        assert results == [True]
        assert t.is_loaded is True
        assert t.effective_device == C.DEVICE_CPU
        assert wm.call_count == 2


class TestTranscribe:
    """Test the transcribe() method with mocked model."""

    def test_transcribe_returns_text_on_success(self) -> None:
        t = Transcriber()
        t._loaded = True

        mock_segment = MagicMock()
        mock_segment.text = "  Hello world  "
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_segment], MagicMock())

        with patch("faster_whisper.WhisperModel", return_value=mock_model):
            # Manually set the model
            t._model = mock_model

            audio = np.zeros(C.SAMPLE_RATE, dtype=np.float32)
            text = t.transcribe(audio, language="en")

        assert "Hello world" in text

    def test_transcribe_empty_audio_returns_empty(self) -> None:
        t = Transcriber()
        t._loaded = True
        result = t.transcribe(np.array([], dtype=np.float32))
        assert result == ""

    def test_transcribe_none_audio_returns_empty(self) -> None:
        t = Transcriber()
        t._loaded = True
        result = t.transcribe(None)
        assert result == ""

    def test_transcribe_passes_language_auto_as_none(self) -> None:
        """When language='auto', faster-whisper expects ``language=None``."""
        t = Transcriber()
        t._loaded = True

        mock_segment = MagicMock()
        mock_segment.text = "Привет"
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_segment], MagicMock())
        t._model = mock_model

        audio = np.zeros(C.SAMPLE_RATE, dtype=np.float32)
        t.transcribe(audio, language="auto")

        call_kwargs = mock_model.transcribe.call_args
        assert call_kwargs.kwargs.get("language") is None or call_kwargs[1].get("language") is None

    def test_transcribe_passes_explicit_language(self) -> None:
        t = Transcriber()
        t._loaded = True

        mock_segment = MagicMock()
        mock_segment.text = "Test"
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_segment], MagicMock())
        t._model = mock_model

        audio = np.zeros(C.SAMPLE_RATE, dtype=np.float32)
        t.transcribe(audio, language="ru")

        call_args = mock_model.transcribe.call_args
        lang_kwarg = call_args.kwargs.get("language")
        assert lang_kwarg == "ru"
