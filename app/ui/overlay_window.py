"""The 'Google-Translate-style' overlay: transparent boxes drawn on top of the real
form showing what the AI is about to type into each field, plus a small floating
toolbar with the actual Fill / Hide actions.
"""
from __future__ import annotations

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from app.core.models import CaptureRegion, FieldFill
from app.ui import theme


class OverlayCanvas(QWidget):
    """Transparent, click-through layer that draws a proposed-value badge over
    each detected field. Sits exactly on top of the captured screen region."""

    def __init__(self, region: CaptureRegion, fields: list[FieldFill]) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(region.x, region.y, region.width, region.height)
        self._origin = (region.x, region.y)
        self.fields = fields

    def set_fields(self, fields: list[FieldFill]) -> None:
        self.fields = fields
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        ox, oy = self._origin

        box_pen = QPen(QColor(theme.ACCENT))
        box_pen.setWidth(2)
        font = QFont("Segoe UI", 10)
        painter.setFont(font)
        metrics = QFontMetrics(font)

        for field in self.fields:
            local = QRect(field.x - ox, field.y - oy, field.width, field.height)

            painter.setPen(box_pen)
            painter.setBrush(QColor(124, 92, 252, 40))
            painter.drawRoundedRect(local, 6, 6)

            if not field.value:
                continue

            text = field.value
            text_w = metrics.horizontalAdvance(text) + 16
            text_h = metrics.height() + 8
            badge = QRect(local.x(), local.y() - text_h - 4, max(text_w, 40), text_h)
            if badge.y() < 0:
                badge.moveTop(local.bottom() + 4)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(29, 29, 39, 235))
            painter.drawRoundedRect(badge, 6, 6)
            painter.setPen(QColor(theme.TEXT))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, text)


class FloatingToolbar(QWidget):
    """Small always-on-top control strip anchored near the top of the region."""

    fill_clicked = Signal()
    close_clicked = Signal()

    def __init__(self, region: CaptureRegion, field_count: int) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(theme.STYLESHEET)

        bar = QWidget(self)
        bar.setObjectName("Card")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        self.label = QLabel(f"Найдено полей: {field_count}")
        self.label.setObjectName("StatusLabel")
        layout.addWidget(self.label)

        fill_btn = QPushButton("✅ Заполнить")
        fill_btn.setObjectName("Success")
        fill_btn.clicked.connect(self.fill_clicked.emit)
        layout.addWidget(fill_btn)

        close_btn = QPushButton("✖ Скрыть")
        close_btn.setObjectName("Ghost")
        close_btn.clicked.connect(self.close_clicked.emit)
        layout.addWidget(close_btn)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(bar)

        width = 260 if field_count else 220
        self.setGeometry(region.x + region.width - width - 12, max(region.y - 56, 8), width, 48)

    def set_field_count(self, count: int) -> None:
        self.label.setText(f"Найдено полей: {count}")
