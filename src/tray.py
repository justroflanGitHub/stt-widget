"""
tray.py — System tray icon with context menu for the VoiceToText widget.

Provides quick access to: mode toggle, language selection, settings reset, quit.
The tray icon dynamically changes based on the widget state.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush, QPen, QRadialGradient
from PyQt5.QtCore import Qt, QRectF, QObject, QPointF, pyqtSignal
from PyQt5.QtWidgets import (
    QAction,
    QActionGroup,
    QMenu,
    QSystemTrayIcon,
)

from . import constants as C

logger = logging.getLogger(__name__)


def _draw_icon(state: str, size: int = 64) -> QPixmap:
    """Draw a tray icon pixmap for the given widget state.

    Args:
        state: One of STATE_* constants.
        size: Pixel size of the square pixmap.

    Returns:
        QPixmap with the rendered icon.
    """
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing, True)

    centre = size / 2

    # ── Resolve colours ───────────────────────────────────────────────────────
    state_colours = {
        C.STATE_IDLE: (C.COLOR_IDLE_BG, C.COLOR_IDLE_FG, C.COLOR_IDLE_BORDER),
        C.STATE_RECORDING: (C.COLOR_RECORDING_BG, C.COLOR_RECORDING_FG, C.COLOR_RECORDING_BORDER),
        C.STATE_PROCESSING: (C.COLOR_PROCESSING_BG, C.COLOR_PROCESSING_FG, C.COLOR_PROCESSING_BORDER),
        C.STATE_DONE: (C.COLOR_DONE_BG, C.COLOR_DONE_FG, C.COLOR_DONE_BORDER),
        C.STATE_LOADING: (C.COLOR_LOADING_BG, C.COLOR_LOADING_FG, C.COLOR_LOADING_BG),
    }
    bg_hex, fg_hex, border_hex = state_colours.get(state, state_colours[C.STATE_IDLE])
    bg = QColor(bg_hex)
    fg = QColor(fg_hex)
    border = QColor(border_hex)

    # ── Background circle ─────────────────────────────────────────────────────
    gradient = QRadialGradient(QPointF(centre, centre), centre)
    gradient.setColorAt(0.0, bg)
    gradient.setColorAt(1.0, QColor(0, 0, 0, 200))
    painter.setBrush(QBrush(gradient))
    painter.setPen(QPen(border, 2))
    painter.drawEllipse(2, 2, size - 4, size - 4)

    if state == C.STATE_RECORDING:
        # Big red dot
        red = QColor(C.COLOR_RECORDING_FG)
        painter.setBrush(QBrush(red))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(centre, centre), size * 0.28, size * 0.28)
        # Inner highlight
        highlight = QColor(255, 255, 255, 80)
        painter.setBrush(QBrush(highlight))
        painter.drawEllipse(QPointF(centre - 3, centre - 3), size * 0.10, size * 0.10)

    elif state == C.STATE_PROCESSING:
        # Yellow spinner arc
        yellow = QColor(C.COLOR_PROCESSING_FG)
        painter.setPen(QPen(yellow, 3, Qt.SolidLine, Qt.RoundCap))
        painter.setBrush(Qt.NoBrush)
        radius = size * 0.28
        rect = QRectF(centre - radius, centre - radius, radius * 2, radius * 2)
        painter.drawArc(rect, 45 * 16, 270 * 16)
        # Three dots
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(yellow))
        for i in range(3):
            angle = math.radians(i * 120 + 45)
            dx = math.cos(angle) * (radius + 5)
            dy = math.sin(angle) * (radius + 5)
            painter.drawEllipse(QPointF(centre + dx, centre + dy), 2, 2)

    elif state == C.STATE_DONE:
        # Green checkmark
        green = QColor(C.COLOR_DONE_FG)
        painter.setPen(QPen(green, 3.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        s = size * 0.18
        p1 = QPointF(centre - s, centre + s * 0.15)
        p2 = QPointF(centre - s * 0.3, centre + s * 0.8)
        p3 = QPointF(centre + s, centre - s * 0.6)
        painter.drawLine(p1, p2)
        painter.drawLine(p2, p3)

    elif state == C.STATE_LOADING:
        # Three pink dots
        pink = QColor(C.COLOR_LOADING_FG)
        painter.setBrush(QBrush(pink))
        painter.setPen(Qt.NoPen)
        for i, offset in enumerate([-10, 0, 10]):
            painter.drawEllipse(QPointF(centre + offset, centre), 3, 3)

    else:
        # Idle: mic icon
        painter.setPen(QPen(fg, 2.5, Qt.SolidLine, Qt.RoundCap))
        painter.setBrush(Qt.NoBrush)
        mic_w = size * 0.20
        mic_h = size * 0.32
        mic_rect = QRectF(centre - mic_w / 2, centre - mic_h / 2 - 2, mic_w, mic_h)
        painter.drawRoundedRect(mic_rect, mic_w / 2, mic_w / 2)
        arc_r = size * 0.23
        painter.drawArc(
            QRectF(centre - arc_r, centre - arc_r / 2, arc_r * 2, arc_r * 2),
            0, 180 * 16,
        )
        painter.drawLine(
            QPointF(centre, centre + arc_r / 2),
            QPointF(centre, centre + arc_r / 2 + 4),
        )

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
    model_changed = pyqtSignal(str)
    set_hotkey_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(
        self,
        mode: str = C.MODE_TOGGLE,
        language: str = C.DEFAULT_LANGUAGE,
        model_size: str = C.DEFAULT_MODEL_SIZE,
    ) -> None:
        super().__init__()
        self._mode = mode
        self._language = language
        self._model_size = model_size
        self._state = C.STATE_IDLE

        icon = QIcon(_draw_icon(C.STATE_IDLE))
        self._tray = QSystemTrayIcon(icon)
        self._tray.setToolTip(C.APP_NAME)
        self._tray.setVisible(True)

        self._build_menu()

    def _build_menu(self) -> None:
        """Construct the right-click context menu."""
        menu = QMenu()

        # ── Set hotkey action ────────────────────────────────────────────────
        self._hotkey_action = QAction("Set Hotkey…", menu)
        self._hotkey_action.triggered.connect(lambda: self.set_hotkey_requested.emit())
        menu.addAction(self._hotkey_action)
        menu.addSeparator()

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

        # ── Model submenu ────────────────────────────────────────────────────
        model_menu = menu.addMenu("Model")
        model_group = QActionGroup(menu)
        model_group.setExclusive(True)
        for size in C.SUPPORTED_MODEL_SIZES:
            label = C.MODEL_LABELS.get(size, size)
            act = QAction(label, model_menu, checkable=True)
            act.setChecked(self._model_size == size)
            act.triggered.connect(lambda checked, sz=size: self._on_model_selected(sz))
            model_group.addAction(act)
            model_menu.addAction(act)

        # ── Separator + Quit ──────────────────────────────────────────────────
        menu.addSeparator()
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self._on_quit)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)

    # ── State management ──────────────────────────────────────────────────────

    def set_state(self, state: str) -> None:
        """Update the tray icon to reflect the current widget state.

        Args:
            state: One of ``STATE_*`` constants.
        """
        if state == self._state:
            return
        self._state = state
        icon = QIcon(_draw_icon(state))
        self._tray.setIcon(icon)

        tooltips = {
            C.STATE_IDLE: C.APP_NAME,
            C.STATE_RECORDING: f"{C.APP_NAME} — Recording…",
            C.STATE_PROCESSING: f"{C.APP_NAME} — Processing…",
            C.STATE_DONE: f"{C.APP_NAME} — Done",
            C.STATE_LOADING: f"{C.APP_NAME} — Loading model…",
        }
        self._tray.setToolTip(tooltips.get(state, C.APP_NAME))

    # ── Slot handlers ─────────────────────────────────────────────────────────

    def _on_mode_selected(self, mode: str) -> None:
        self._mode = mode
        self.mode_changed.emit(mode)
        logger.info("Tray: mode changed to %s", mode)

    def _on_language_selected(self, lang: str) -> None:
        self._language = lang
        self.language_changed.emit(lang)
        logger.info("Tray: language changed to %s", lang)

    def _on_model_selected(self, size: str) -> None:
        self._model_size = size
        self.model_changed.emit(size)
        logger.info("Tray: model changed to %s", size)

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

    def update_model(self, size: str) -> None:
        """Update the checked state of the model menu."""
        self._model_size = size

    def update_hotkey_label(self, hotkey: str) -> None:
        """Refresh the 'Set Hotkey…' action to show the current binding."""
        from .hotkey_dialog import pretty_hotkey
        self._hotkey_action.setText("Set Hotkey… (%s)" % pretty_hotkey(hotkey))

    def hide(self) -> None:
        """Hide the tray icon."""
        self._tray.hide()
