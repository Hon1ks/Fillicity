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
GoToDelay = 0.35
# Longer than Windows' default double-click time (500 ms), so the activation
# click and the first real click on the same spot never merge into a
# double-click (which would put an Excel cell into in-cell edit mode).
ActivationDelay = 0.6

# Top-level window classes of the target app on Windows.
EXCEL_WINDOW_CLASSES = {"XLMAIN"}
GRID_WINDOW_CLASSES = {"SALFRAME"}  # LibreOffice
BROWSER_WINDOW_CLASSES = {"Chrome_WidgetWin_1", "MozillaWindowClass"}  # Chrome/Edge/Opera, Firefox


def fillable(fields: list[FieldFill]) -> list[FieldFill]:
    return [f for f in fields if f.enabled and f.value]


def target_kind_for_class(window_class: str) -> str:
    if window_class in EXCEL_WINDOW_CLASSES:
        return "excel"
    if window_class in GRID_WINDOW_CLASSES:
        return "grid"
    if window_class in BROWSER_WINDOW_CLASSES:
        return "browser"
    return "other"


def clear_keys(kind: str) -> list[tuple[str, ...]]:
    """Keystrokes that empty the clicked field before pasting.

    Never ctrl+a: in Excel it selects the whole sheet (pasting then fills every
    cell) and in Word the whole document.
    - excel/grid: Delete clears exactly the selected cell.
    - browser: End, Shift+Home selects the input's text, which the paste replaces.
    - other: leave existing text alone - selecting "the line" in e.g. Word would
      also grab the field's printed label.
    """
    if kind in ("excel", "grid"):
        return [("delete",)]
    if kind == "browser":
        return [("end",), ("shift", "home")]
    return []


def _window_at(x: int, y: int) -> tuple[int, str]:
    """Top-level window under a screen point and its class (Windows only)."""
    if sys.platform != "win32":
        return 0, ""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.WindowFromPoint.argtypes = [wintypes.POINT]
    user32.WindowFromPoint.restype = wintypes.HWND
    user32.GetAncestor.restype = wintypes.HWND
    hwnd = user32.WindowFromPoint(wintypes.POINT(x, y))
    root = user32.GetAncestor(hwnd, 2) if hwnd else None  # GA_ROOT
    if not root:
        return 0, ""
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(root, buf, 256)
    return int(root), buf.value


def _bring_to_front(hwnd: int) -> bool:
    if not hwnd or sys.platform != "win32":
        return False
    import ctypes

    return bool(ctypes.windll.user32.SetForegroundWindow(hwnd))


def fill_fields(
    fields: list[FieldFill],
    on_progress: Callable[[int, int, FieldFill], None] | None = None,
    abort_check: Callable[[], bool] | None = None,
    target_kind: str | None = None,
    probe: tuple[int, int] | None = None,
) -> int:
    """Fills each field and returns how many were filled.

    `probe` is a screen point inside the captured form, used to find which
    application the form belongs to.
    """
    import pyautogui
    import pyperclip

    pyautogui.FAILSAFE = True
    ordered = fill_order(fillable(fields))
    total = len(ordered)
    if not total:
        return 0
    paste_key = "command" if sys.platform == "darwin" else "ctrl"

    def paste(text: str) -> None:
        pyperclip.copy(text)
        time.sleep(ClipboardDelay)
        pyautogui.hotkey(paste_key, "v")

    # Let our own windows finish hiding, then bring the target app to the front.
    time.sleep(StartDelay)
    kind = target_kind
    hwnd, window_class = _window_at(*(probe or ordered[0].center))
    if kind is None:
        kind = target_kind_for_class(window_class)
    if not _bring_to_front(hwnd):
        # The first click on an inactive window may only activate it. Must
        # happen before any F5: sent to a browser instead, F5 reloads the page.
        pyautogui.click(*(probe or ordered[0].center))
        time.sleep(ActivationDelay)
    if kind == "excel":
        time.sleep(0.2)
        pyautogui.press("esc")  # leave in-cell edit mode / close open menus
    clearing = clear_keys(kind)

    filled = 0
    for index, field in enumerate(ordered, start=1):
        if abort_check and abort_check():
            break

        if kind == "excel" and field.cell:
            # Exact navigation by address via Go To (F5), independent of where
            # the model thought the cell was on screen. The address is pasted,
            # not typed, so a Cyrillic keyboard layout can't garble it.
            pyautogui.press("f5")
            time.sleep(GoToDelay)
            paste(field.cell)
            pyautogui.press("enter")
            time.sleep(ClickDelay)
        else:
            cx, cy = field.center
            pyautogui.moveTo(cx, cy, duration=0.15)
            pyautogui.click(cx, cy)
            time.sleep(ClickDelay)

        for keys in clearing:
            pyautogui.hotkey(*keys)

        # Paste via clipboard instead of pyautogui.typewrite(): typewrite drives
        # raw keyboard-scancode events from a hardcoded US-layout table, so it
        # silently drops any non-ASCII character (Cyrillic, accents, etc.).
        paste(field.value)

        if kind != "excel":
            # Tab rather than Enter: both commit a cell, but Enter in a web
            # form text input submits the whole form after the first field.
            pyautogui.press("tab")

        filled += 1
        if on_progress:
            on_progress(index, total, field)

    return filled
