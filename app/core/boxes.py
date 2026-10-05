"""Finds input boxes (text fields, selects, table cells) in a screenshot and
draws numbered tags on them for the model ("Set-of-Marks" prompting).

Vision models are poor at pixel coordinates but reliable at reading a number
printed on the image. So instead of asking "where is the Vessel Name input",
we find every input box ourselves, label them 1..N, and ask "which number".
The click then goes to the exact centre of a box we measured.

An input box, in any app, is a white-ish rectangle enclosed by a border.
"""
from __future__ import annotations

import io
import re

Box = tuple[int, int, int, int]  # x, y, w, h in screenshot pixels

WHITE_MIN = 235
MAX_MARKS = 150


def detect_boxes(png_bytes: bytes) -> list[Box]:
    from PIL import Image

    img = Image.open(io.BytesIO(png_bytes)).convert("L")
    w, h = img.size
    mask = img.point(lambda v: 255 if v >= WHITE_MIN else 0).tobytes()
    gray = img.tobytes()

    parent: list[int] = []

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    # Connected components of white pixels, built from per-row runs.
    runs: list[tuple[int, int, int]] = []  # (y, x0, x1) inclusive
    prev: list[int] = []
    run_re = re.compile(rb"\xff+")
    for y in range(h):
        row = mask[y * w:(y + 1) * w]
        current: list[int] = []
        j = 0
        for m in run_re.finditer(row):
            x0, x1 = m.start(), m.end() - 1
            idx = len(runs)
            runs.append((y, x0, x1))
            parent.append(idx)
            while j < len(prev) and runs[prev[j]][2] < x0:
                j += 1
            k = j
            while k < len(prev) and runs[prev[k]][1] <= x1:
                a, b = find(prev[k]), find(idx)
                if a != b:
                    parent[b] = a
                k += 1
            current.append(idx)
        prev = current

    comps: dict[int, list[int]] = {}
    for idx, (y, x0, x1) in enumerate(runs):
        root = find(idx)
        c = comps.get(root)
        if c is None:
            comps[root] = [x0, y, x1, y, x1 - x0 + 1]
        else:
            c[0] = min(c[0], x0)
            c[1] = min(c[1], y)
            c[2] = max(c[2], x1)
            c[3] = max(c[3], y)
            c[4] += x1 - x0 + 1

    boxes: list[Box] = []
    for x0, y0, x1, y1, area in comps.values():
        bw, bh = x1 - x0 + 1, y1 - y0 + 1
        if not (16 <= bw <= 0.8 * w and 10 <= bh <= 120):
            continue
        if x0 == 0 or y0 == 0 or x1 == w - 1 or y1 == h - 1:
            continue  # touches the screenshot edge: background, not a box
        if area < 0.8 * bw * bh:
            continue  # not rectangular
        if _ring_dark_ratio(gray, w, x0, y0, x1, y1) < 0.7:
            continue  # not enclosed by a border
        boxes.append((x0, y0, bw, bh))
    boxes.sort(key=lambda b: (b[1], b[0]))
    return boxes


def _ring_dark_ratio(gray: bytes, w: int, x0: int, y0: int, x1: int, y1: int) -> float:
    total = dark = 0
    for x in range(x0, x1 + 1):
        for y in (y0 - 1, y1 + 1):
            total += 1
            dark += gray[y * w + x] < WHITE_MIN
    for y in range(y0, y1 + 1):
        for x in (x0 - 1, x1 + 1):
            total += 1
            dark += gray[y * w + x] < WHITE_MIN
    return dark / total if total else 0.0


def box_containing(boxes: list[Box], x: float, y: float) -> int | None:
    for i, (bx, by, bw, bh) in enumerate(boxes):
        if bx <= x < bx + bw and by <= y < by + bh:
            return i
    return None


def draw_marks(image, boxes: list[Box], scale: float):
    """Draws numbered tags (1..N) on a PIL image already downscaled by `scale`
    (original px = image px * scale). Returns the same image."""
    from PIL import ImageDraw, ImageFont

    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.load_default(size=12)
    except TypeError:  # very old Pillow
        font = ImageFont.load_default()
    for number, (x, y, bw, bh) in enumerate(boxes, start=1):
        label = str(number)
        left, top = x / scale + 1, y / scale + 1
        tw = draw.textlength(label, font=font)
        draw.rectangle([left, top, left + tw + 5, top + 13], fill=(220, 30, 30))
        draw.text((left + 3, top), label, fill="white", font=font)
    return image
