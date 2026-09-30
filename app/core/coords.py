"""Coordinate math shared by capture, overlay and filling.

Fillicity keeps every stored coordinate in *physical* screen pixels (what mss
captures and what pyautogui clicks). Qt widgets use *logical* pixels, which
differ from physical ones whenever Windows display scaling isn't 100%. Qt 6
scales each screen around its own native top-left corner, so conversion is
linear relative to that origin.
"""
from __future__ import annotations

from app.core.models import FieldFill


def logical_to_physical(value: float, origin: int, dpr: float) -> int:
    return origin + round((value - origin) * dpr)


def physical_to_logical(value: float, origin: int, dpr: float) -> int:
    return origin + round((value - origin) / dpr)


def downscale_size(width: int, height: int, max_side: int) -> tuple[int, int, float]:
    """Returns (new_width, new_height, scale) where scale maps new -> original."""
    longest = max(width, height)
    if longest <= max_side:
        return width, height, 1.0
    factor = max_side / longest
    new_w, new_h = max(1, round(width * factor)), max(1, round(height * factor))
    return new_w, new_h, width / new_w


def fill_order(fields: list[FieldFill]) -> list[FieldFill]:
    """Bottom-to-top rows, right-to-left within a row.

    Filling a cell can make the host app reflow (Excel auto-fits row heights /
    column widths). Reflow only moves content below or to the right of the
    edited cell, so going in reverse reading order means every shift lands on
    cells that are already filled, never on ones still waiting to be clicked.
    """
    rows: list[list[FieldFill]] = []
    for field in sorted(fields, key=lambda f: f.center[1], reverse=True):
        cy = field.center[1]
        for row in rows:
            anchor = row[0]
            tolerance = max(4, min(anchor.height, field.height) // 2)
            if abs(anchor.center[1] - cy) <= tolerance:
                row.append(field)
                break
        else:
            rows.append([field])
    ordered: list[FieldFill] = []
    for row in rows:
        ordered.extend(sorted(row, key=lambda f: f.center[0], reverse=True))
    return ordered
