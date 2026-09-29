"""Dev-only helper: render the main window off-screen and save a PNG screenshot.
Not part of the shipped app."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow

app = QApplication(sys.argv)
win = MainWindow()
win.resize(980, 720)
win.show()
app.processEvents()
pixmap = win.grab()
out = Path(__file__).resolve().parent / "preview_main_window.png"
pixmap.save(str(out), "PNG")
print(f"Saved {out}")
