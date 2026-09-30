"""Dev-only end-to-end check: real pyautogui fill into a Qt test form on X11."""
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication, QGridLayout, QLineEdit, QWidget

from app.core import form_filler
from app.core.models import FieldFill
from app.ui.dpi import logical_rect_to_region, region_to_logical

KIND = sys.argv[1] if len(sys.argv) > 1 else "browser"
app = QApplication(sys.argv)
print("dpr:", app.primaryScreen().devicePixelRatio())

form = QWidget()
form.setWindowTitle("Test form")
grid = QGridLayout(form)
edits = {}
for r in range(3):
    for c, col in enumerate("ABC"):
        e = QLineEdit()
        e.setFixedWidth(150)
        grid.addWidget(e, r, c)
        edits[f"{col}{r + 2}"] = e
edits["A2"].setText("old value")  # correction case: must be replaced, not appended
form.move(40, 40)
form.show()
for _ in range(20):
    app.processEvents()
    time.sleep(0.05)

values = {
    "A2": "Базовая подготовка", "B2": "20.08.2025", "C2": "20.08.2030",
    "A3": "ГМССБ", "B3": "26.08.2025", "C3": "26.08.2030",
    "A4": "Диплом", "B4": "17.09.2025", "C4": "",
}
fields = []
for name, e in edits.items():
    top_left = e.mapToGlobal(e.rect().topLeft())
    region = logical_rect_to_region(QRect(top_left, e.size()))
    fields.append(FieldFill(label=name, value=values[name], x=region.x, y=region.y,
                            width=region.width, height=region.height))

back, _ = region_to_logical(logical_rect_to_region(QRect(100, 100, 200, 200)))
print("roundtrip logical rect:", back.getRect())

done = threading.Event()
result = {}
def run():
    try:
        result["count"] = form_filler.fill_fields(fields, target_kind=KIND)
    except Exception as exc:  # noqa: BLE001
        result["error"] = repr(exc)
    done.set()
threading.Thread(target=run, daemon=True).start()
while not done.is_set():
    app.processEvents()
    time.sleep(0.02)
for _ in range(10):
    app.processEvents()
    time.sleep(0.05)

print("result:", result)
ok = True
for name, e in edits.items():
    expected = values[name] if values[name] else ""
    actual = e.text()
    mark = "OK " if actual == expected else "BAD"
    ok &= actual == expected
    print(f"{mark} {name}: {actual!r} (expected {expected!r})")
print("ALL OK" if ok else "FAILURES")
