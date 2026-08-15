"""
icons.py — shared vector icon painting.

The microphone glyph is used by both the floating widget and the tray icon,
so it is rendered from one place. Geometry lives in a 100×100 design space
and is scaled to the target size, keeping edges crisp from a 16 px tray
glyph up to the full-size widget.
"""

from __future__ import annotations

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPen

# ── Design-space geometry (100×100 box, glyph centred at ~50,50) ─────────────
_CAPSULE = QRectF(41.0, 24.0, 18.0, 34.0)   # mic body
_CAPSULE_R = 9.0                            # fully-rounded ends (half width)
_CRADLE = QRectF(29.5, 31.0, 41.0, 33.0)    # U-shaped basket around the body
_STEM_TOP = 64.0                            # cradle nadir → base
_STEM_BOTTOM = 72.0
_BASE_Y = 72.0
_BASE_HALF = 11.5
_STROKE = 3.8
_SHADOW_OFFSET = 2.4


def _mix(base: QColor, other: QColor, t: float) -> QColor:
    """Blend *other* into *base* by fraction *t* (0..1)."""
    return QColor(
        round(base.red() + (other.red() - base.red()) * t),
        round(base.green() + (other.green() - base.green()) * t),
        round(base.blue() + (other.blue() - base.blue()) * t),
    )


def _paint_glyph_flat(painter: QPainter, colour: QColor, brush: QBrush) -> None:
    """Draw the whole glyph in one flat colour (used for the drop shadow)."""
    painter.setPen(QPen(colour, _STROKE, Qt.SolidLine, Qt.RoundCap))
    painter.setBrush(brush)
    painter.drawRoundedRect(_CAPSULE, _CAPSULE_R, _CAPSULE_R)
    painter.setBrush(Qt.NoBrush)
    # NB: in Qt, drawArc(rect, 0, 180*16) renders the TOP half of the ellipse
    # (angles sweep counter-clockwise in the y-down screen space). Starting at
    # 180° and sweeping 180° gives the bottom half — the U-shaped basket.
    painter.drawArc(_CRADLE, 180 * 16, 180 * 16)
    painter.drawLine(QPointF(50.0, _STEM_TOP), QPointF(50.0, _STEM_BOTTOM))
    painter.drawLine(
        QPointF(50.0 - _BASE_HALF, _BASE_Y), QPointF(50.0 + _BASE_HALF, _BASE_Y)
    )


def draw_microphone(painter: QPainter, colour: QColor, size: float) -> None:
    """Draw a polished microphone centred in a *size*×*size* box.

    The painter's origin is treated as the box's top-left corner; callers
    should already have enabled antialiasing.
    """
    scale = size / 100.0
    painter.save()
    painter.scale(scale, scale)

    white = QColor(255, 255, 255)
    black = QColor(0, 0, 0)

    # ── Soft drop shadow for depth ──────────────────────────────────────────
    painter.translate(0.0, _SHADOW_OFFSET)
    _paint_glyph_flat(painter, QColor(0, 0, 0, 80), QBrush(QColor(0, 0, 0, 80)))
    painter.translate(0.0, -_SHADOW_OFFSET)

    # ── Capsule: light→dark vertical gradient with a glassy highlight ───────
    body = QLinearGradient(_CAPSULE.topLeft(), _CAPSULE.bottomLeft())
    body.setColorAt(0.0, _mix(colour, white, 0.42))
    body.setColorAt(0.55, colour)
    body.setColorAt(1.0, _mix(colour, black, 0.22))
    painter.setBrush(QBrush(body))
    painter.setPen(QPen(_mix(colour, black, 0.38), 2.2))
    painter.drawRoundedRect(_CAPSULE, _CAPSULE_R, _CAPSULE_R)

    sheen_top = _CAPSULE.top() + 4.0
    sheen = QLinearGradient(
        QPointF(_CAPSULE.left(), sheen_top), QPointF(_CAPSULE.left(), sheen_top + 12.0)
    )
    sheen.setColorAt(0.0, QColor(255, 255, 255, 130))
    sheen.setColorAt(1.0, QColor(255, 255, 255, 0))
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(sheen))
    painter.drawRoundedRect(QRectF(44.2, sheen_top, 4.6, 12.0), 2.3, 2.3)

    # ── Cradle, stem and base ───────────────────────────────────────────────
    painter.setPen(QPen(colour, _STROKE, Qt.SolidLine, Qt.RoundCap))
    painter.setBrush(Qt.NoBrush)
    painter.drawArc(_CRADLE, 180 * 16, 180 * 16)
    painter.drawLine(QPointF(50.0, _STEM_TOP), QPointF(50.0, _STEM_BOTTOM))
    painter.drawLine(
        QPointF(50.0 - _BASE_HALF, _BASE_Y), QPointF(50.0 + _BASE_HALF, _BASE_Y)
    )

    painter.restore()
