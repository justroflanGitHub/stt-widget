"""
main.py — Entry point for VoiceToText Widget.

Wires together the widget, audio recorder, transcriber, tray, and global hotkey.
"""

from __future__ import annotations

import logging
import sys
import threading
from typing import Optional

from PyQt5.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import QApplication

from . import constants as C
from .config import load_settings, save_settings
from .clipboard_util import copy_to_clipboard

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("voice-widget")


class AppController(QObject):
    """Central controller connecting all components.

    Runs audio recording and transcription on background threads so the
    PyQt5 event loop is never blocked.
    """

    recording_started = pyqtSignal()
    recording_stopped = pyqtSignal()
    transcription_done = pyqtSignal(str)
    model_loaded = pyqtSignal(bool)

    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self._app = app
        self._settings = load_settings()
        self._recorder = None
        self._transcriber = None
        self._widget = None
        self._tray = None
        self._hotkey_listener = None
        self._last_transcription: str = ""

        self._init_components()

    def _init_components(self) -> None:
        """Create and wire all application components."""
        # ── Import heavy modules lazily ────────────────────────────────────────
        from .widget import VoiceWidget
        from .tray import TrayController
        from .audio_recorder import AudioRecorder
        from .transcriber import Transcriber

        # ── Transcriber (model loads in background) ────────────────────────────
        self._transcriber = Transcriber(
            model_size=self._settings["model_size"],
            compute_type=C.DEFAULT_COMPUTE_TYPE,
            device=C.DEFAULT_DEVICE,
        )
        self._transcriber.load_model(callback=self._on_model_loaded)

        # ── Audio recorder ─────────────────────────────────────────────────────
        self._recorder = AudioRecorder()

        # ── Widget ─────────────────────────────────────────────────────────────
        pos = self._settings.get("widget_position", [100, 100])
        self._widget = VoiceWidget(mode=self._settings["mode"])
        self._widget.move(pos[0], pos[1])
        self._widget.show()

        # Wire widget callbacks
        self._widget.on_activate = self.start_recording
        self._widget.on_deactivate = self.stop_recording
        self._widget.on_drag_end = self._on_widget_dragged

        # ── Tray ───────────────────────────────────────────────────────────────
        self._tray = TrayController(
            mode=self._settings["mode"],
            language=self._settings["language"],
        )
        self._tray.mode_changed.connect(self._on_mode_changed)
        self._tray.language_changed.connect(self._on_language_changed)
        self._tray.quit_requested.connect(self.quit)

        # ── Global hotkey ──────────────────────────────────────────────────────
        self._setup_hotkey()

    def _setup_hotkey(self) -> None:
        """Register the global hotkey via pynput."""
        from pynput import keyboard

        hotkey_str = self._settings.get("global_hotkey", C.DEFAULT_HOTKEY)

        def _on_activate() -> None:
            """Called when the global hotkey is pressed."""
            logger.info("Global hotkey activated.")
            state = self._widget.get_state()
            if state in (C.STATE_IDLE, C.STATE_DONE):
                self.start_recording()
            elif state == C.STATE_RECORDING:
                self.stop_recording()

        try:
            self._hotkey_listener = keyboard.GlobalHotKeys({
                hotkey_str: _on_activate,
            })
            self._hotkey_listener.start()
            logger.info("Global hotkey registered: %s", hotkey_str)
        except Exception as exc:
            logger.warning("Failed to register hotkey: %s", exc)

    # ── Model callback ─────────────────────────────────────────────────────────

    def _on_model_loaded(self, success: bool) -> None:
        """Called from the model-loader background thread."""
        self.model_loaded.emit(success)
        if success:
            self._widget.set_state(C.STATE_IDLE)
            if self._tray:
                self._tray.set_state(C.STATE_IDLE)
            logger.info("Model ready — widget is now active.")
        else:
            self._widget.set_state(C.STATE_IDLE)
            if self._tray:
                self._tray.set_state(C.STATE_IDLE)
            logger.error("Model failed to load. Widget will attempt transcription on demand.")

    # ── Recording lifecycle ────────────────────────────────────────────────────

    def start_recording(self) -> None:
        """Begin microphone recording (called from UI thread)."""
        if self._recorder.is_recording:
            return
        if self._widget.get_state() in (C.STATE_PROCESSING, C.STATE_LOADING):
            return
        try:
            self._recorder.start()
            self._widget.set_state(C.STATE_RECORDING)
            if self._tray:
                self._tray.set_state(C.STATE_RECORDING)
            self.recording_started.emit()
        except Exception as exc:
            logger.error("Failed to start recording: %s", exc)

    def stop_recording(self) -> None:
        """Stop recording and launch transcription thread."""
        if not self._recorder.is_recording:
            return
        self._widget.set_state(C.STATE_PROCESSING)
        if self._tray:
            self._tray.set_state(C.STATE_PROCESSING)
        self.recording_stopped.emit()

        thread = threading.Thread(
            target=self._transcribe_worker,
            daemon=True,
            name="transcribe-worker",
        )
        thread.start()

    def _transcribe_worker(self) -> None:
        """Run in a background thread: get audio → transcribe → copy → notify UI."""
        audio = self._recorder.stop()
        if audio is None or len(audio) < int(C.SAMPLE_RATE * C.MIN_RECORDING_DURATION_S):
            logger.warning("Recording too short; discarding.")
            QTimer.singleShot(0, lambda: self._set_state_both(C.STATE_IDLE))
            return

        text = self._transcriber.transcribe(audio, language=self._settings["language"])

        if text:
            self._last_transcription = text
            copy_to_clipboard(text)

        # Update UI on the main thread
        QTimer.singleShot(0, lambda: self._on_transcription_complete(text))

    def _set_state_both(self, state: str) -> None:
        """Update both widget and tray icon to the same state."""
        self._widget.set_state(state)
        if self._tray:
            self._tray.set_state(state)

    def _on_transcription_complete(self, text: str) -> None:
        """Called on the main thread after transcription finishes."""
        self._widget.set_state(C.STATE_DONE)
        self.transcription_done.emit(text)

        if text and self._tray:
            self._tray.show_message(
                "Transcription",
                text[:200] + ("…" if len(text) > 200 else ""),
            )

        # Return to idle after the flash
        QTimer.singleShot(C.DONE_FLASH_DURATION_MS, lambda: self._set_state_both(C.STATE_IDLE))

    # ── Settings callbacks ─────────────────────────────────────────────────────

    def _on_mode_changed(self, mode: str) -> None:
        self._settings["mode"] = mode
        self._widget.set_mode(mode)
        save_settings(self._settings)
        if self._tray:
            self._tray.show_message("Mode", f"Switched to {mode}")

    def _on_language_changed(self, lang: str) -> None:
        self._settings["language"] = lang
        save_settings(self._settings)
        if self._tray:
            self._tray.show_message("Language", f"Set to {lang}")

    def _on_widget_dragged(self, x: int, y: int) -> None:
        self._settings["widget_position"] = [x, y]
        save_settings(self._settings)

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def quit(self) -> None:
        """Clean shutdown: stop hotkey, save settings, quit app."""
        logger.info("Shutting down…")
        if self._hotkey_listener:
            self._hotkey_listener.stop()
        if self._recorder and self._recorder.is_recording:
            self._recorder.stop()
        save_settings(self._settings)
        if self._tray:
            self._tray.hide()
        self._app.quit()


def main() -> None:
    """Application entry point."""
    app = QApplication(sys.argv)
    app.setApplicationName(C.APP_NAME)
    app.setApplicationVersion(C.APP_VERSION)
    app.setQuitOnLastWindowClosed(False)  # tray keeps app alive

    controller = AppController(app)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
