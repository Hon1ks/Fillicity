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
    b64 = base64.standard_b64encode(buf.getvalue()).decode()
    sent_b64, w, h, scale = _prepare_screenshot(b64, 3000, 1500)
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
    assert target_kind_for_class("Chrome_WidgetWin_1") == "browser"
    assert target_kind_for_class("OpusApp") == "other"  # Word
    for kind in ("grid", "browser", "other"):
        assert ("ctrl", "a") not in clear_keys(kind)
    assert clear_keys("grid") == [("delete",)]
    assert clear_keys("other") == []
