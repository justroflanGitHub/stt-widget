"""
audio_recorder.py — Microphone capture via sounddevice.

Records mono 16 kHz float32 audio in a background thread and returns
the concatenated numpy array on stop.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

import numpy as np

from . import constants as C

logger = logging.getLogger(__name__)


class AudioRecorder:
    """Thread-safe microphone recorder using ``sounddevice``.

    Usage::

        rec = AudioRecorder()
        rec.start()          # non-blocking
        ...
        audio = rec.stop()   # returns np.ndarray[float32] or None
    """

    def __init__(
        self,
        sample_rate: int = C.SAMPLE_RATE,
        channels: int = C.CHANNELS,
        dtype: str = C.DTYPE,
        chunk_duration: float = C.CHUNK_DURATION_S,
    ) -> None:
        self._sample_rate: int = sample_rate
        self._channels: int = channels
        self._dtype: str = dtype
        self._chunk_size: int = int(sample_rate * chunk_duration)

        self._stream = None
        self._buffer: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._recording: bool = False

        # Import sounddevice lazily so tests can mock it
        self._sd = None

    @property
    def is_recording(self) -> bool:
        """Return True if currently recording."""
        return self._recording

    def _import_sounddevice(self):
        """Lazily import sounddevice to allow headless testing."""
        if self._sd is None:
            import sounddevice as sd
            self._sd = sd
        return self._sd

    def _audio_callback(
        self, indata: np.ndarray, frames: int, time_info, status
    ) -> None:
        """Called by sounddevice for each chunk of audio data."""
        if status:
            logger.debug("Audio callback status: %s", status)
        with self._lock:
            self._buffer.append(indata.copy())

    def start(self) -> None:
        """Begin recording from the default microphone.

        Raises:
            RuntimeError: if recording is already in progress.
        """
        if self._recording:
            raise RuntimeError("Recording is already in progress.")

        sd = self._import_sounddevice()

        with self._lock:
            self._buffer = []

        self._stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=self._channels,
            dtype=self._dtype,
            blocksize=self._chunk_size,
            callback=self._audio_callback,
        )
        self._stream.start()
        self._recording = True
        logger.info("Recording started (sr=%d, ch=%d).", self._sample_rate, self._channels)

    def stop(self) -> Optional[np.ndarray]:
        """Stop recording and return the captured audio.

        Returns:
            Concatenated audio as ``np.ndarray`` of shape
            ``(n_samples,)`` for mono, or ``None`` if nothing was recorded.
        """
        if not self._recording:
            return None

        self._recording = False

        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        with self._lock:
            if not self._buffer:
                logger.warning("No audio data captured.")
                return None
            audio = np.concatenate(self._buffer, axis=0)
            self._buffer = []

        # Flatten to 1-D for mono
        if self._channels == 1 and audio.ndim > 1:
            audio = audio.flatten()

        logger.info("Recording stopped, %d samples captured.", len(audio))
        return audio

    def get_rms(self, audio: np.ndarray) -> float:
        """Compute the root-mean-square of *audio* (useful for silence detection).

        Args:
            audio: 1-D numpy array of float values.

        Returns:
            RMS value as a float.
        """
        if audio is None or len(audio) == 0:
            return 0.0
        return float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))
