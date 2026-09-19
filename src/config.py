"""
config.py — Settings load/save with JSON backend.

Single source of truth for configuration management.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from . import constants as C

logger = logging.getLogger(__name__)


def _default_settings() -> dict[str, Any]:
    """Return the default settings dictionary."""
    return {
        "mode": C.MODE_TOGGLE,
        "language": C.DEFAULT_LANGUAGE,
        "model_size": C.DEFAULT_MODEL_SIZE,
        "device": C.DEFAULT_DEVICE,
        "widget_position": [100, 100],
        "global_hotkey": C.DEFAULT_HOTKEY,
    }


def get_settings_path() -> Path:
    """Return the absolute path to ``settings.json``.

    When frozen by PyInstaller, store settings next to the executable — a
    stable, user-writable location — rather than inside the bundle's
    ``_internal`` directory (which is an internal, version-specific folder
    and in onefile builds is a wiped temp dir). In development, use the
    project root (the parent of ``src/``).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / C.SETTINGS_FILENAME
    src_dir = Path(__file__).resolve().parent
    project_root = src_dir.parent
    return project_root / C.SETTINGS_FILENAME


def load_settings() -> dict[str, Any]:
    """Load settings from JSON file, falling back to defaults.

    Returns:
        A dictionary with keys: mode, language, model_size, device,
        widget_position, global_hotkey.
    """
    path = get_settings_path()
    defaults = _default_settings()

    if not path.exists():
        logger.info("Settings file not found at %s; using defaults.", path)
        return defaults

    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read settings (%s); using defaults.", exc)
        return defaults

    # Merge: start with defaults, override with file values
    merged = {**defaults, **data}
    # Validate known keys
    if merged["mode"] not in C.SUPPORTED_MODES:
        logger.warning("Unknown mode %r; falling back to default.", merged["mode"])
        merged["mode"] = C.MODE_TOGGLE

    if merged["language"] not in C.SUPPORTED_LANGUAGES:
        logger.warning("Unknown language %r; falling back to default.", merged["language"])
        merged["language"] = C.DEFAULT_LANGUAGE

    if merged["device"] not in C.SUPPORTED_DEVICES:
        logger.warning("Unknown device %r; falling back to default.", merged["device"])
        merged["device"] = C.DEFAULT_DEVICE

    return merged


def save_settings(settings: dict[str, Any]) -> None:
    """Persist settings to JSON file.

    Args:
        settings: Dictionary with configuration values.
    """
    path = get_settings_path()
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(settings, fh, indent=4, ensure_ascii=False)
        logger.info("Settings saved to %s", path)
    except OSError as exc:
        logger.error("Failed to save settings: %s", exc)
