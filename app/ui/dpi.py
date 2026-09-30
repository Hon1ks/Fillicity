"""Bridges Qt's logical pixels and the physical pixels stored everywhere else."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QGuiApplication, QScreen

from app.core.coords import logical_to_physical, physical_to_logical
from app.core.models import CaptureRegion


def _screen_at_logical(x: int, y: int) -> QScreen:
    return QGuiApplication.screenAt(QPoint(x, y)) or QGuiApplication.primaryScreen()


def _screen_at_physical(x: int, y: int) -> QScreen:
    for screen in QGuiApplication.screens():
        g, dpr = screen.geometry(), screen.devicePixelRatio()
        if g.x() <= x < g.x() + g.width() * dpr and g.y() <= y < g.y() + g.height() * dpr:
            return screen
    return QGuiApplication.primaryScreen()


def logical_rect_to_region(rect: QRect) -> CaptureRegion:
    screen = _screen_at_logical(rect.x(), rect.y())
    g, dpr = screen.geometry(), screen.devicePixelRatio()
    return CaptureRegion(
        x=logical_to_physical(rect.x(), g.x(), dpr),
        y=logical_to_physical(rect.y(), g.y(), dpr),
        width=max(1, round(rect.width() * dpr)),
        height=max(1, round(rect.height() * dpr)),
    )


def region_to_logical(region: CaptureRegion) -> tuple[QRect, float]:
    """Logical rect covering the region, plus the dpr used to map into it."""
    screen = _screen_at_physical(region.x, region.y)
    g, dpr = screen.geometry(), screen.devicePixelRatio()
    rect = QRect(
        physical_to_logical(region.x, g.x(), dpr),
        physical_to_logical(region.y, g.y(), dpr),
        max(1, round(region.width / dpr)),
        max(1, round(region.height / dpr)),
    )
    return rect, dpr
