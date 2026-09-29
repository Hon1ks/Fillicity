"""Background QThreads so network calls / simulated typing never freeze the UI."""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from app.core import ai_engine, form_filler
from app.core.models import CaptureRegion, FieldFill, FillPlan, SourceDocument


class AnalyzeWorker(QThread):
    succeeded = Signal(object)  # FillPlan
    failed = Signal(str)

    def __init__(
        self,
        api_key: str,
        region: CaptureRegion,
        screenshot_b64: str,
        width: int,
        height: int,
        sources: list[SourceDocument],
        model: str,
    ) -> None:
        super().__init__()
        self._args = (api_key, region, screenshot_b64, width, height, sources, model)

    def run(self) -> None:
        try:
            plan: FillPlan = ai_engine.analyze(*self._args)
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI, not swallowed
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(plan)


class FillWorker(QThread):
    progress = Signal(int, int, object)  # index, total, FieldFill
    finished_ok = Signal(int)
    failed = Signal(str)

    def __init__(self, fields: list[FieldFill]) -> None:
        super().__init__()
        self.fields = fields
        self._abort = False

    def abort(self) -> None:
        self._abort = True

    def run(self) -> None:
        try:
            count = form_filler.fill_fields(
                self.fields,
                on_progress=lambda i, t, f: self.progress.emit(i, t, f),
                abort_check=lambda: self._abort,
            )
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.finished_ok.emit(count)
