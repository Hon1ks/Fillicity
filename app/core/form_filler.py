"""Actually types the proposed values into the real, on-screen form by driving the
mouse and keyboard (works with any application, not just browsers).
"""
from __future__ import annotations

import time
from collections.abc import Callable

from app.core.models import FieldFill

ClickDelay = 0.25
TypeInterval = 0.02


def fill_fields(
    fields: list[FieldFill],
    on_progress: Callable[[int, int, FieldFill], None] | None = None,
    abort_check: Callable[[], bool] | None = None,
) -> int:
    """Clicks each field and types its value. Returns how many fields were filled."""
    import pyautogui

    pyautogui.FAILSAFE = True
    filled = 0
    total = len(fields)

    for index, field in enumerate(fields, start=1):
        if abort_check and abort_check():
            break
        if not field.value:
            continue

        cx, cy = field.center
        pyautogui.moveTo(cx, cy, duration=0.15)
        pyautogui.click(cx, cy)
        time.sleep(ClickDelay)

        # Deliberately NOT ctrl+a: in grid apps like Excel a plain click only
        # selects the cell (no text-edit mode), so ctrl+a is "select all cells"
        # rather than "select this field's text" - it was clearing the whole
        # sheet/table instead of just the target cell. A single Delete clears
        # exactly the active cell/selection in both spreadsheets and normal
        # text inputs, which is what we actually want here.
        pyautogui.press("delete")
        pyautogui.typewrite(field.value, interval=TypeInterval)
        pyautogui.press("enter")

        filled += 1
        if on_progress:
            on_progress(index, total, field)

    return filled
