# -*- coding: utf-8 -*-
"""日志页：进度条 + 滚动日志（文本可复制）。"""
from __future__ import annotations

import os
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QTextEdit, QScrollArea,
)

from core.sources.base import VideoSource


class LogsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._meta: dict[int, dict] = {}
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        title = QLabel("日志")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #ffffff;")
        sub = QLabel("实时进度与运行日志（日志内容可选中复制）")
        sub.setStyleSheet("color: #8a8aa0;")
        root.addWidget(title)
        root.addWidget(sub)

        # 进度区（滚动）
        self.prog_container = QWidget()
        self.prog_container.setStyleSheet("background: transparent;")
        self.prog_layout = QVBoxLayout(self.prog_container)
        self.prog_layout.setContentsMargins(0, 0, 0, 0)
        self.prog_layout.setSpacing(8)
        self.prog_layout.addStretch(1)
        prog_scroll = QScrollArea()
        prog_scroll.setWidgetResizable(True)
        prog_scroll.setWidget(self.prog_container)
        root.addWidget(prog_scroll, 1)

        # 日志文本区
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        root.addWidget(self.log, 1)

    # ---- 对外接口 ----
    def add_videos(self, videos: list[VideoSource]):
        for v in videos:
            if id(v) in self._meta:
                continue
            name = os.path.basename(v.file_path)
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(10)
            name_label = QLabel(name)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setFixedHeight(16)
            status = QLabel("排队中")
            rl.addWidget(name_label, 2)
            rl.addWidget(bar, 5)
            rl.addWidget(status, 2)
            self.prog_layout.insertWidget(self.prog_layout.count() - 1, row)
            self._meta[id(v)] = {"name": name, "bar": bar, "status": status}
            self._append(name, "排队中")

    def on_progress(self, video, percent: int, message: str):
        m = self._meta.get(id(video))
        if m:
            m["bar"].setValue(percent)
            m["status"].setText(message)
        self._append(self._name(video), f"{percent}% {message}")

    def on_status(self, video, cn_status: str):
        m = self._meta.get(id(video))
        if m:
            m["status"].setText(cn_status)
        self._append(self._name(video), cn_status)

    def _name(self, video) -> str:
        m = self._meta.get(id(video))
        return m["name"] if m else os.path.basename(getattr(video, "file_path", ""))

    def _append(self, name: str, message: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.append(f"[{ts}] {name} —— {message}")
