"""Actually types the proposed values into the real, on-screen form by driving the
mouse and keyboard (works with any application, not just browsers).
"""
from __future__ import annotations

import sys
import time
from collections.abc import Callable

from app.core.coords import fill_order
from app.core.models import FieldFill

StartDelay = 0.4
ClickDelay = 0.25
ClipboardDelay = 0.08
# Longer than Windows' default double-click time (500 ms), so the activation
# click and the first real click on the same spot never merge into a
# double-click (which would put an Excel cell into in-cell edit mode).
ActivationDelay = 0.6


# Top-level window classes of the foreground app on Windows.
GRID_WINDOW_CLASSES = {"XLMAIN", "SALFRAME"}  # Excel, LibreOffice
BROWSER_WINDOW_CLASSES = {"Chrome_WidgetWin_1", "MozillaWindowClass"}  # Chrome/Edge/Opera, Firefox


def fillable(fields: list[FieldFill]) -> list[FieldFill]:
    return [f for f in fields if f.enabled and f.value]


def target_kind_for_class(window_class: str) -> str:
    if window_class in GRID_WINDOW_CLASSES:
        return "grid"
    if window_class in BROWSER_WINDOW_CLASSES:
        return "browser"
    return "other"


def detect_target_kind() -> str:
    if sys.platform != "win32":
        return "other"
    import ctypes

    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return target_kind_for_class(buf.value)


def clear_keys(kind: str) -> list[tuple[str, ...]]:
    """Keystrokes that empty the clicked field before pasting.

    Never ctrl+a: in Excel it selects the whole sheet (pasting then fills every
    cell) and in Word the whole document.
    - grid: Delete clears exactly the selected cell.
    - browser: End, Shift+Home selects the input's text, which the paste replaces.
    - other: leave existing text alone - selecting "the line" in e.g. Word would
      also grab the field's printed label.
    """
    if kind == "grid":
        return [("delete",)]
    if kind == "browser":
        return [("end",), ("shift", "home")]
    return []


def fill_fields(
    fields: list[FieldFill],
    on_progress: Callable[[int, int, FieldFill], None] | None = None,
    abort_check: Callable[[], bool] | None = None,
    target_kind: str | None = None,
) -> int:
    """Clicks each field and pastes its value. Returns how many fields were filled."""
    import pyautogui
    import pyperclip

    pyautogui.FAILSAFE = True
    ordered = fill_order(fillable(fields))
    total = len(ordered)
    if not total:
        return 0
    paste_key = "command" if _is_mac() else "ctrl"

    # Let our own windows finish hiding, then bring the target app to the
    # front: the first click on an inactive window may only activate it.
    time.sleep(StartDelay)
    pyautogui.click(*ordered[0].center)
    time.sleep(ActivationDelay)
    kind = target_kind or detect_target_kind()
    clearing = clear_keys(kind)

    filled = 0
    for index, field in enumerate(ordered, start=1):
        if abort_check and abort_check():
            break

        cx, cy = field.center
        pyautogui.moveTo(cx, cy, duration=0.15)
        pyautogui.click(cx, cy)
        time.sleep(ClickDelay)

        for keys in clearing:
            pyautogui.hotkey(*keys)

        # Paste via clipboard instead of pyautogui.typewrite(): typewrite drives
        # raw keyboard-scancode events from a hardcoded US-layout table, so it
        # silently drops any non-ASCII character (Cyrillic, accents, etc.).
        pyperclip.copy(field.value)
        time.sleep(ClipboardDelay)
        pyautogui.hotkey(paste_key, "v")

        # Tab rather than Enter: both commit an Excel cell, but Enter in a web
        # form text input submits the whole form after the first field.
        pyautogui.press("tab")

        filled += 1
        if on_progress:
            on_progress(index, total, field)

    return filled


def _is_mac() -> bool:
    import sys

    return sys.platform == "darwin"
