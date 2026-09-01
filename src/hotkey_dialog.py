"""
hotkey_dialog.py — capture a global hotkey by pressing it.

A modal dialog that listens for the next key combination via Qt key events and
returns the corresponding pynput hotkey string (e.g. ``"<ctrl>+<alt>+v"``,
``"<ctrl_r>"``), which is the format :mod:`src.hotkey` expects.

Qt reports the same ``Key_Control`` for both physical Ctrl keys, so the side is
taken from the native scan code (on Windows the right-side key carries the
extended-key bit: Right Ctrl scans as 0x11D vs Left Ctrl 0x01D).
"""

from __future__ import annotations

from typing import List, Optional

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
    "<ctrl_l>": "L-Ctrl",
    "<ctrl_r>": "R-Ctrl",
    "<alt>": "Alt",
    "<alt_l>": "L-Alt",
    "<alt_r>": "R-Alt",
    "<shift>": "Shift",
    "<shift_l>": "L-Shift",
    "<shift_r>": "R-Shift",
    "<cmd>": "Win",
    "<cmd_l>": "L-Win",
    "<cmd_r>": "R-Win",
    "<space>": "Space",
    "<enter>": "Enter",
    "<tab>": "Tab",
}
# canonical modifier order when formatting (sides grouped with their base key)
_TOKEN_ORDER = (
    "<ctrl_l>", "<ctrl>", "<ctrl_r>",
    "<alt_l>", "<alt>", "<alt_r>",
    "<shift_l>", "<shift>", "<shift_r>",
    "<cmd_l>", "<cmd>", "<cmd_r>",
)

# Qt key -> generic modifier token
_QT_MODIFIER_KEYS = {
    Qt.Key_Control: "ctrl",
    Qt.Key_Alt: "alt",
    Qt.Key_Shift: "shift",
    Qt.Key_Meta: "cmd",
}

# Windows set-1 scan codes of the physical modifier variants, as reported by
# ``QKeyEvent.nativeScanCode()`` (the extended key contributes bit 0x100).
_SCAN_TO_TOKEN = {
    0x01D: "ctrl_l", 0x11D: "ctrl_r",
    0x02A: "shift_l", 0x036: "shift_r",
    0x038: "alt_l", 0x138: "alt_r",
    0x15B: "cmd_l", 0x15C: "cmd_r",
}


def pretty_hotkey(hotkey: str) -> str:
    """Render a pynput hotkey string as ``"Ctrl + Alt + V"``."""
    parts = hotkey.split("+")
    ordered = sorted(
        parts,
        key=lambda p: _TOKEN_ORDER.index(p) if p in _TOKEN_ORDER else len(_TOKEN_ORDER),
    )
    return " + ".join(_TOKEN_TO_LABEL.get(p, p.upper()) for p in ordered)


class HotkeyDialog(QDialog):
    """Press a key combination; the chosen combo becomes the hotkey."""

    def __init__(self, current: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Set Hotkey")
        self.setModal(True)
        self.setMinimumWidth(340)
        self._captured: Optional[str] = current
        # Modifier tokens physically held down right now, in press order.
        # Side-specific ("ctrl_r") when the scan code is known, generic
        # ("ctrl") otherwise.
        self._mods_down: List[str] = []

        layout = QVBoxLayout(self)

        self._instruction = QLabel(
            "Press the key combination you want to use.\n"
            "It must include Ctrl, Alt, Shift, or Win — a single Right Ctrl\n"
            "(or Left Ctrl / Right Alt, etc.) on its own also works."
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

        if event.isAutoRepeat():
            return

        # ── Modifier key: track the physically held side ──────────────────────
        generic = _QT_MODIFIER_KEYS.get(key)
        if generic is not None:
            token = _SCAN_TO_TOKEN.get(event.nativeScanCode(), generic)
            if token not in self._mods_down:
                self._mods_down.append(token)

            # A lone side modifier is itself a sensible hotkey (Right Ctrl);
            # a lone generic one is not — it would fire on both sides, i.e.
            # during everyday copy/paste.
            if self._mods_down == [token] and token in _SCAN_TO_TOKEN.values():
                self._captured = "<%s>" % token
                self._msg.setText("")
                self._refresh_display()
            return

        # ── Regular key: build the combination from the held modifiers ────────
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

        if not self._mods_down:
            self._msg.setText("Add Ctrl / Alt / Shift / Win.")
            return
        if token is None:
            self._msg.setText("Use a letter, digit, Space, or Enter.")
            return

        parts = ["<%s>" % m for m in self._mods_down]
        self._captured = "+".join(parts + [token])
        self._msg.setText("")
        self._refresh_display()

    def keyReleaseEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        """Forget the released modifier so the next capture starts clean."""
        if event.isAutoRepeat():
            return
        generic = _QT_MODIFIER_KEYS.get(event.key())
        if generic is not None:
            token = _SCAN_TO_TOKEN.get(event.nativeScanCode(), generic)
            while token in self._mods_down:
                self._mods_down.remove(token)

    def hotkey(self) -> Optional[str]:
        """Return the captured hotkey string (pynput format)."""
        return self._captured
