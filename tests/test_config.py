"""Tests for config.py — settings load/save/migration logic."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src import constants as C
from src.config import load_settings, save_settings, _default_settings


class TestDefaultSettings:
    """Verify the default settings dictionary is well-formed."""

    def test_defaults_contain_required_keys(self) -> None:
        defaults = _default_settings()
        assert "mode" in defaults
        assert "language" in defaults
        assert "model_size" in defaults
        assert "device" in defaults
        assert "widget_position" in defaults
        assert "global_hotkey" in defaults

    def test_default_mode_is_valid(self) -> None:
        defaults = _default_settings()
        assert defaults["mode"] in C.SUPPORTED_MODES

    def test_default_language_is_valid(self) -> None:
        defaults = _default_settings()
        assert defaults["language"] in C.SUPPORTED_LANGUAGES

    def test_default_device_is_valid(self) -> None:
        defaults = _default_settings()
        assert defaults["device"] in C.SUPPORTED_DEVICES

    def test_widget_position_is_pair_of_ints(self) -> None:
        defaults = _default_settings()
        pos = defaults["widget_position"]
        assert len(pos) == 2
        assert all(isinstance(v, int) for v in pos)


class TestLoadSettings:
    """Test loading settings with and without a settings.json present."""

    def test_load_returns_defaults_when_no_file(self, tmp_path: Path) -> None:
        with patch("src.config.get_settings_path", return_value=tmp_path / "missing.json"):
            settings = load_settings()
        assert settings["mode"] == C.MODE_TOGGLE
        assert settings["language"] == C.DEFAULT_LANGUAGE

    def test_load_reads_valid_file(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        path.write_text(
            json.dumps({
                "mode": "push_to_talk",
                "language": "ru",
                "model_size": "tiny",
                "widget_position": [50, 75],
                "global_hotkey": "<ctrl>+<alt>+r",
            }),
            encoding="utf-8",
        )
        with patch("src.config.get_settings_path", return_value=path):
            settings = load_settings()
        assert settings["mode"] == "push_to_talk"
        assert settings["language"] == "ru"
        assert settings["model_size"] == "tiny"
        assert settings["widget_position"] == [50, 75]
        assert settings["global_hotkey"] == "<ctrl>+<alt>+r"

    def test_load_falls_back_on_invalid_json(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        path.write_text("{ invalid json !!!", encoding="utf-8")
        with patch("src.config.get_settings_path", return_value=path):
            settings = load_settings()
        assert settings["mode"] == C.MODE_TOGGLE

    def test_load_falls_back_on_unknown_mode(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        path.write_text(
            json.dumps({"mode": "bogus_mode"}),
            encoding="utf-8",
        )
        with patch("src.config.get_settings_path", return_value=path):
            settings = load_settings()
        assert settings["mode"] == C.MODE_TOGGLE

    def test_load_falls_back_on_unknown_language(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        path.write_text(
            json.dumps({"language": "fr"}),
            encoding="utf-8",
        )
        with patch("src.config.get_settings_path", return_value=path):
            settings = load_settings()
        assert settings["language"] == C.DEFAULT_LANGUAGE

    def test_load_falls_back_on_unknown_device(self, tmp_path: Path) -> None:
        """Legacy settings.json without 'device' (or with a bogus value) must
        not crash — it falls back to the default device."""
        path = tmp_path / "settings.json"
        path.write_text(
            json.dumps({"device": "tpu"}),
            encoding="utf-8",
        )
        with patch("src.config.get_settings_path", return_value=path):
            settings = load_settings()
        assert settings["device"] == C.DEFAULT_DEVICE

    def test_load_reads_cuda_device(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        path.write_text(
            json.dumps({"device": "cuda"}),
            encoding="utf-8",
        )
        with patch("src.config.get_settings_path", return_value=path):
            settings = load_settings()
        assert settings["device"] == "cuda"


class TestSaveSettings:
    """Test saving settings to disk."""

    def test_save_writes_valid_json(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        data = {
            "mode": "toggle",
            "language": "en",
            "model_size": "base",
            "widget_position": [10, 20],
            "global_hotkey": "<ctrl>+v",
        }
        with patch("src.config.get_settings_path", return_value=path):
            save_settings(data)
        assert path.exists()
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["mode"] == "toggle"
        assert loaded["language"] == "en"

    def test_save_then_load_roundtrip(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        data = {
            "mode": "push_to_talk",
            "language": "ru",
            "model_size": "small",
            "device": "cuda",
            "widget_position": [300, 200],
            "global_hotkey": "<alt>+v",
        }
        with patch("src.config.get_settings_path", return_value=path):
            save_settings(data)
            loaded = load_settings()
        assert loaded == data
