"""Dev-only end-to-end check of numbered-box placement on a real widget form:
capture -> detect boxes -> model answers by box number only (with deliberately
wrong pixels) -> place_fields -> real pyautogui fill -> verify."""
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication, QFormLayout, QLineEdit, QStyleFactory, QWidget

from app.core import form_filler, screen_capture
from app.core.ai_engine import parse_fields, place_fields
from app.core.boxes import box_containing, detect_boxes
from app.ui.dpi import logical_rect_to_region

app = QApplication(sys.argv)
app.setStyle(QStyleFactory.create("Fusion"))
form = QWidget()
form.setStyleSheet("background: white;")
layout = QFormLayout(form)
labels = ["Vessel Name", "IMO Number", "Call Sign", "Capitan", "Remarks"]
edits = {}
for name in labels:
    e = QLineEdit()
    e.setFixedWidth(220)
    e.setStyleSheet("QLineEdit { border: 1px solid #767676; background: white; }")
    layout.addRow(name, e)
    edits[name] = e
form.move(60, 60)
form.show()
for _ in range(20):
    app.processEvents()
    time.sleep(0.05)

frame = QRect(form.mapToGlobal(form.rect().topLeft()), form.size())
region = logical_rect_to_region(frame)
png, _ = screen_capture.capture_region(region)
boxes = detect_boxes(png)
print("dpr", app.primaryScreen().devicePixelRatio(), "region", region, "boxes", len(boxes))

# What the model would answer: just the box number of each field.
values = {"Vessel Name": "MV Северный", "IMO Number": "9876543",
          "Call Sign": "UBCD7", "Capitan": "Иванов И.И.", "Remarks": ""}
answer = []
for name, e in edits.items():
    r = logical_rect_to_region(QRect(e.mapToGlobal(e.rect().topLeft()), e.size()))
    i = box_containing(boxes, r.x - region.x + r.width / 2, r.y - region.y + r.height / 2)
    print(f"  {name}: widget at {r.x - region.x},{r.y - region.y} -> box {None if i is None else i + 1}")
    answer.append({"label": name, "value": values[name], "box": 0 if i is None else i + 1,
                   "x": 3, "y": 3, "width": 10, "height": 10})  # wrong pixels on purpose
data = {"fields": answer}
fields = parse_fields(data, region, 1.0, region.width, region.height, len(boxes))
place_fields(fields, data, region, None, boxes)

done = threading.Event()
result = {}
threading.Thread(target=lambda: (result.update(n=form_filler.fill_fields(fields, target_kind="browser")), done.set()),
                 daemon=True).start()
while not done.is_set():
    app.processEvents()
    time.sleep(0.02)
for _ in range(10):
    app.processEvents()
    time.sleep(0.05)
ok = all(edits[n].text() == values[n] for n in labels)
for n in labels:
    print(("OK " if edits[n].text() == values[n] else "BAD"), n, repr(edits[n].text()))
print("filled", result, "ALL OK" if ok else "FAILURES")
