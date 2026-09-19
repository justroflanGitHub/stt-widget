"""
transcriber.py — faster-whisper wrapper for speech-to-text (CPU or CUDA GPU).

The model loads once in a background thread; ``transcribe()`` blocks
until the model is ready, then performs inference.
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
import threading
import time
from typing import Callable, Optional

import numpy as np

from . import constants as C

logger = logging.getLogger(__name__)


def _cublas_loadable() -> bool:
    """Return True when cuBLAS can be loaded for this process.

    ctranslate2.dll loads ``cublas64_12.dll`` lazily with a plain
    ``LoadLibrary`` at the first GPU matmul — the same lookup this probe
    performs. When it fails, the model still *loads* on CUDA (weights are
    copied with plain memcpys), but the first real inference either raises or,
    worse, deadlocks inside ctranslate2 while the widget sits in Processing
    forever. Checking up front turns that into a clean "CUDA unavailable".

    Two locations are tried:

    * by name — i.e. the standard Windows search order, whose first entry is
      the executable's directory (where build.spec puts the DLLs);
    * the pip-installed ``nvidia-cublas-cu12`` wheel, whose ``bin`` directory
      is never on the search path by itself. Loading by absolute path still
      helps: the loader keys loaded modules by base name, so ctranslate2's
      later by-name ``LoadLibrary`` reuses the module preloaded here.
    """
    if sys.platform != "win32":
        return True  # Linux wheels link cuBLAS through rpath — nothing to probe.

    candidates: list[str] = []
    try:
        import sysconfig

        pip_bin = os.path.join(
            sysconfig.get_paths()["purelib"], "nvidia", "cublas", "bin"
        )
        if os.path.isdir(pip_bin):
            for name in os.listdir(pip_bin):
                if name.lower() == "cublas64_12.dll":
                    candidates.append(os.path.join(pip_bin, name))
                    break
    except Exception:  # sysconfig quirks in frozen builds — the by-name
        pass           # lookup below is the one that matters there anyway.
    candidates.append("cublas64_12.dll")  # also pulls in cublasLt64_12.dll

    for candidate in candidates:
        try:
            ctypes.CDLL(candidate)
            return True
        except OSError:
            continue
    return False


def cuda_available() -> bool:
    """Return True when CTranslate2 can actually run on the GPU.

    A visible CUDA device is not enough: the driver only provides
    ``nvcuda.dll``, while inference additionally needs the CUDA 12 runtime
    libraries (cuBLAS). Both are checked so ``auto`` never resolves to a CUDA
    that deadlocks at the first transcription.
    """
    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() <= 0:
            return False
        if not _cublas_loadable():
            logger.warning(
                "CUDA device found but cublas64_12.dll is not loadable — "
                "GPU disabled. Place cublas64_12.dll + cublasLt64_12.dll next "
                "to the executable (or install the CUDA 12 runtime / "
                "nvidia-cublas-cu12)."
            )
            return False
        return True
    except Exception as exc:
        logger.warning("CUDA detection failed (%s); treating as unavailable.", exc)
        return False


def resolve_device(device: str) -> str:
    """Map a configured device (``auto``/``cpu``/``cuda``) to a concrete one.

    ``auto`` becomes ``cuda`` when a GPU is visible, otherwise ``cpu``.
    Explicit ``cpu``/``cuda`` are passed through unchanged — a requested CUDA
    load that fails at runtime falls back to CPU inside ``load_model``.
    """
    if device == C.DEVICE_AUTO:
        return C.DEVICE_CUDA if cuda_available() else C.DEVICE_CPU
    return device


class Transcriber:
    """Thin wrapper around ``faster_whisper.WhisperModel``.

    The model is loaded asynchronously.  Callers can check
    :attr:`is_loaded` or pass a *callback* to ``load_model`` to be
    notified when loading completes.

    Parameters:
        model_size: Whisper model identifier (``"tiny"``, ``"base"``, ...).
        device: Inference device (``"auto"``, ``"cpu"``, ``"cuda"``).
        compute_type: CTranslate2 compute type; when ``None`` it is chosen
            automatically from the resolved device (``float16`` on CUDA,
            ``int8`` on CPU).

    Attributes:
        effective_device: The device the model actually loaded on (set after
            a successful ``load_model``; useful when ``auto`` resolved to CUDA
            or a CUDA load fell back to CPU).
    """

    def __init__(
        self,
        model_size: str = C.DEFAULT_MODEL_SIZE,
        device: str = C.DEFAULT_DEVICE,
        compute_type: Optional[str] = None,
    ) -> None:
        self._model_size: str = model_size
        self._device: str = device
        self._compute_type: Optional[str] = compute_type
        self._effective_device: Optional[str] = None
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

    @property
    def device(self) -> str:
        """The configured device (``auto``/``cpu``/``cuda``) before resolution."""
        return self._device

    @property
    def effective_device(self) -> Optional[str]:
        """The concrete device (``cpu``/``cuda``) the model loaded on."""
        return self._effective_device

    # ── Model loading ─────────────────────────────────────────────────────────

    def load_model(
        self,
        callback: Optional[Callable[[bool], None]] = None,
    ) -> None:
        """Load the Whisper model in a background thread.

        ``auto`` devices are resolved to CUDA/CPU first. If a CUDA load then
        fails (e.g. missing cuDNN runtime), the worker retries once on CPU so
        the app keeps working.

        Args:
            callback: Called with ``True`` on success or ``False`` on failure.
        """

        def _load_one(whisper_cls, device: str) -> object:
            """Build the model for a concrete *device* with the matching compute type."""
            compute = self._compute_type or C.compute_type_for_device(device)
            logger.info(
                "Loading Whisper model '%s' (device=%s, compute=%s)…",
                self._model_size,
                device,
                compute,
            )
            return whisper_cls(
                self._model_size,
                device=device,
                compute_type=compute,
            )

        def _worker() -> None:
            try:
                from faster_whisper import WhisperModel

                resolved = resolve_device(self._device)
                try:
                    model = _load_one(WhisperModel, resolved)
                    if resolved == C.DEVICE_CUDA and not self._warm_up_cuda(model):
                        raise RuntimeError("CUDA warm-up inference failed (see log)")
                except Exception as cuda_exc:
                    if resolved != C.DEVICE_CUDA:
                        raise
                    logger.warning(
                        "CUDA load failed (%s); falling back to CPU.", cuda_exc
                    )
                    resolved = C.DEVICE_CPU
                    model = _load_one(WhisperModel, resolved)

                with self._load_lock:
                    self._model = model
                    self._loaded = True
                    self._effective_device = resolved
                logger.info("Whisper model loaded successfully on '%s'.", resolved)
                if callback:
                    callback(True)
            except Exception as exc:
                logger.error("Failed to load model: %s", exc)
                if callback:
                    callback(False)

        thread = threading.Thread(target=_worker, daemon=True, name="model-loader")
        thread.start()

    @staticmethod
    def _warm_up_cuda(model) -> bool:
        """Run a tiny real inference so lazy CUDA loads happen *now*, not mid-use.

        Loading the model only memcpy's weights to the GPU; cuBLAS and friends
        are first touched by an actual forward pass. If that first pass fails
        or deadlocks (broken/missing CUDA runtime), this is where we want to
        find out — before reporting the model as ready. The call runs in its
        own daemon thread with a timeout because the failure mode is not
        always an exception: a half-initialised CUDA stack can hang inside
        ctranslate2 forever, and a hung warm-up thread is disposable.
        """
        outcome: dict = {}

        def _run() -> None:
            try:
                t0 = time.monotonic()
                segments, _info = model.transcribe(
                    np.zeros(C.SAMPLE_RATE, dtype=np.float32),  # 1 s of silence
                    language="en",
                    vad_filter=False,
                    beam_size=1,
                )
                for _ in segments:  # generator — force the forward pass
                    pass
                outcome["ok"] = True
                outcome["ms"] = (time.monotonic() - t0) * 1000.0
            except Exception as exc:
                outcome["ok"] = False
                outcome["error"] = str(exc)

        probe = threading.Thread(target=_run, daemon=True, name="cuda-warmup")
        probe.start()
        probe.join(C.CUDA_WARMUP_TIMEOUT_S)
        if outcome.get("ok"):
            logger.info("CUDA warm-up inference OK in %.0f ms.", outcome["ms"])
            return True
        if probe.is_alive():
            logger.error(
                "CUDA warm-up did not finish within %ss — GPU inference "
                "deadlocked; falling back to CPU.",
                C.CUDA_WARMUP_TIMEOUT_S,
            )
        else:
            logger.error("CUDA warm-up failed: %s", outcome.get("error"))
        return False

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
