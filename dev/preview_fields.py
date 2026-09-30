"""Dev-only: render main window with a fake plan + settings dialog to PNG."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication

from app.core.models import CaptureRegion, FieldFill, FillPlan
from app.ui import theme
from app.ui.main_window import MainWindow
from app.ui.settings_dialog import SettingsDialog

app = QApplication(sys.argv)
win = MainWindow()
win.region = CaptureRegion(0, 0, 900, 500)
plan = FillPlan(region=win.region, notes="Заполнены пустые ячейки по данным из файла.", fields=[
    FieldFill("Подготовка (A2)", "Базовая подготовка", 30, 200, 190, 20),
    FieldFill("Дата выдачи (B2)", "20.08.2025", 220, 200, 95, 20),
    FieldFill("Действителен до (C2)", "20.08.2030", 318, 200, 115, 20),
    FieldFill("Подготовка (A3)", "", 30, 220, 190, 20),
])
win._on_analysis_done(plan)
win._close_overlay()
item = win.fields_table.item(2, 1)
item.setText("21.08.2030")
win.fields_table.item(0, 0).setCheckState(win.fields_table.item(0, 0).checkState().__class__.Unchecked)
print("edited value:", plan.fields[2].value, "| A2 enabled:", plan.fields[0].enabled,
      "| A3 enabled:", plan.fields[3].enabled, "| fill btn:", win.fill_btn.isEnabled())
win.show()
app.processEvents()
win.grab().save("dev/preview_fields.png")
dlg = SettingsDialog()
dlg.setStyleSheet(theme.STYLESHEET)
dlg.show()
app.processEvents()
dlg.grab().save("dev/preview_settings.png")
print("saved")
