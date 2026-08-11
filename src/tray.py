"""
tray.py — System tray icon with context menu for the VoiceToText widget.

Provides quick access to: mode toggle, language selection, settings reset, quit.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush, QPen
from PyQt5.QtCore import Qt, QRectF, QObject, pyqtSignal
from PyQt5.QtWidgets import (
    QAction,
    QActionGroup,
    QMenu,
    QSystemTrayIcon,
)

from . import constants as C

logger = logging.getLogger(__name__)


def _create_tray_icon_pixmap() -> QPixmap:
    """Draw a simple mic-in-circle icon for the system tray."""
    size = 64
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing, True)

    # Background circle
    bg = QColor(C.COLOR_IDLE_BG)
    painter.setBrush(QBrush(bg))
    painter.setPen(QPen(QColor(C.COLOR_IDLE_BORDER), 2))
    painter.drawEllipse(2, 2, size - 4, size - 4)

    # Mic capsule
    fg = QColor(C.COLOR_IDLE_FG)
    painter.setPen(QPen(fg, 2.5, Qt.SolidLine, Qt.RoundCap))
    painter.setBrush(Qt.NoBrush)
    centre = size / 2
    painter.drawRoundedRect(QRectF(centre - 6, centre - 12, 12, 18), 6, 6)

    # Arc
    arc_r = 12
    painter.drawArc(QRectF(centre - arc_r, centre - arc_r / 2, arc_r * 2, arc_r * 2), 0, 180 * 16)

    # Stem
    painter.drawLine(int(centre), int(centre + arc_r / 2), int(centre), int(centre + arc_r / 2 + 4))

    painter.end()
    return pix


class TrayController(QObject):
    """Manages the QSystemTrayIcon and its context menu.

    Signals:
        mode_changed(str): Emitted when the user switches mode.
        language_changed(str): Emitted when the user picks a language.
        quit_requested(): Emitted when the user selects Quit.
    """

    mode_changed = pyqtSignal(str)
    language_changed = pyqtSignal(str)
    quit_requested = pyqtSignal()

    def __init__(self, mode: str = C.MODE_TOGGLE, language: str = C.DEFAULT_LANGUAGE) -> None:
        super().__init__()
        self._mode = mode
        self._language = language

        icon = QIcon(_create_tray_icon_pixmap())

        self._tray = QSystemTrayIcon(icon)
        self._tray.setToolTip(C.APP_NAME)
        self._tray.setVisible(True)

        self._build_menu()

    def _build_menu(self) -> None:
        """Construct the right-click context menu."""
        menu = QMenu()

        # ── Mode submenu ──────────────────────────────────────────────────────
        mode_menu = menu.addMenu("Mode")
        mode_group = QActionGroup(menu)
        mode_group.setExclusive(True)

        toggle_action = QAction("Toggle", mode_menu, checkable=True)
        ptt_action = QAction("Push-to-Talk", mode_menu, checkable=True)
        toggle_action.setChecked(self._mode == C.MODE_TOGGLE)
        ptt_action.setChecked(self._mode == C.MODE_PUSH_TO_TALK)
        toggle_action.triggered.connect(lambda: self._on_mode_selected(C.MODE_TOGGLE))
        ptt_action.triggered.connect(lambda: self._on_mode_selected(C.MODE_PUSH_TO_TALK))
        mode_group.addAction(toggle_action)
        mode_group.addAction(ptt_action)
        mode_menu.addAction(toggle_action)
        mode_menu.addAction(ptt_action)

        # ── Language submenu ──────────────────────────────────────────────────
        lang_menu = menu.addMenu("Language")
        lang_group = QActionGroup(menu)
        lang_group.setExclusive(True)

        for lang_code in C.SUPPORTED_LANGUAGES:
            label = "Auto" if lang_code == "auto" else ("Russian" if lang_code == "ru" else "English")
            act = QAction(label, lang_menu, checkable=True)
            act.setChecked(self._language == lang_code)
            act.triggered.connect(lambda checked, lc=lang_code: self._on_language_selected(lc))
            lang_group.addAction(act)
            lang_menu.addAction(act)

        # ── Separator + Quit ──────────────────────────────────────────────────
        menu.addSeparator()
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self._on_quit)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)

    # ── Slot handlers ─────────────────────────────────────────────────────────

    def _on_mode_selected(self, mode: str) -> None:
        self._mode = mode
        self.mode_changed.emit(mode)
        logger.info("Tray: mode changed to %s", mode)

    def _on_language_selected(self, lang: str) -> None:
        self._language = lang
        self.language_changed.emit(lang)
        logger.info("Tray: language changed to %s", lang)

    def _on_quit(self) -> None:
        logger.info("Tray: quit requested.")
        self.quit_requested.emit()

    # ── Public methods ────────────────────────────────────────────────────────

    def show_message(self, title: str, message: str) -> None:
        """Show a balloon notification from the tray icon."""
        self._tray.showMessage(title, message, QSystemTrayIcon.Information, C.TOOLTIP_DURATION_MS)

    def update_mode(self, mode: str) -> None:
        """Update the checked state of the mode menu."""
        self._mode = mode

    def update_language(self, lang: str) -> None:
        """Update the checked state of the language menu."""
        self._language = lang

    def hide(self) -> None:
        """Hide the tray icon."""
        self._tray.hide()
