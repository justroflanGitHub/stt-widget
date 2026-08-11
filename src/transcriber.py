"""
transcriber.py — faster-whisper wrapper for CPU speech-to-text.

The model loads once in a background thread; ``transcribe()`` blocks
until the model is ready, then performs inference.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

import numpy as np

from . import constants as C

logger = logging.getLogger(__name__)


class Transcriber:
    """Thin wrapper around ``faster_whisper.WhisperModel``.

    The model is loaded asynchronously.  Callers can check
    :attr:`is_loaded` or pass a *callback* to ``load_model`` to be
    notified when loading completes.

    Parameters:
        model_size: Whisper model identifier (``"tiny"``, ``"base"``, ...).
        compute_type: CTranslate2 compute type (``"int8"``, ``"float16"``, ...).
        device: Inference device (``"cpu"``, ``"cuda"``).
    """

    def __init__(
        self,
        model_size: str = C.DEFAULT_MODEL_SIZE,
        compute_type: str = C.DEFAULT_COMPUTE_TYPE,
        device: str = C.DEFAULT_DEVICE,
    ) -> None:
        self._model_size: str = model_size
        self._compute_type: str = compute_type
        self._device: str = device
        self._model = None
        self._loaded: bool = False
        self._load_lock = threading.Lock()

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def is_loaded(self) -> bool:
        """True when the model has finished loading."""
        return self._loaded

    @property
    def model_size(self) -> str:
        return self._model_size

    # ── Model loading ─────────────────────────────────────────────────────────

    def load_model(
        self,
        callback: Optional[Callable[[bool], None]] = None,
    ) -> None:
        """Load the Whisper model in a background thread.

        Args:
            callback: Called with ``True`` on success or ``False`` on failure.
        """

        def _worker() -> None:
            try:
                from faster_whisper import WhisperModel

                logger.info(
                    "Loading Whisper model '%s' (device=%s, compute=%s)…",
                    self._model_size,
                    self._device,
                    self._compute_type,
                )
                model = WhisperModel(
                    self._model_size,
                    device=self._device,
                    compute_type=self._compute_type,
                )
                with self._load_lock:
                    self._model = model
                    self._loaded = True
                logger.info("Whisper model loaded successfully.")
                if callback:
                    callback(True)
            except Exception as exc:
                logger.error("Failed to load model: %s", exc)
                if callback:
                    callback(False)

        thread = threading.Thread(target=_worker, daemon=True, name="model-loader")
        thread.start()

    # ── Transcription ─────────────────────────────────────────────────────────

    def transcribe(
        self,
        audio: np.ndarray,
        language: str = C.DEFAULT_LANGUAGE,
    ) -> str:
        """Transcribe *audio* and return the recognised text.

        Blocks until the model has finished loading.

        Args:
            audio: 1-D float32 numpy array at 16 kHz.
            language: ``"auto"``, ``"ru"``, or ``"en"``.

        Returns:
            The transcribed text, or an empty string on failure.
        """
        # Wait for model to be ready
        import time

        timeout_s = 120
        waited = 0.0
        while not self._loaded:
            if waited >= timeout_s:
                logger.error("Timed out waiting for model to load (%ds).", timeout_s)
                return ""
            time.sleep(0.2)
            waited += 0.2

        if audio is None or len(audio) == 0:
            logger.warning("Empty audio passed to transcribe().")
            return ""

        # Determine language code for faster-whisper
        lang_arg: Optional[str] = None if language == "auto" else language

        try:
            with self._load_lock:
                model = self._model

            segments, _info = model.transcribe(
                audio,
                language=lang_arg,
                beam_size=1,       # fastest for CPU real-time
                best_of=1,
                temperature=0.0,
                vad_filter=True,
            )
            # segments is a generator — consume it
            text = " ".join(seg.text.strip() for seg in segments).strip()
            logger.info("Transcription result (%d chars): %s", len(text), text[:120])
            return text
        except Exception as exc:
            logger.error("Transcription failed: %s", exc)
            return ""
