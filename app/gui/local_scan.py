"""本地扫描专用后台任务；不持有页面或访问任何控件。"""
from __future__ import annotations

from threading import Event, Thread

from PySide6.QtCore import QObject, Signal

from core.sources.local import LocalAdapter


class LocalScanTask(QObject):
    progress = Signal(str, int, int)
    batch = Signal(list)
    finished = Signal(bool, int, str)

    def __init__(self, roots):
        super().__init__()
        self.roots = list(roots)
        self.cancel_event = Event()
        self.thread = Thread(target=self._run, name="local-video-scan", daemon=True)

    def _emit(self, signal, *args):
        try:
            signal.emit(*args)
        except RuntimeError:
            # QApplication/page may already have been destroyed during slow NAS I/O.
            self.cancel_event.set()

    def _run(self):
        adapter = LocalAdapter(self.roots)
        error = ""
        try:
            adapter.list_videos(
                on_progress=lambda *args: self._emit(self.progress, *args),
                on_batch=lambda videos: self._emit(self.batch, videos),
                cancel_event=self.cancel_event,
            )
        except Exception as exc:
            error = str(exc)
        self._emit(self.finished, self.cancel_event.is_set(),
                   getattr(adapter, "warning_count", 0), error)
