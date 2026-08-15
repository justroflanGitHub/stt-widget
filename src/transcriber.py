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

        try:
            with self._load_lock:
                model = self._model

            # Resolve language: explicit ru/en, or detect between the two.
            if language == "auto":
                lang_arg = self._detect_ru_or_en(model, audio)
            else:
                lang_arg = language

            logger.info("Starting transcription (audio len=%d samples, lang=%s)...", len(audio), lang_arg)

            segments, _info = model.transcribe(
                audio,
                language=lang_arg,
                beam_size=5,                      # beam search: more accurate than greedy (was 1)
                best_of=1,
                temperature=0.0,
                condition_on_previous_text=False, # avoids repetition / hallucination loops
                vad_filter=True,
                # Prime the model so foreign terms are kept in their original
                # script (e.g. an English word inside Russian speech stays Latin
                # instead of being transliterated). See _initial_prompt_for().
                initial_prompt=self._initial_prompt_for(lang_arg),
            )
            # segments is a generator — consume it
            text = " ".join(seg.text.strip() for seg in segments).strip()
            logger.info("Transcription result (%d chars): %s", len(text), text[:120])
            return text
        except Exception as exc:
            logger.error("Transcription failed: %s", exc)
            return ""

    @staticmethod
    def _initial_prompt_for(lang: Optional[str]) -> Optional[str]:
        """Return an initial prompt that primes the model to keep foreign terms
        in their original script (e.g. an English word inside Russian speech).

        Without this, forcing ``language="ru"`` transliterates an English term
        like "deploy" into Cyrillic. The prompt is a natural sentence in the
        target language that already contains the foreign terms, so the model's
        vocabulary/context accepts mixed-script output.
        """
        if lang == "ru":
            return (
                "Обсуждаем разработку: нужно сделать deploy и проверить server, "
                "закрыть баги, залогировать commit и выпустить релиз."
            )
        return None

    @staticmethod
    def _detect_ru_or_en(model, audio) -> Optional[str]:
        """Return ``"ru"`` or ``"en"`` — whichever Whisper finds more likely.

        Full auto-detection across ~100 languages is unreliable on short clips
        (it often returns ``uk``/``be`` for Russian). Since the user speaks only
        Russian or English, we read the full probability distribution from
        ``detect_language`` and take the higher of the two. Returns ``None`` on
        failure so faster-whisper falls back to its own auto-detection.
        """
        try:
            _lang, _prob, all_probs = model.detect_language(audio, vad_filter=True)
            probs = dict(all_probs)
            ru = float(probs.get("ru", 0.0))
            en = float(probs.get("en", 0.0))
            chosen = "ru" if ru >= en else "en"
            logger.info("Language detection (ru/en): ru=%.2f en=%.2f -> %s", ru, en, chosen)
            return chosen
        except Exception as exc:
            logger.warning("Language detection failed (%s); falling back to full auto.", exc)
            return None
