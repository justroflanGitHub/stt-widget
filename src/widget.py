"""
widget.py — PyQt5 frameless always-on-top draggable widget.

Renders the mic icon with QPainter (no external assets).
Manages the recording → transcribing → done state machine.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

from PyQt5.QtCore import (
    QPropertyAnimation,
    QPoint,
    QPointF,
    QRectF,
    QSize,
    Qt,
    QTimer,
    pyqtProperty,
)
from PyQt5.QtGui import (
    QBrush,
    QColor,
    QLinearGradient,
    QPainter,
    QPen,
    QRadialGradient,
)
from PyQt5.QtWidgets import QWidget

from . import constants as C

logger = logging.getLogger(__name__)


def _color_from_hex(hex_str: str) -> QColor:
    """Convert ``"#RRGGBB"`` string to ``QColor``."""
    return QColor(hex_str)


class VoiceWidget(QWidget):
    """The floating voice-to-text widget.

    Signals (via Qt properties & timers):
        - Click handling is done in :meth:`mousePressEvent` / :meth:`mouseReleaseEvent`.
        - External code connects by polling :attr:`state` or overriding callbacks.
    """

    # Callbacks set by main.py
    on_activate: Optional[callable] = None     # called when user starts recording
    on_deactivate: Optional[callable] = None   # called when user stops recording
    on_drag_end: Optional[callable] = None     # called with (x, y) when widget moved

    def __init__(self, mode: str = C.MODE_TOGGLE, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._mode: str = mode
        self._state: str = C.STATE_LOADING  # start in loading until model ready
        self._drag_offset: Optional[QPoint] = None
        self._pulse_visible: bool = True
        self._spinner_angle: float = 0.0

        # ── Window flags: frameless, always on top, tool window ───────────────
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # ── Fixed size ────────────────────────────────────────────────────────
        self.setFixedSize(C.WIDGET_SIZE, C.WIDGET_SIZE)

        # ── Timers ────────────────────────────────────────────────────────────
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._on_pulse_tick)

        self._spinner_timer = QTimer(self)
        self._spinner_timer.timeout.connect(self._on_spinner_tick)

        self._done_timer = QTimer(self)
        self._done_timer.setSingleShot(True)
        self._done_timer.timeout.connect(self._reset_to_idle)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_state(self, state: str) -> None:
        """Update the widget visual state.

        Args:
            state: One of ``STATE_*`` constants.
        """
        self._state = state
        self.update()

        # Manage timers
        self._pulse_timer.stop()
        self._spinner_timer.stop()

        if state == C.STATE_RECORDING:
            self._pulse_timer.start(C.PULSE_INTERVAL_MS)
        elif state == C.STATE_PROCESSING:
            self._spinner_angle = 0.0
            self._spinner_timer.start(C.SPINNER_INTERVAL_MS)
        elif state == C.STATE_DONE:
            self._done_timer.start(C.DONE_FLASH_DURATION_MS)

    def get_state(self) -> str:
        """Return the current visual state."""
        return self._state

    def set_mode(self, mode: str) -> None:
        """Set interaction mode (``MODE_TOGGLE`` or ``MODE_PUSH_TO_TALK``)."""
        self._mode = mode

    def get_mode(self) -> str:
        """Return the current interaction mode."""
        return self._mode

    def _reset_to_idle(self) -> None:
        """Return to idle after the done flash."""
        if self._state == C.STATE_DONE:
            self.set_state(C.STATE_IDLE)

    # ── Drawing ───────────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        """Render the widget based on the current state."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = QRectF(0, 0, C.WIDGET_SIZE, C.WIDGET_SIZE)

        # Resolve colours for current state
        bg_color, fg_color, border_color = self._colours_for_state()

        # Draw background circle with gradient
        gradient = QRadialGradient(
            QPointF(C.WIDGET_SIZE / 2, C.WIDGET_SIZE / 2), C.WIDGET_SIZE / 2
        )
        gradient.setColorAt(0.0, bg_color)
        gradient.setColorAt(1.0, QColor(0, 0, 0, 200))
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(border_color), 2))
        painter.drawRoundedRect(rect, C.WIDGET_CORNER_RADIUS, C.WIDGET_CORNER_RADIUS)

        # Draw state-specific icon
        if self._state == C.STATE_RECORDING:
            self._draw_recording_icon(painter)
        elif self._state == C.STATE_PROCESSING:
            self._draw_processing_icon(painter)
        elif self._state == C.STATE_DONE:
            self._draw_done_icon(painter)
        elif self._state == C.STATE_LOADING:
            self._draw_loading_icon(painter)
        else:
            self._draw_mic_icon(painter)

    def _colours_for_state(self) -> tuple[QColor, QColor, QColor]:
        """Return (background, foreground, border) colours for the current state."""
        mapping = {
            C.STATE_IDLE: (C.COLOR_IDLE_BG, C.COLOR_IDLE_FG, C.COLOR_IDLE_BORDER),
            C.STATE_RECORDING: (C.COLOR_RECORDING_BG, C.COLOR_RECORDING_FG, C.COLOR_RECORDING_BORDER),
            C.STATE_PROCESSING: (C.COLOR_PROCESSING_BG, C.COLOR_PROCESSING_FG, C.COLOR_PROCESSING_BORDER),
            C.STATE_DONE: (C.COLOR_DONE_BG, C.COLOR_DONE_FG, C.COLOR_DONE_BORDER),
            C.STATE_LOADING: (C.COLOR_LOADING_BG, C.COLOR_LOADING_FG, C.COLOR_LOADING_BG),
        }
        bg, fg, br = mapping.get(self._state, mapping[C.STATE_IDLE])
        return _color_from_hex(bg), _color_from_hex(fg), _color_from_hex(br)

    def _draw_mic_icon(self, painter: QPainter) -> None:
        """Draw a microphone icon (idle state)."""
        centre_x = C.WIDGET_SIZE / 2
        centre_y = C.WIDGET_SIZE / 2

        fg = _color_from_hex(C.COLOR_IDLE_FG)
        painter.setPen(QPen(fg, 2.5, Qt.SolidLine, Qt.RoundCap))
        painter.setBrush(Qt.NoBrush)

        # Mic capsule body
        mic_w = 12
        mic_h = 20
        mic_rect = QRectF(
            centre_x - mic_w / 2,
            centre_y - mic_h / 2 - 2,
            mic_w,
            mic_h,
        )
        painter.drawRoundedRect(mic_rect, 6, 6)

        # Stand arc (U-shape under the capsule)
        arc_radius = 14
        arc_rect = QRectF(
            centre_x - arc_radius,
            centre_y - arc_radius / 2,
            arc_radius * 2,
            arc_radius * 2,
        )
        painter.drawArc(arc_rect, 0 * 16, 180 * 16)

        # Stem
        painter.drawLine(
            QPointF(centre_x, centre_y + arc_radius / 2),
            QPointF(centre_x, centre_y + arc_radius / 2 + 4),
        )

    def _draw_recording_icon(self, painter: QPainter) -> None:
        """Draw a pulsing red circle with outer glow (recording state)."""
        centre_x = C.WIDGET_SIZE / 2
        centre_y = C.WIDGET_SIZE / 2

        # Outer glow ring (expands/contracts with pulse)
        glow_alpha = 120 if self._pulse_visible else 30
        glow_radius = 26 if self._pulse_visible else 22
        glow = QColor(255, 0, 0, glow_alpha)
        painter.setBrush(QBrush(glow))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(centre_x, centre_y), glow_radius, glow_radius)

        # Main red circle
        red = QColor(C.COLOR_RECORDING_FG)
        alpha = 255 if self._pulse_visible else 140
        red.setAlpha(alpha)
        painter.setBrush(QBrush(red))
        painter.setPen(Qt.NoPen)

        radius = 16
        painter.drawEllipse(QPointF(centre_x, centre_y), radius, radius)

        # Inner highlight
        highlight = QColor(255, 255, 255, alpha // 3)
        painter.setBrush(QBrush(highlight))
        painter.drawEllipse(QPointF(centre_x - 4, centre_y - 4), 6, 6)

    def _draw_processing_icon(self, painter: QPainter) -> None:
        """Draw a spinner arc (processing state)."""
        centre_x = C.WIDGET_SIZE / 2
        centre_y = C.WIDGET_SIZE / 2
        radius = 14

        yellow = _color_from_hex(C.COLOR_PROCESSING_FG)
        painter.setPen(QPen(yellow, 3, Qt.SolidLine, Qt.RoundCap))
        painter.setBrush(Qt.NoBrush)

        # Draw a 90° arc that rotates
        start_angle = int(self._spinner_angle * 16)
        span = 90 * 16
        rect = QRectF(
            centre_x - radius,
            centre_y - radius,
            radius * 2,
            radius * 2,
        )
        painter.drawArc(rect, start_angle, span)

        # Three dots
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(yellow))
        for i in range(3):
            angle = math.radians(self._spinner_angle / 16 + i * 120)
            dx = math.cos(angle) * (radius + 4)
            dy = math.sin(angle) * (radius + 4)
            painter.drawEllipse(QPointF(centre_x + dx, centre_y + dy), 1.5, 1.5)

    def _draw_done_icon(self, painter: QPainter) -> None:
        """Draw a checkmark (done state)."""
        centre_x = C.WIDGET_SIZE / 2
        centre_y = C.WIDGET_SIZE / 2

        green = _color_from_hex(C.COLOR_DONE_FG)
        painter.setPen(QPen(green, 3.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)

        # Checkmark: down-right then up-right
        p1 = QPointF(centre_x - 10, centre_y + 1)
        p2 = QPointF(centre_x - 3, centre_y + 8)
        p3 = QPointF(centre_x + 10, centre_y - 6)

        painter.drawLine(p1, p2)
        painter.drawLine(p2, p3)

    def _draw_loading_icon(self, painter: QPainter) -> None:
        """Draw three pulsing dots (loading model state)."""
        centre_x = C.WIDGET_SIZE / 2
        centre_y = C.WIDGET_SIZE / 2

        pink = _color_from_hex(C.COLOR_LOADING_FG)
        painter.setBrush(QBrush(pink))
        painter.setPen(Qt.NoPen)

        for i, offset in enumerate([-10, 0, 10]):
            t = (self._spinner_angle / 360 + i / 3.0) % 1.0
            alpha = int(80 + 175 * abs(math.sin(t * math.pi)))
            c = QColor(pink)
            c.setAlpha(alpha)
            painter.setBrush(QBrush(c))
            painter.drawEllipse(QPointF(centre_x + offset, centre_y), 3, 3)

    # ── Timer slots ───────────────────────────────────────────────────────────

    def _on_pulse_tick(self) -> None:
        """Toggle pulse visibility for recording animation."""
        self._pulse_visible = not self._pulse_visible
        self.update()

    def _on_spinner_tick(self) -> None:
        """Advance spinner / loading animation."""
        self._spinner_angle = (self._spinner_angle + 30) % 3600
        self.update()

    # ── Mouse handling (drag + click logic) ───────────────────────────────────

    def mousePressEvent(self, event) -> None:  # noqa: N802
        """Handle mouse press: start drag or start recording."""
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.pos()

            if self._mode == C.MODE_PUSH_TO_TALK and self._state in (C.STATE_IDLE, C.STATE_DONE):
                if self.on_activate:
                    self.on_activate()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        """Move the widget while dragging."""
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(self.pos() + event.pos() - self._drag_offset)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        """Handle mouse release: stop drag, trigger callbacks."""
        if event.button() == Qt.LeftButton:
            # Notify drag end
            if self.on_drag_end:
                self.on_drag_end(self.x(), self.y())

            if self._mode == C.MODE_PUSH_TO_TALK:
                if self._state == C.STATE_RECORDING and self.on_deactivate:
                    self.on_deactivate()
            elif self._mode == C.MODE_TOGGLE:
                if self._state in (C.STATE_IDLE,):
                    if self.on_activate:
                        self.on_activate()
                elif self._state == C.STATE_RECORDING:
                    if self.on_deactivate:
                        self.on_deactivate()

        self._drag_offset = None
