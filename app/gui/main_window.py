# -*- coding: utf-8 -*-
"""主窗口：侧边导航 + 6 个页面，统一管理任务队列并广播进度/状态。"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QPushButton, QLabel,
)

from core.config import Config
from core.pipeline import Pipeline
from core.store import Store
from core.task_queue import TaskQueue
from .settings_page import SettingsPage
from .library_page import LibraryPage
from .analysis_page import AnalysisPage
from .logs_page import LogsPage
from .search_page import SearchPage
from .errors_page import ErrorsPage

STATUS_CN = {"pending": "排队中", "processing": "处理中", "done": "已完成",
             "failed": "失败", "cancelled": "已取消"}


class MainWindow(QMainWindow):
    task_status = Signal(object, str)       # (video, 中文状态)
    task_progress = Signal(object, int, str)  # (video, percent, message)

    def __init__(self, cfg: Config, store: Store):
        super().__init__()
        self.cfg = cfg
        self.store = store
        self._nav_buttons = []
        self.setWindowTitle("NAS 视频内容分析与标注")
        self.resize(1400, 900)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_sidebar())

        self.stack = QStackedWidget()
        self.settings = SettingsPage(cfg)
        self.library = LibraryPage(cfg)
        self.analysis = AnalysisPage(cfg)
        self.logs = LogsPage()
        self.search = SearchPage(cfg, store)
        self.errors = ErrorsPage(store)
        for p in (self.settings, self.library, self.analysis, self.logs, self.search, self.errors):
            self.stack.addWidget(p)
        root.addWidget(self.stack, 1)

        self.library.enqueue.connect(self._on_enqueue)
        self.analysis.cancel_signal.connect(self._on_cancel)

        # 统一任务队列
        self.queue = TaskQueue(
            lambda: Pipeline(cfg, store),
            workers=cfg.runtime["workers"],
            on_status=lambda v, s, m: self.task_status.emit(v, STATUS_CN.get(s, s)),
            on_progress=lambda v, p, m: self.task_progress.emit(v, p, m),
        )
        self.queue.start()

        self.task_status.connect(self.analysis.on_status)
        self.task_status.connect(self.logs.on_status)
        self.task_progress.connect(self.logs.on_progress)

    def _build_sidebar(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(220)
        w.setStyleSheet("background: #1b1b2a;")
        v = QVBoxLayout(w)
        v.setContentsMargins(12, 24, 12, 20)
        v.setSpacing(8)
        logo = QLabel("NASVA")
        logo.setStyleSheet("color: #7c6cff; font-size: 19px; font-weight: bold; background: transparent;")
        sub = QLabel("视频分析与标注")
        sub.setStyleSheet("color: #8a8aa0; font-size: 11px; background: transparent;")
        v.addWidget(logo)
        v.addWidget(sub)
        v.addSpacing(24)
        for i, name in enumerate(["设置", "媒体库", "分析任务", "日志", "检索", "错误"]):
            b = QPushButton(name)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setFixedHeight(42)
            b.clicked.connect(lambda _=False, idx=i: self._switch(idx))
            v.addWidget(b)
            self._nav_buttons.append(b)
            if i == 0:
                b.setChecked(True)
        v.addStretch(1)
        about = QPushButton("关于")
        about.setObjectName("nav")
        about.setFixedHeight(34)
        about.clicked.connect(self._show_about)
        v.addWidget(about)
        ver = QLabel("v1.1.0 · 本地运行")
        ver.setStyleSheet("color: #5a5a6e; font-size: 11px; background: transparent;")
        v.addWidget(ver)
        return w

    def _switch(self, idx):
        self.stack.setCurrentIndex(idx)
        for i, b in enumerate(self._nav_buttons):
            b.setChecked(i == idx)
        if idx == 4:  # 检索
            self.search.run_search()
        if idx == 5:  # 错误
            self.errors.refresh()

    def _on_enqueue(self, videos):
        for v in videos:
            self.queue.submit(v)
        self.analysis.add_videos(videos)
        self.logs.add_videos(videos)
        self._switch(2)  # 切到分析任务页

    def _on_cancel(self, video):
        self.queue.cancel(video)

    def _show_about(self):
        from .about_dialog import AboutDialog
        AboutDialog(self).exec()

    def closeEvent(self, event):
        """关闭窗口时优雅释放资源：停止任务队列、关闭数据库连接。"""
        self.library.shutdown()
        try:
            self.queue.stop()
        except Exception:
            pass
        try:
            self.store.close()
        except Exception:
            pass
        event.accept()
