"""Finds a spreadsheet's cell grid in a screenshot, so a cell address the model
read from the headers ("B3") can be turned into an exact on-screen rectangle.

Vision models are poor at pixel coordinates but good at reading the column
letters / row numbers printed in Excel's headers. Gridlines are 1px light
lines between white cells, which is easy to find exactly.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass

CELL_RE = re.compile(r"^\$?([A-Z]{1,3})\$?([0-9]{1,7})$")

# Models sometimes answer with Cyrillic look-alikes ("В3" instead of "B3").
_HOMOGLYPHS = str.maketrans("АВСЕНКМОРТХавсеокмортх", "ABCEHKMOPTXABCEOKMOPTX")


@dataclass
class Grid:
    col_edges: list[int]  # x of each column boundary, left to right
    row_edges: list[int]  # y of each row boundary, top to bottom


def normalize_cell(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip().translate(_HOMOGLYPHS).upper().replace(" ", "")
    return text if CELL_RE.match(text) else None


def split_cell(cell: str) -> tuple[int, int]:
    """'B3' -> (column index 1-based, row 1-based)."""
    m = CELL_RE.match(cell)
    if not m:
        raise ValueError(cell)
    col = 0
    for ch in m.group(1):
        col = col * 26 + (ord(ch) - 64)
    return col, int(m.group(2))


def detect_grid(png_bytes: bytes) -> Grid | None:
    from PIL import Image, ImageChops

    img = Image.open(io.BytesIO(png_bytes)).convert("L")
    w, h = img.size
    if w < 100 or h < 100:
        return None

    white = img.point(lambda v: 255 if v >= 245 else 0)
    line = img.point(lambda v: 255 if 60 <= v < 245 else 0)
    off = ImageChops.offset

    # Gridline pixel: line-coloured with white cells on both sides.
    v_mask = ImageChops.multiply(line, ImageChops.multiply(off(white, 1, 0), off(white, -1, 0)))
    h_mask = ImageChops.multiply(line, ImageChops.multiply(off(white, 0, 1), off(white, 0, -1)))
    # Header border: line-coloured with white only on the cell side.
    v_edge = ImageChops.multiply(line, off(white, -1, 0))
    h_edge = ImageChops.multiply(line, off(white, 0, -1))

    cols = _chain(_peaks(_profile(v_mask, w, h, vertical=True), ratio=0.3), min_gap=12)
    rows = _chain(_peaks(_profile(h_mask, w, h, vertical=False), ratio=0.2), min_gap=8)
    if len(cols) < 2 or len(rows) < 3:
        return None

    # The sheet body is where the column gridlines actually run; anything
    # above/left of it (ribbon, formula bar) is not part of the grid.
    v_bytes, h_bytes = v_mask.tobytes(), h_mask.tobytes()
    body_top = _median([_first_set(v_bytes, w, h, x, vertical=True) for x in cols])
    body_left = _median([_first_set(h_bytes, w, h, y, vertical=False) for y in rows])
    if body_top is None or body_left is None:
        return None
    rows = _fill_gaps([y for y in rows if y > body_top + 2])
    cols = [x for x in cols if x > body_left + 2]
    if len(cols) < 1 or len(rows) < 2:
        return None

    top = _nearest_peak(_profile(h_edge, w, h, vertical=False), body_top, rows[0])
    left = _nearest_peak(_profile(v_edge, w, h, vertical=True), body_left, cols[0])
    rows.insert(0, top)
    cols.insert(0, left)
    return Grid(col_edges=cols, row_edges=rows)


def _profile(mask, w: int, h: int, vertical: bool) -> list[float]:
    from PIL import Image

    size = (w, 1) if vertical else (1, h)
    span = h if vertical else w
    return [v / 255 * span for v in mask.resize(size, Image.BOX).tobytes()]


def _first_set(data: bytes, w: int, h: int, pos: int, vertical: bool) -> int | None:
    if vertical:
        for y in range(h):
            if data[y * w + pos]:
                return y
    else:
        row = data[pos * w:(pos + 1) * w]
        for x, v in enumerate(row):
            if v:
                return x
    return None


def _median(values: list[int | None]) -> int | None:
    vals = sorted(v for v in values if v is not None)
    return vals[len(vals) // 2] if vals else None


def _fill_gaps(lines: list[int]) -> list[int]:
    """Re-insert boundaries hidden under something (a border, an overlay):
    a gap that is ~2x or ~3x the typical row height means rows are missing."""
    if len(lines) < 3:
        return lines
    gaps = sorted(b - a for a, b in zip(lines, lines[1:]))
    step = gaps[len(gaps) // 2]
    out = [lines[0]]
    for nxt in lines[1:]:
        gap = nxt - out[-1]
        k = round(gap / step)
        if k >= 2 and abs(gap - k * step) <= 0.15 * step:
            out.extend(out[-1] + round(gap * i / k) for i in range(1, k))
        out.append(nxt)
    return out


def _nearest_peak(counts: list[float], near: int, first_line: int) -> int:
    """Strongest edge within a few px of where the body starts; falls back to
    the body start itself."""
    lo, hi = max(0, near - 6), min(len(counts), near + 3)
    window = counts[lo:hi]
    if window and max(window) >= 40:
        return lo + window.index(max(window))
    return max(0, min(near - 1, first_line - 1))


def cell_rect(grid: Grid, cell: str, top_left: str = "A1") -> tuple[int, int, int, int] | None:
    col, row = split_cell(cell)
    col0, row0 = split_cell(top_left)
    ci, ri = col - col0, row - row0
    if ci < 0 or ri < 0:
        return None
    if ci + 1 >= len(grid.col_edges) or ri + 1 >= len(grid.row_edges):
        return None
    x0, x1 = grid.col_edges[ci], grid.col_edges[ci + 1]
    y0, y1 = grid.row_edges[ri], grid.row_edges[ri + 1]
    return x0 + 1, y0 + 1, max(1, x1 - x0 - 1), max(1, y1 - y0 - 1)


def cell_at(grid: Grid, x: float, y: float) -> tuple[int, int, int, int] | None:
    """Exact rectangle of the grid cell under a point, if any."""
    cols, rows = grid.col_edges, grid.row_edges
    for i in range(len(cols) - 1):
        if cols[i] <= x < cols[i + 1]:
            break
    else:
        return None
    for j in range(len(rows) - 1):
        if rows[j] <= y < rows[j + 1]:
            break
    else:
        return None
    return cols[i] + 1, rows[j] + 1, max(1, cols[i + 1] - cols[i] - 1), max(1, rows[j + 1] - rows[j] - 1)


def _peaks(counts: list[float], ratio: float) -> list[int]:
    if not counts:
        return []
    best = max(counts)
    if best < 40:
        return []
    threshold = max(40.0, best * ratio)
    peaks = []
    for i, c in enumerate(counts):
        if c >= threshold and (not peaks or i - peaks[-1] > 2):
            peaks.append(i)
        elif c >= threshold and counts[i] > counts[peaks[-1]]:
            peaks[-1] = i
    return peaks


def _chain(lines: list[int], min_gap: int) -> list[int]:
    """Drop lines closer than a row/column could ever be (double borders)."""
    out: list[int] = []
    for x in lines:
        if not out or x - out[-1] >= min_gap:
            out.append(x)
    return out
