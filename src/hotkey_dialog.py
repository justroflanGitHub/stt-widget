"""
hotkey_dialog.py — capture a global hotkey by pressing it.

A modal dialog that listens for the next key combination via Qt key events and
returns the corresponding pynput hotkey string (e.g. ``"<ctrl>+<alt>+v"``),
which is the format ``pynput.keyboard.GlobalHotKeys`` expects.
"""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from . import constants as C

# pynput token -> human-readable label
_TOKEN_TO_LABEL = {
    "<ctrl>": "Ctrl",
    "<alt>": "Alt",
    "<shift>": "Shift",
    "<cmd>": "Win",
    "<space>": "Space",
    "<enter>": "Enter",
    "<tab>": "Tab",
}
# canonical modifier order when formatting
_MOD_ORDER = ("<ctrl>", "<alt>", "<shift>", "<cmd>")


def pretty_hotkey(hotkey: str) -> str:
    """Render a pynput hotkey string as ``"Ctrl + Alt + V"``."""
    parts = hotkey.split("+")
    return " + ".join(_TOKEN_TO_LABEL.get(p, p.upper()) for p in parts)


class HotkeyDialog(QDialog):
    """Press a key combination; the chosen combo becomes the hotkey."""

    def __init__(self, current: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Set Hotkey")
        self.setModal(True)
        self.setMinimumWidth(340)
        self._captured: Optional[str] = current

        layout = QVBoxLayout(self)

        self._instruction = QLabel(
            "Press the key combination you want to use.\n"
            "It must include Ctrl, Alt, Shift, or Win."
        )
        self._instruction.setWordWrap(True)
        layout.addWidget(self._instruction)

        self._display = QLabel()
        self._display.setAlignment(Qt.AlignCenter)
        self._display.setStyleSheet("font-size: 22px; font-weight: bold; padding: 14px;")
        layout.addWidget(self._display)

        self._msg = QLabel("")
        self._msg.setAlignment(Qt.AlignCenter)
        self._msg.setStyleSheet("color: #cc5555;")
        layout.addWidget(self._msg)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        self._save_btn = self._buttons.button(QDialogButtonBox.Save)
        self._save_btn.setEnabled(False)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        reset = QPushButton("Reset to default (%s)" % pretty_hotkey(C.DEFAULT_HOTKEY))
        reset.clicked.connect(self._reset_default)
        layout.addWidget(reset)

        self._refresh_display()
        self.grabKeyboard()

    def _refresh_display(self) -> None:
        if self._captured:
            self._display.setText(pretty_hotkey(self._captured))
            self._save_btn.setEnabled(True)
        else:
            self._display.setText("Press a key combination…")
            self._save_btn.setEnabled(False)

    def _reset_default(self) -> None:
        self._captured = C.DEFAULT_HOTKEY
        self._msg.setText("")
        self._refresh_display()

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        key = event.key()
        mods = event.modifiers()

        # Ignore bare modifier presses and auto-repeat — wait for a real key.
        if key in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta):
            return
        if event.isAutoRepeat():
            return

        parts = []
        if mods & Qt.ControlModifier:
            parts.append("<ctrl>")
        if mods & Qt.AltModifier:
            parts.append("<alt>")
        if mods & Qt.ShiftModifier:
            parts.append("<shift>")
        if mods & Qt.MetaModifier:
            parts.append("<cmd>")
        parts = [m for m in _MOD_ORDER if m in parts]

        token: Optional[str] = None
        if Qt.Key_A <= key <= Qt.Key_Z:
            token = chr(key).lower()
        elif Qt.Key_0 <= key <= Qt.Key_9:
            token = chr(key)
        elif key == Qt.Key_Space:
            token = "<space>"
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            token = "<enter>"
        elif key == Qt.Key_Tab:
            token = "<tab>"

        if not parts:
            self._msg.setText("Add Ctrl / Alt / Shift / Win.")
            return
        if token is None:
            self._msg.setText("Use a letter, digit, Space, or Enter.")
            return

        self._captured = "+".join(parts + [token])
        self._msg.setText("")
        self._refresh_display()

    def hotkey(self) -> Optional[str]:
        """Return the captured hotkey string (pynput format)."""
        return self._captured
