import base64
import io

import pytest
from PIL import Image

from app.core import ai_engine
from app.core.ai_engine import AIEngineError, _parse_json, _prepare_screenshot, parse_fields
from app.core.coords import downscale_size, fill_order, logical_to_physical, physical_to_logical
from app.core.form_filler import fillable
from app.core.models import CaptureRegion, FieldFill


def cell(label, x, y, w=100, h=20, value="v"):
    return FieldFill(label=label, value=value, x=x, y=y, width=w, height=h)


def test_fill_order_is_bottom_up_right_to_left():
    # 2x3 grid like the Excel sheet: rows at y=100/120, columns A/B/C.
    fields = [
        cell("A2", 0, 100), cell("B2", 100, 101), cell("C2", 200, 99),
        cell("A3", 0, 120), cell("B3", 100, 121), cell("C3", 200, 119),
    ]
    assert [f.label for f in fill_order(fields)] == ["C3", "B3", "A3", "C2", "B2", "A2"]


def test_fillable_skips_disabled_and_empty():
    a, b, c = cell("a", 0, 0), cell("b", 0, 0, value=""), cell("c", 0, 0)
    c.enabled = False
    assert fillable([a, b, c]) == [a]


@pytest.mark.parametrize("dpr", [1.0, 1.25, 1.5, 2.0])
def test_logical_physical_roundtrip(dpr):
    origin = 1920
    for value in (1920, 2000, 2345):
        phys = logical_to_physical(value, origin, dpr)
        assert abs(physical_to_logical(phys, origin, dpr) - value) <= 1


def test_logical_to_physical_scales_relative_to_screen_origin():
    assert logical_to_physical(100, 0, 1.5) == 150
    assert logical_to_physical(1920 + 100, 1920, 1.5) == 1920 + 150


def test_downscale_size():
    assert downscale_size(800, 600, 1568) == (800, 600, 1.0)
    w, h, scale = downscale_size(1920, 1080, 1568)
    assert (w, h) == (1568, 882)
    assert scale == pytest.approx(1920 / 1568)


