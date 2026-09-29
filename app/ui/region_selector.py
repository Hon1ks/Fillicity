"""Full-desktop, drag-to-select overlay used to pick which screen area to watch."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QKeyEvent, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget

from app.core.models import CaptureRegion


class RegionSelector(QWidget):
    """Semi-transparent full-desktop overlay for dragging out a rectangle."""

    region_selected = Signal(object)  # CaptureRegion
    cancelled = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)

        geo = self._virtual_desktop_geometry()
        self.setGeometry(geo)
        self._origin_x, self._origin_y = geo.x(), geo.y()

        self._start: QPoint | None = None
        self._current: QPoint | None = None

    @staticmethod
    def _virtual_desktop_geometry() -> QRect:
        rect = QRect()
        for screen in QGuiApplication.screens():
            rect = rect.united(screen.geometry())
        return rect

    def showEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        self.activateWindow()
        self.raise_()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(10, 10, 15, 110))

        if self._start and self._current:
            selection = QRect(self._start, self._current).normalized()
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(selection, Qt.GlobalColor.transparent)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            pen = QPen(QColor("#7C5CFC"))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(selection)

            size_text = f"{selection.width()} x {selection.height()}"
            painter.setPen(QColor("#EDEDF4"))
            painter.drawText(selection.x() + 6, max(selection.y() - 8, 14), size_text)

        painter.setPen(QColor("#EDEDF4"))
        painter.drawText(
            self.rect().adjusted(0, 24, 0, 0),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            "Выделите область формы (ЛКМ + перетаскивание) · Esc — отмена",
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._start = event.position().toPoint()
            self._current = self._start
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._start is not None:
            self._current = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._start is not None:
            selection = QRect(self._start, event.position().toPoint()).normalized()
            self._start = None
            self._current = None
            if selection.width() < 8 or selection.height() < 8:
                self.update()
                return
            region = CaptureRegion(
                x=self._origin_x + selection.x(),
                y=self._origin_y + selection.y(),
                width=selection.width(),
                height=selection.height(),
            )
            self.close()
            self.region_selected.emit(region)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            self.cancelled.emit()
