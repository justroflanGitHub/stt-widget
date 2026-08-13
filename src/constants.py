"""
constants.py — All application constants in a single source of truth.

No magic numbers scattered across modules. Everything lives here.
"""

from __future__ import annotations

# ── Application metadata ──────────────────────────────────────────────────────
APP_NAME: str = "VoiceToText Widget"
APP_VERSION: str = "1.0.0"

# ── Widget geometry ───────────────────────────────────────────────────────────
WIDGET_SIZE: int = 72          # square widget, px — slightly bigger
WIDGET_CORNER_RADIUS: int = 18 # rounded corner radius

# ── Colour palette ────────────────────────────────────────────────────────────
# Idle state
COLOR_IDLE_BG: str = "#2B2D31"
COLOR_IDLE_FG: str = "#5865F2"   # blurple
COLOR_IDLE_BORDER: str = "#4752C4"

# Recording state
COLOR_RECORDING_BG: str = "#3B1C1C"
COLOR_RECORDING_FG: str = "#FF0000"  # bright red — impossible to miss
COLOR_RECORDING_BORDER: str = "#FF0000"

# Processing state
COLOR_PROCESSING_BG: str = "#2B2D31"
COLOR_PROCESSING_FG: str = "#FEE75C"  # yellow
COLOR_PROCESSING_BORDER: str = "#CC9B2E"

# Done / success state
COLOR_DONE_BG: str = "#1C3B1C"
COLOR_DONE_FG: str = "#57F287"   # green
COLOR_DONE_BORDER: str = "#3BA55C"

# Loading state
COLOR_LOADING_BG: str = "#2B2D31"
COLOR_LOADING_FG: str = "#EB459E"  # pink

# ── Animation timing ──────────────────────────────────────────────────────────
PULSE_INTERVAL_MS: int = 350       # pulsing red circle interval (faster for visibility)
DONE_FLASH_DURATION_MS: int = 800  # green flash duration
TOOLTIP_DURATION_MS: int = 5000    # tooltip display duration
SPINNER_INTERVAL_MS: int = 150     # spinner frame interval

# ── Audio recording ───────────────────────────────────────────────────────────
SAMPLE_RATE: int = 16000          # Whisper expects 16 kHz mono
CHANNELS: int = 1
DTYPE: str = "float32"
CHUNK_DURATION_S: float = 0.5     # read chunk size in seconds
SILENCE_THRESHOLD: float = 0.01   # RMS below this = silence
MIN_RECORDING_DURATION_S: float = 0.3  # ignore clicks shorter than this

# ── Speech-to-Text ────────────────────────────────────────────────────────────
DEFAULT_MODEL_SIZE: str = "base"
DEFAULT_COMPUTE_TYPE: str = "int8"
DEFAULT_DEVICE: str = "cpu"
DEFAULT_LANGUAGE: str = "auto"     # "auto", "ru", or "en"
SUPPORTED_LANGUAGES: tuple[str, ...] = ("auto", "ru", "en")

# ── Interaction modes ─────────────────────────────────────────────────────────
MODE_TOGGLE: str = "toggle"
MODE_PUSH_TO_TALK: str = "push_to_talk"
SUPPORTED_MODES: tuple[str, ...] = (MODE_TOGGLE, MODE_PUSH_TO_TALK)

# ── Global hotkey ─────────────────────────────────────────────────────────────
DEFAULT_HOTKEY: str = "<ctrl>+<alt>+v"

# ── Settings file ─────────────────────────────────────────────────────────────
SETTINGS_FILENAME: str = "settings.json"

# ── Widget states (enum-like) ─────────────────────────────────────────────────
STATE_IDLE: str = "idle"
STATE_RECORDING: str = "recording"
STATE_PROCESSING: str = "processing"
STATE_DONE: str = "done"
STATE_LOADING: str = "loading"