def test_prepare_screenshot_downscales_large_images():
    img = Image.new("RGB", (3000, 1500), "white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    sent_b64, w, h, scale = _prepare_screenshot(buf.getvalue(), 3000, 1500)
    assert (w, h) == (1568, 784)
    assert Image.open(io.BytesIO(base64.standard_b64decode(sent_b64))).size == (1568, 784)
    assert scale == pytest.approx(3000 / 1568)


def test_parse_fields_maps_back_to_physical_and_drops_out_of_bounds():
    region = CaptureRegion(x=10, y=20, width=2000, height=1000)
    data = {"fields": [
        {"label": "Имя", "value": "Иван", "x": 100, "y": 50, "width": 40, "height": 10},
        {"label": "outside", "value": "x", "x": 5000, "y": 50, "width": 40, "height": 10},
        {"label": "bad", "value": "x", "x": "?", "y": 1},
        {"label": "null", "value": None, "x": 1, "y": 1},
        "garbage",
    ]}
    fields = parse_fields(data, region, 2.0, 2000, 1000)
    assert [f.label for f in fields] == ["Имя", "null"]
    assert (fields[0].x, fields[0].y, fields[0].width, fields[0].height) == (210, 120, 80, 20)
    assert fields[1].value == ""


@pytest.mark.parametrize("raw", [
    '{"fields": [], "notes": "ok"}',
    '```json\n{"fields": [], "notes": "ok"}\n```',
    'Let me look at the form {first} ... here it is: {"fields": [], "notes": "ok"} done',
])
def test_parse_json_tolerates_wrapping(raw):
    assert _parse_json(raw)["notes"] == "ok"


def test_parse_json_rejects_prose():
    with pytest.raises(AIEngineError):
        _parse_json("Let me analyze this Noon Report Form and 1. **Vessel Name**")


def test_analyze_requires_key():
    with pytest.raises(AIEngineError):
        ai_engine.analyze("", CaptureRegion(0, 0, 10, 10), "", 10, 10, [])


def test_clear_keys_never_select_all():
    from app.core.form_filler import clear_keys, target_kind_for_class

    assert target_kind_for_class("XLMAIN") == "grid"
    assert target_kind_for_class("SALFRAME") == "grid"
    assert target_kind_for_class("Chrome_WidgetWin_1") == "browser"
    assert target_kind_for_class("OpusApp") == "other"  # Word
    for kind in ("grid", "browser", "other"):
        assert ("ctrl", "a") not in clear_keys(kind)
    assert clear_keys("grid") == []  # paste into a selected cell replaces it
    for kind in ("grid", "browser", "other"):
        assert ("delete",) not in clear_keys(kind)  # a failed paste must not erase
    assert clear_keys("other") == []


# ---------------------------------------------------------------- grid

GRIDLINE, HEADER, HEADER_SEP = (218, 220, 221), (223, 227, 232), (177, 181, 186)
COL_EDGES = [30, 220, 315, 435, 499, 563, 627, 691, 755, 819]
ROW_TOP, ROW_H, N_ROWS = 110, 20, 30


def excel_like_png(hide_row_line: int | None = None) -> bytes:
    from PIL import ImageDraw

    w, h = 900, ROW_TOP + ROW_H * N_ROWS + 30
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    # ribbon + formula bar: a white box with a gray frame, above the headers
    d.rectangle([0, 0, w, 85], fill=(230, 233, 238))
    d.rectangle([60, 60, w - 20, 80], fill="white", outline=(180, 180, 180))
    # column header band and row header band
    d.rectangle([0, 90, w, ROW_TOP - 1], fill=HEADER)
    d.rectangle([0, 90, COL_EDGES[0] - 1, h], fill=HEADER)
    d.line([0, ROW_TOP - 1, w, ROW_TOP - 1], fill=HEADER_SEP)
    d.line([COL_EDGES[0] - 1, 90, COL_EDGES[0] - 1, h], fill=HEADER_SEP)
    for x in COL_EDGES[1:]:
        d.line([x, ROW_TOP, x, h], fill=GRIDLINE)
        d.line([x, 90, x, ROW_TOP - 1], fill=HEADER_SEP)
    for r in range(1, N_ROWS + 1):
        y = ROW_TOP + r * ROW_H
        d.line([COL_EDGES[0], y, w, y], fill=GRIDLINE)
    # a bordered table (black) and a green-filled row, like the user's sheet
    d.rectangle([COL_EDGES[0], ROW_TOP, COL_EDGES[3], ROW_TOP + 10 * ROW_H], outline="black")
    for x in COL_EDGES[1:3]:
        d.line([x, ROW_TOP, x, ROW_TOP + 10 * ROW_H], fill="black")
    d.rectangle([COL_EDGES[0] + 1, ROW_TOP + 8 * ROW_H + 1, COL_EDGES[3] - 1,
                 ROW_TOP + 9 * ROW_H - 1], fill=(216, 228, 188))
    if hide_row_line is not None:  # something covering a row boundary
        y = ROW_TOP + hide_row_line * ROW_H
        d.rectangle([COL_EDGES[0] + 1, y - 3, w, y + 3], fill=(120, 100, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.parametrize("hidden", [None, 3])
def test_detect_grid_finds_exact_cells(hidden):
    from app.core.grid import cell_rect, detect_grid

    grid = detect_grid(excel_like_png(hide_row_line=hidden))
    assert grid is not None
    assert grid.col_edges[:len(COL_EDGES)] == [COL_EDGES[0] - 1] + COL_EDGES[1:]
    assert grid.row_edges[0] == ROW_TOP - 1
    assert grid.row_edges[1:6] == [ROW_TOP + ROW_H * i for i in range(1, 6)]
    x, y, w, h = cell_rect(grid, "B3")
    assert (x, y) == (COL_EDGES[1] + 1, ROW_TOP + 2 * ROW_H + 1)
    assert (w, h) == (COL_EDGES[2] - COL_EDGES[1] - 1, ROW_H - 1)
    # scrolled sheet: first visible cell is C5, so C5 is the top-left cell
    assert cell_rect(grid, "C5", top_left="C5")[:2] == (COL_EDGES[0], ROW_TOP)
    assert cell_rect(grid, "A1", top_left="C5") is None


def test_detect_grid_rejects_non_spreadsheet():
    from app.core.grid import detect_grid

    img = Image.new("RGB", (400, 300), (40, 40, 50))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    assert detect_grid(buf.getvalue()) is None


def test_normalize_cell_handles_cyrillic_lookalikes():
    from app.core.grid import normalize_cell, split_cell

    assert normalize_cell("В3") == "B3"  # Cyrillic В
    assert normalize_cell(" c10 ") == "C10"
    assert split_cell(normalize_cell("$A$1")) == (1, 1)
    assert normalize_cell("Дата") is None
    assert normalize_cell(None) is None
    assert split_cell("AA12") == (27, 12)


def test_place_fields_snaps_cells_to_grid():
    from app.core.ai_engine import parse_fields, place_fields
    from app.core.grid import detect_grid

    png = excel_like_png()
    region = CaptureRegion(x=100, y=50, width=900, height=ROW_TOP + ROW_H * N_ROWS + 30)
    data = {"top_left_cell": "A1", "fields": [
        # model's pixel guess is far off, but the address is right
        {"label": "Дата", "value": "20.08.2025", "cell": "В3", "x": 600, "y": 500,
         "width": 50, "height": 10},
        {"label": "no coords", "value": "x", "cell": "C4"},
        {"label": "plain", "value": "y", "x": 10, "y": 10, "width": 5, "height": 5},
    ]}
    fields = parse_fields(data, region, 1.0, region.width, region.height)
    place_fields(fields, data, region, detect_grid(png), [])
    by_label = {f.label: f for f in fields}
    b3 = by_label["Дата"]
    assert b3.cell == "B3"
    assert (b3.x, b3.y) == (100 + COL_EDGES[1] + 1, 50 + ROW_TOP + 2 * ROW_H + 1)
    c4 = by_label["no coords"]
    assert (c4.x, c4.y) == (100 + COL_EDGES[2] + 1, 50 + ROW_TOP + 3 * ROW_H + 1)
    # no address and the guess is outside the grid: left where the model said
    assert (by_label["plain"].x, by_label["plain"].y) == (110, 60)



# ---------------------------------------------------------------- input boxes

FORM_BOXES = [(200, 40, 160, 22), (200, 80, 160, 22), (200, 120, 60, 22), (290, 120, 60, 22),
              (200, 160, 300, 80)]


def web_form_png() -> bytes:
    """A browser-like form: labels, bordered inputs, a gray button, a checkbox."""
    from PIL import ImageDraw

    img = Image.new("RGB", (640, 320), "white")
    d = ImageDraw.Draw(img)
    for i, (x, y, w, h) in enumerate(FORM_BOXES):
        d.text((20, y + 4), f"Label {i}", fill="black")
        d.rectangle([x - 1, y - 1, x + w, y + h], outline=(118, 118, 118))
    d.rectangle([20, 270, 120, 300], fill=(225, 225, 225), outline=(118, 118, 118))  # button
    d.rectangle([380, 42, 392, 54], outline=(118, 118, 118))  # checkbox: too small
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_detect_boxes_finds_inputs_only():
    from app.core.boxes import detect_boxes

    assert detect_boxes(web_form_png()) == FORM_BOXES


def test_marks_are_drawn_on_the_image_sent_to_the_model():
    from app.core.ai_engine import _prepare_screenshot

    png = web_form_png()
    plain, *_ = _prepare_screenshot(png, 640, 320, [])
    marked, w, h, scale = _prepare_screenshot(png, 640, 320, FORM_BOXES)
    assert (w, h, scale) == (640, 320, 1.0)
    img = Image.open(io.BytesIO(base64.standard_b64decode(marked))).convert("RGB")
    x, y, _, _ = FORM_BOXES[0]
    assert img.getpixel((x + 2, y + 2)) == (220, 30, 30)  # red tag in the corner
    assert plain != marked


def test_place_fields_uses_box_number_and_snaps_guesses_into_boxes():
    from app.core.ai_engine import parse_fields, place_fields

    region = CaptureRegion(x=1000, y=500, width=640, height=320)
    data = {"fields": [
        {"label": "picked", "value": "a", "box": 2, "x": 5, "y": 5, "width": 5, "height": 5},
        {"label": "guess", "value": "b", "x": 300, "y": 125, "width": 20, "height": 10},
        {"label": "bad box", "value": "c", "box": 99, "x": 600, "y": 300, "width": 4, "height": 4},
    ]}
    fields = parse_fields(data, region, 1.0, 640, 320, len(FORM_BOXES))
    place_fields(fields, data, region, None, FORM_BOXES)
    by = {f.label: f for f in fields}
    assert (by["picked"].x, by["picked"].y, by["picked"].width) == (1200, 580, 160)
    assert by["guess"].box == 4 and (by["guess"].x, by["guess"].y) == (1290, 620)
    assert by["bad box"].box == 0 and (by["bad box"].x, by["bad box"].y) == (1600, 800)


def test_unanchored_fields_are_flagged():
    from app.core.ai_engine import parse_fields, place_fields

    region = CaptureRegion(x=0, y=0, width=640, height=320)
    data = {"fields": [
        {"label": "in box", "value": "a", "box": 1, "x": 1, "y": 1},
        {"label": "nowhere", "value": "b", "x": 600, "y": 300, "width": 4, "height": 4},
    ]}
    fields = parse_fields(data, region, 1.0, 640, 320, len(FORM_BOXES))
    place_fields(fields, data, region, None, FORM_BOXES)
    assert [f.anchored for f in fields] == [True, False]



def test_paste_uses_layout_independent_key_codes(monkeypatch):
    """Under a Russian layout pyautogui can't map "v" and sends nothing; the
    paste must go out as the V virtual-key code instead."""
    import types

    from app.core import form_filler

    events = []
    user32 = types.SimpleNamespace(
        MapVirtualKeyW=lambda vk, kind: vk + 1000,
        keybd_event=lambda vk, scan, flags, extra: events.append((vk, flags)),
    )
    fake_ctypes = types.SimpleNamespace(windll=types.SimpleNamespace(user32=user32))
    monkeypatch.setattr(form_filler.sys, "platform", "win32")
    monkeypatch.setitem(__import__("sys").modules, "ctypes", fake_ctypes)
    form_filler.press_paste()
    assert events == [(0x11, 0), (0x56, 0), (0x56, 2), (0x11, 2)]
