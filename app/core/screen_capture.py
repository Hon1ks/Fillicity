"""Grab a screenshot of a screen region using mss (fast, cross-platform, multi-monitor)."""
from __future__ import annotations

import base64
import io

from app.core.models import CaptureRegion


def capture_region(region: CaptureRegion) -> tuple[bytes, str]:
    """Returns (png_bytes, base64_str) for the given absolute-desktop region."""
    import mss
    from PIL import Image

    with mss.mss() as sct:
        monitor = {
            "left": region.x,
            "top": region.y,
            "width": region.width,
            "height": region.height,
        }
        shot = sct.grab(monitor)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()
    return png_bytes, base64.standard_b64encode(png_bytes).decode("ascii")


def virtual_desktop_bounds() -> CaptureRegion:
    """The bounding box that covers every connected monitor."""
    import mss

    with mss.mss() as sct:
        m = sct.monitors[0]  # index 0 = union of all monitors in mss
        return CaptureRegion(x=m["left"], y=m["top"], width=m["width"], height=m["height"])
