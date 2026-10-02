# -*- coding: utf-8 -*-
"""分析任务页：任务列表 + 中文状态（任务队列由主窗口统一管理）。"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView,
)

from core.config import Config
from core.sources.base import VideoSource


class AnalysisPage(QWidget):
    cancel_signal = Signal(object)  # 请求取消某个正在处理的任务

    def __init__(self, cfg: Config, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self._rows: dict[int, int] = {}
        self._running_video = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)
        title = QLabel("分析任务")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #ffffff;")
        sub = QLabel("队列与状态，失败可重试（详细进度见“日志”页）")
        sub.setStyleSheet("color: #8a8aa0;")
        root.addWidget(title)
        root.addWidget(sub)

        bar = QHBoxLayout()
        self.cancel_btn = QPushButton("取消当前任务")
        self.cancel_btn.clicked.connect(self._on_cancel)
        bar.addWidget(self.cancel_btn)
        self.clear_btn = QPushButton("清除已完成/失败")
        self.clear_btn.clicked.connect(self._clear_done)
        bar.addWidget(self.clear_btn)
        bar.addStretch(1)
        root.addLayout(bar)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["文件名", "状态", "回写目标"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        root.addWidget(self.table, 1)

    def add_videos(self, videos: list[VideoSource]):
        for v in videos:
            if id(v) in self._rows:
                continue
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(v.title or os.path.basename(v.file_path)))
            self.table.setItem(row, 1, QTableWidgetItem("排队中"))
            self.table.setItem(row, 2, QTableWidgetItem(self._target_label(v)))
            self._rows[id(v)] = row

    def _target_label(self, v: VideoSource) -> str:
        if v.source_type == "jellyfin":
            return "Jellyfin 简介栏"
        return "优先 NFO（无则 txt）" if self.cfg.output.get("local_mode") == "nfo_first" else "仅 txt"

    def on_status(self, video, cn_status: str):
        row = self._rows.get(id(video))
        if row is None:
            return
        item = QTableWidgetItem(cn_status)
        if cn_status == "失败":
            item.setForeground(Qt.red)
        elif cn_status == "已完成":
            item.setForeground(Qt.darkGreen)
        elif cn_status == "已取消":
            item.setForeground(Qt.gray)
        self.table.setItem(row, 1, item)

        if cn_status == "处理中":
            self._running_video = video
        elif cn_status in ("已完成", "失败", "已取消") and self._running_video is video:
            self._running_video = None

    def _on_cancel(self):
        if self._running_video is not None:
            self.cancel_signal.emit(self._running_video)

    def _clear_done(self):
        for r in range(self.table.rowCount() - 1, -1, -1):
            item = self.table.item(r, 1)
            txt = item.text() if item else ""
            if txt in ("已完成", "失败", "已取消"):
                self.table.removeRow(r)
