from __future__ import annotations

import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core import config, data_loader, screen_capture
from app.core.data_loader import UnsupportedFileError
from app.core.models import CaptureRegion, FillPlan, SourceDocument
from app.ui import theme
from app.ui.overlay_window import FloatingToolbar, OverlayCanvas
from app.ui.region_selector import RegionSelector
from app.ui.settings_dialog import SettingsDialog
from app.ui.workers import AnalyzeWorker, FillWorker

FILE_FILTER = (
    "Поддерживаемые файлы (*.md *.txt *.csv *.xlsx *.xlsm *.docx *.pdf "
    "*.png *.jpg *.jpeg *.webp *.bmp *.gif)"
)


def _card(title: str) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("Card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(10)
    label = QLabel(title)
    label.setObjectName("SectionTitle")
    layout.addWidget(label)
    return frame, layout


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Fillicity")
        self.resize(980, 720)
        self.setStyleSheet(theme.STYLESHEET)

        self.region: CaptureRegion | None = None
        self.screenshot_png: bytes | None = None
        self.screenshot_b64: str = ""
        self.screenshot_size: tuple[int, int] = (0, 0)
        self.sources: list[SourceDocument] = []
        self.plan: FillPlan | None = None

        self._region_selector: RegionSelector | None = None
        self._overlay_canvas: OverlayCanvas | None = None
        self._toolbar: FloatingToolbar | None = None
        self._analyze_worker: AnalyzeWorker | None = None
        self._fill_worker: FillWorker | None = None

        self._build_ui()
        self._refresh_states()

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        root.addLayout(self._build_header())

        grid = QGridLayout()
        grid.setSpacing(16)
        grid.addWidget(self._build_capture_card(), 0, 0)
        grid.addWidget(self._build_data_card(), 0, 1)
        grid.addWidget(self._build_recognize_card(), 1, 0)
        grid.addWidget(self._build_fill_card(), 1, 1)
        root.addLayout(grid, stretch=1)

        root.addWidget(self._build_log_panel())

    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setObjectName("Header")
        text_col = QVBoxLayout()
        title = QLabel("Fillicity")
        title.setObjectName("TitleLabel")
        subtitle = QLabel("AI-автозаполнение любых форм и документов на экране")
        subtitle.setObjectName("SubtitleLabel")
        text_col.addWidget(title)
        text_col.addWidget(subtitle)
        row.addLayout(text_col)
        row.addStretch(1)

        settings_btn = QPushButton("⚙ Настройки")
        settings_btn.setObjectName("Ghost")
        settings_btn.clicked.connect(self._open_settings)
        row.addWidget(settings_btn, alignment=Qt.AlignmentFlag.AlignTop)
        return row

    def _build_capture_card(self) -> QFrame:
        frame, layout = _card("1. Показать экран")

        btn_row = QHBoxLayout()
        select_btn = QPushButton("🖵 Выбрать область")
        select_btn.setObjectName("Primary")
        select_btn.clicked.connect(self._start_region_selection)
        full_btn = QPushButton("🖥 Весь экран")
        full_btn.setObjectName("Ghost")
        full_btn.clicked.connect(self._capture_full_screen)
        btn_row.addWidget(select_btn)
        btn_row.addWidget(full_btn)
        layout.addLayout(btn_row)

        self.region_status = QLabel("Область экрана ещё не выбрана")
        self.region_status.setObjectName("StatusLabel")
        self.region_status.setWordWrap(True)
        layout.addWidget(self.region_status)

        self.preview_label = QLabel()
        self.preview_label.setFixedHeight(140)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet(
            f"background-color: {theme.PANEL_ALT}; border: 1px dashed {theme.BORDER}; "
            "border-radius: 8px; color: #6C6C7C;"
        )
        self.preview_label.setText("Превью появится здесь")
        layout.addWidget(self.preview_label, stretch=1)

        rescan_btn = QPushButton("🔄 Обновить снимок")
        rescan_btn.setObjectName("Ghost")
        rescan_btn.clicked.connect(self._rescan_region)
        self.rescan_btn = rescan_btn
        layout.addWidget(rescan_btn)
        return frame

    def _build_data_card(self) -> QFrame:
        frame, layout = _card("2. Данные для заполнения")

        add_btn = QPushButton("📎 Добавить файл или изображение")
        add_btn.setObjectName("Primary")
        add_btn.clicked.connect(self._add_source_files)
        layout.addWidget(add_btn)

        hint = QLabel("md, txt, csv, xlsx, docx, pdf, png/jpg — любые данные, откуда брать значения")
        hint.setObjectName("StatusLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.sources_list = QListWidget()
        layout.addWidget(self.sources_list, stretch=1)

        remove_btn = QPushButton("🗑 Удалить выбранное")
        remove_btn.setObjectName("Ghost")
        remove_btn.clicked.connect(self._remove_selected_source)
        layout.addWidget(remove_btn)
        return frame

    def _build_recognize_card(self) -> QFrame:
        frame, layout = _card("3. Распознать форму")

        hint = QLabel(
            "AI найдёт пустые поля в выбранной области и покажет поверх экрана, "
            "чем их предлагает заполнить — как в Google Переводчике."
        )
        hint.setObjectName("StatusLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        layout.addStretch(1)

        recognize_btn = QPushButton("✨ Распознать и показать")
        recognize_btn.setObjectName("Primary")
        recognize_btn.clicked.connect(self._run_recognition)
        self.recognize_btn = recognize_btn
        layout.addWidget(recognize_btn)
        return frame

    def _build_fill_card(self) -> QFrame:
        frame, layout = _card("4. Заполнить")

        self.fields_summary = QLabel("Сначала распознайте форму")
        self.fields_summary.setObjectName("StatusLabel")
        self.fields_summary.setWordWrap(True)
        layout.addWidget(self.fields_summary)

        layout.addStretch(1)

        fill_btn = QPushButton("✅ Заполнить форму")
        fill_btn.setObjectName("Success")
        fill_btn.clicked.connect(self._run_fill)
        self.fill_btn = fill_btn
        layout.addWidget(fill_btn)
        return frame

    def _build_log_panel(self) -> QFrame:
        frame, layout = _card("Журнал")
        frame.setMaximumHeight(150)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)
        return frame

    # -------------------------------------------------------------- helpers

    def _log(self, message: str) -> None:
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_view.append(f"[{ts}] {message}")

    def _refresh_states(self) -> None:
        has_region = self.region is not None
        self.recognize_btn.setEnabled(has_region)
        self.rescan_btn.setEnabled(has_region)
        self.fill_btn.setEnabled(bool(self.plan and self.plan.fields))

    def _open_settings(self) -> None:
        SettingsDialog(self).exec()

    # ------------------------------------------------------------- capture

    # Gives the window manager/compositor time to actually unmap this window
    # before we grab the screen, so Fillicity's own UI never ends up inside
    # the captured screenshot.
    HIDE_CAPTURE_DELAY_MS = 200

    def _start_region_selection(self) -> None:
        self.hide()
        self._region_selector = RegionSelector()
        self._region_selector.region_selected.connect(self._on_region_selected)
        self._region_selector.cancelled.connect(self._on_region_cancelled)
        self._region_selector.show()

    def _on_region_cancelled(self) -> None:
        self.show()
        self._log("Выбор области отменена")

    def _capture_full_screen(self) -> None:
        self.hide()
        QTimer.singleShot(self.HIDE_CAPTURE_DELAY_MS, self._do_full_screen_capture)

    def _do_full_screen_capture(self) -> None:
        self._on_region_selected(screen_capture.virtual_desktop_bounds())

    def _on_region_selected(self, region: CaptureRegion) -> None:
        # Main window (and the region-selector overlay) must already be hidden/
        # closed at this point so the screenshot only contains the real form.
        self.region = region
        self._log(f"Область выбрана: {region.width}x{region.height} @ ({region.x},{region.y})")
        QTimer.singleShot(self.HIDE_CAPTURE_DELAY_MS, self._finish_capture)

    def _finish_capture(self) -> None:
        self._capture_preview()
        self.show()
        self._refresh_states()

    def _rescan_region(self) -> None:
        if self.region:
            self.hide()
            QTimer.singleShot(self.HIDE_CAPTURE_DELAY_MS, self._finish_capture)

    def _capture_preview(self) -> None:
        if not self.region:
            return
        png_bytes, b64 = screen_capture.capture_region(self.region)
        self.screenshot_png = png_bytes
        self.screenshot_b64 = b64
        self.screenshot_size = (self.region.width, self.region.height)

        pixmap = QPixmap()
        pixmap.loadFromData(png_bytes, "PNG")
        scaled = pixmap.scaled(
            self.preview_label.width() or 300,
            self.preview_label.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)
        self.region_status.setText(
            f"Область: {self.region.width}x{self.region.height} px "
            f"в позиции ({self.region.x}, {self.region.y})"
        )

    # ------------------------------------------------------------- sources

    def _add_source_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Добавить данные", "", FILE_FILTER)
        for path in paths:
            try:
                doc = data_loader.load_source(path)
            except UnsupportedFileError as exc:
                QMessageBox.warning(self, "Неподдерживаемый файл", str(exc))
                continue
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, "Ошибка чтения файла", f"{path}:\n{exc}")
                continue
            self.sources.append(doc)
            item = QListWidgetItem(f"{'🖼' if doc.kind == 'image' else '📄'} {doc.name}")
            self.sources_list.addItem(item)
            self._log(f"Добавлен источник данных: {doc.name}")

    def _remove_selected_source(self) -> None:
        row = self.sources_list.currentRow()
        if row < 0:
            return
        self.sources_list.takeItem(row)
        removed = self.sources.pop(row)
        self._log(f"Удалён источник данных: {removed.name}")

    # ---------------------------------------------------------- recognition

    def _run_recognition(self) -> None:
        if not self.region or not self.screenshot_b64:
            QMessageBox.information(self, "Нет области", "Сначала выберите область экрана.")
            return
        api_key = config.get_api_key()
        if not api_key:
            QMessageBox.information(
                self, "Нет API ключа", "Укажите OpenRouter API ключ в Настройках."
            )
            return

        self.recognize_btn.setEnabled(False)
        self.recognize_btn.setText("⏳ Распознаю...")
        self._log("Отправляю снимок экрана и данные на анализ AI...")

        width, height = self.screenshot_size
        model = config.get_model()
        self._analyze_worker = AnalyzeWorker(
            api_key, self.region, self.screenshot_b64, width, height, list(self.sources), model
        )
        self._analyze_worker.succeeded.connect(self._on_analysis_done)
        self._analyze_worker.failed.connect(self._on_analysis_failed)
        self._analyze_worker.start()

    def _on_analysis_done(self, plan: FillPlan) -> None:
        self.recognize_btn.setEnabled(True)
        self.recognize_btn.setText("✨ Распознать и показать")
        self.plan = plan
        self._log(f"Найдено полей: {len(plan.fields)}. {plan.notes}")
        self.fields_summary.setText(
            f"Найдено полей: {len(plan.fields)}\n{plan.notes}" if plan.fields
            else f"Полей не найдено.\n{plan.notes}"
        )
        self._show_overlay(plan)
        self._refresh_states()

    def _on_analysis_failed(self, message: str) -> None:
        self.recognize_btn.setEnabled(True)
        self.recognize_btn.setText("✨ Распознать и показать")
        self._log(f"Ошибка анализа: {message}")
        QMessageBox.warning(self, "Ошибка распознавания", message)

    def _show_overlay(self, plan: FillPlan) -> None:
        self._close_overlay()
        self._overlay_canvas = OverlayCanvas(plan.region, plan.fields)
        self._overlay_canvas.show()

        self._toolbar = FloatingToolbar(plan.region, len(plan.fields))
        self._toolbar.fill_clicked.connect(self._run_fill)
        self._toolbar.close_clicked.connect(self._close_overlay)
        self._toolbar.show()

    def _close_overlay(self) -> None:
        if self._overlay_canvas:
            self._overlay_canvas.close()
            self._overlay_canvas = None
        if self._toolbar:
            self._toolbar.close()
            self._toolbar = None

    # ---------------------------------------------------------------- fill

    def _run_fill(self) -> None:
        if not self.plan or not self.plan.fields:
            QMessageBox.information(self, "Нечего заполнять", "Сначала распознайте форму.")
            return

        self.fill_btn.setEnabled(False)
        self.fill_btn.setText("⏳ Заполняю...")
        self._log("Начинаю заполнение формы на экране...")

        self._fill_worker = FillWorker(list(self.plan.fields))
        self._fill_worker.progress.connect(self._on_fill_progress)
        self._fill_worker.finished_ok.connect(self._on_fill_done)
        self._fill_worker.failed.connect(self._on_fill_failed)
        self._fill_worker.start()

    def _on_fill_progress(self, index: int, total: int, field) -> None:
        self._log(f"Заполнено {index}/{total}: {field.label} = {field.value}")

    def _on_fill_done(self, count: int) -> None:
        self.fill_btn.setText("✅ Заполнить форму")
        self._refresh_states()
        self._log(f"Готово: заполнено полей — {count}")
        self._close_overlay()

    def _on_fill_failed(self, message: str) -> None:
        self.fill_btn.setText("✅ Заполнить форму")
        self._refresh_states()
        self._log(f"Ошибка заполнения: {message}")
        QMessageBox.warning(self, "Ошибка заполнения", message)
