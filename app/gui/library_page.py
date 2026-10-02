# -*- coding: utf-8 -*-
"""媒体库页：本地路径 / Jellyfin 两个 Tab，勾选后加入分析队列。"""
from __future__ import annotations

import os
from collections import deque

from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QProgressBar,
)

from core.config import Config
from core.sources.base import VideoSource
from core.sources.local import LocalAdapter
from core.sources.jellyfin import JellyfinAdapter
from .util import run_async
from .local_scan import LocalScanTask


class LibraryPage(QWidget):
    enqueue = Signal(list)  # list[VideoSource]

    def __init__(self, cfg: Config, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self._local_videos: list[VideoSource] = []
        self._jf_videos: list[VideoSource] = []
        self._local_worker = None
        self._local_busy = False
        self._closed = False
        self._pending_rows = deque()
        self._scan_outcome = None
        self._display_timer = QTimer(self)
        self._display_timer.setInterval(10)
        self._display_timer.timeout.connect(self._drain_local_rows)
        self._build()
        self.tabs.currentChanged.connect(self._update_add_button)

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)
        title = QLabel("媒体库")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #ffffff;")
        sub = QLabel("从本地路径或 Jellyfin 选择要分析的视频")
        sub.setStyleSheet("color: #8a8aa0;")
        root.addWidget(title)
        root.addWidget(sub)

        self.local_table = self._table(["选择", "文件名", "大小"])
        self.jf_table = self._table(["选择", "文件名", "大小"])
        self._local_path_label = QLabel("")
        self._local_path_label.setWordWrap(True)
        self._jf_path_label = QLabel("")

        self.tabs = QTabWidget()
        self.tabs.addTab(self._tab_page(self.local_table, self._local_path_label, self.on_refresh_local), "本地路径")
        self.tabs.addTab(self._tab_page(self.jf_table, self._jf_path_label, self.on_refresh_jf), "Jellyfin")
        root.addWidget(self.tabs, 1)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.add_btn = QPushButton("加入分析队列")
        self.add_btn.setObjectName("primary")
        self.add_btn.clicked.connect(self.on_add_to_queue)
        bottom.addWidget(self.add_btn)
        root.addLayout(bottom)

    @staticmethod
    def _table(headers):
        t = QTableWidget(0, len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        return t

    def _tab_page(self, table, path_label, refresh_fn):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)
        bar = QHBoxLayout()
        path_label.setStyleSheet("color: #8a8aa0;")
        refresh = QPushButton("刷新")
        refresh.clicked.connect(refresh_fn)
        bar.addWidget(path_label, 1 if table is self.local_table else 0)
        if table is not self.local_table:
            bar.addStretch(1)
        bar.addWidget(refresh)
        if table is self.local_table:
            self.local_refresh_btn = refresh
            self.local_cancel_btn = QPushButton("取消扫描")
            self.local_cancel_btn.clicked.connect(self.cancel_local_scan)
            self.local_cancel_btn.hide()
            bar.addWidget(self.local_cancel_btn)
        v.addLayout(bar)
        if table is self.local_table:
            self.local_progress = QProgressBar()
            self.local_progress.setRange(0, 0)
            self.local_progress.setTextVisible(False)
            self.local_progress.hide()
            v.addWidget(self.local_progress)
        v.addWidget(table, 1)
        return w

    # ---- 扫描 ----
    def _scan_local(self) -> list[VideoSource]:
        """纯扫描（不做 UI），供后台线程调用。"""
        cfg = self.cfg
        roots = cfg.local_paths["roots"]
        if not roots:
            return []
        return LocalAdapter(roots).list_videos()

    _MAX_DISPLAY = 2000  # 表格最多显示的行数，避免海量视频时界面卡死

    def _show_local(self, videos: list[VideoSource]):
        """在 UI 线程更新本地路径表格与提示。"""
        cfg = self.cfg
        roots = cfg.local_paths["roots"]
        self._local_videos = videos
        self._fill_table(self.local_table, videos[:self._MAX_DISPLAY])
        joined = "、".join(roots)
        if not roots:
            self._local_path_label.setStyleSheet("color: #f59e0b; font-weight: bold;")
            self._local_path_label.setText("⚠ 尚未配置媒体根目录，请先在「设置」页选择本地路径并保存")
        elif videos:
            self._local_path_label.setStyleSheet("color: #22c55e;")
            note = (f"（共 {len(videos)} 个，仅显示前 {self._MAX_DISPLAY} 个，建议缩小媒体根目录）"
                    if len(videos) > self._MAX_DISPLAY else "")
            self._local_path_label.setText(f"✓ 扫描路径：{joined}（找到 {len(videos)} 个视频）{note}")
        else:
            self._local_path_label.setStyleSheet("color: #f59e0b; font-weight: bold;")
            self._local_path_label.setText(
                f"⚠ 未找到视频：{joined} —— 请检查路径或文件格式（会递归扫描子文件夹）"
            )

    def refresh_local(self) -> list[VideoSource]:
        """同步扫描并刷新 UI（供测试用，需在主线程调用）。"""
        videos = self._scan_local()
        self._show_local(videos)
        return videos

    def on_refresh_local(self):
        if self._local_busy or self._closed:
            return
        self._scan_roots = list(self.cfg.local_paths["roots"])
        self._local_busy = True
        self._scan_outcome = None
        self._pending_rows.clear()
        self._local_videos = []
        self.local_table.setRowCount(0)
        self.local_table.setEnabled(False)
        self.local_refresh_btn.setEnabled(False)
        self.local_cancel_btn.setEnabled(True)
        self.local_cancel_btn.show()
        self.local_progress.show()
        self._update_add_button()
        self._local_path_label.setStyleSheet("color: #8a8aa0;")
        self._local_path_label.setText("正在扫描… 已发现 0 个视频，警告 0 项")
        task = LocalScanTask(self._scan_roots)
        task.progress.connect(self._on_local_progress, Qt.QueuedConnection)
        task.batch.connect(self._on_local_batch, Qt.QueuedConnection)
        task.finished.connect(self._on_local_finished, Qt.QueuedConnection)
        # Capture only the Event; the running task must not retain the page.
        cancel = task.cancel_event
        self._destroy_connection = self.destroyed.connect(lambda *_: cancel.set())
        self._local_worker = task
        task.thread.start()

    @Slot()
    def cancel_local_scan(self):
        if self._local_worker and self._local_busy:
            self._local_worker.cancel_event.set()
            self.local_cancel_btn.setEnabled(False)
            self._local_path_label.setText("正在取消… 等待当前文件访问结束，界面仍可操作")

    @Slot(str, int, int)
    def _on_local_progress(self, directory, count, warnings):
        if self._closed or not self._local_busy:
            return
        if self._local_worker.cancel_event.is_set():
            return
        self._local_path_label.setText(
            f"正在扫描：{directory}（已发现 {count} 个视频，警告 {warnings} 项）")

    @Slot(list)
    def _on_local_batch(self, videos):
        if self._closed or not self._local_busy:
            return
        start = len(self._local_videos)
        self._local_videos.extend(videos)
        self._pending_rows.extend(videos[:max(0, self._MAX_DISPLAY - start)])
        if self._pending_rows and not self._display_timer.isActive():
            self._display_timer.start()

    @Slot(bool, int, str)
    def _on_local_finished(self, cancelled, warnings, error):
        if self._closed or not self._local_busy:
            return
        self._scan_outcome = (cancelled, warnings, error)
        if self._pending_rows:
            self.local_cancel_btn.setEnabled(False)
            self._local_path_label.setText("扫描已结束，正在加载列表…")
        else:
            self._finish_local_display()

    @Slot()
    def _drain_local_rows(self):
        if self._closed:
            return
        self.local_table.setUpdatesEnabled(False)
        try:
            for _ in range(min(50, len(self._pending_rows))):
                video = self._pending_rows.popleft()
                row = self.local_table.rowCount()
                self.local_table.setRowCount(row + 1)
                self._fill_row(self.local_table, row, video)
        finally:
            self.local_table.setUpdatesEnabled(True)
        if not self._pending_rows:
            self._display_timer.stop()
            if self._scan_outcome is not None:
                self._finish_local_display()

    def _finish_local_display(self):
        cancelled, warnings, error = self._scan_outcome
        count = len(self._local_videos)
        note = f"；仅显示前 {self._MAX_DISPLAY} 个" if count > self._MAX_DISPLAY else ""
        if error:
            message = f"扫描失败：{error}（已保留 {count} 个视频，列表不完整）"
        elif cancelled:
            message = f"已取消，列表不完整（已发现 {count} 个视频）"
        elif not self._scan_roots:
            message = "尚未配置媒体根目录，请先在「设置」页选择本地路径并保存"
        elif not count:
            message = "未找到视频，请检查路径或文件格式（会递归扫描子文件夹）"
        else:
            message = f"扫描完成：找到 {count} 个视频"
        message += f"{note}；警告 {warnings} 项"
        if warnings:
            message += "（部分路径或文件不可访问）"
        self._local_path_label.setText(message)
        self._local_path_label.setToolTip("、".join(self._scan_roots))
        self._local_path_label.setStyleSheet(
            "color: #f59e0b;" if error or cancelled or warnings or not count else "color: #22c55e;")
        self._local_busy = False
        self.destroyed.disconnect(self._destroy_connection)
        self._local_worker = None
        self.local_progress.hide()
        self.local_cancel_btn.hide()
        self.local_refresh_btn.setEnabled(True)
        self.local_table.setEnabled(True)
        self._update_add_button()

    def _update_add_button(self, *_):
        self.add_btn.setEnabled(not (self.tabs.currentIndex() == 0 and self._local_busy))

    def shutdown(self):
        self._closed = True
        self._display_timer.stop()
        self._pending_rows.clear()
        if self._local_worker:
            self._local_worker.cancel_event.set()

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)

    def on_refresh_jf(self):
        cfg = self.cfg
        if not cfg.jellyfin["base_url"] or not cfg.jellyfin["api_key"]:
            self._jf_videos = []
            self._fill_table(self.jf_table, [])
            self._jf_path_label.setText("请先在设置页填写 Jellyfin 地址与 API Key")
            return

        self._jf_path_label.setText("正在从 Jellyfin 拉取…")

        def fn():
            return JellyfinAdapter(cfg.jellyfin["base_url"], cfg.jellyfin["api_key"]).list_videos()

        def done(videos, err):
            if err:
                self._jf_videos = []
                self._fill_table(self.jf_table, [])
                self._jf_path_label.setText(f"拉取失败：{err}")
                return
            self._jf_videos = videos or []
            self._fill_table(self.jf_table, self._jf_videos)
            self._jf_path_label.setText(f"Jellyfin：{cfg.jellyfin['base_url']}")

        self._worker = run_async(fn, done)

    def _fill_table(self, table, videos: list[VideoSource]):
        table.setRowCount(len(videos))
        for r, v in enumerate(videos):
            self._fill_row(table, r, v)

    def _fill_row(self, table, r, v):
        it = QTableWidgetItem()
        it.setCheckState(Qt.Unchecked)
        table.setItem(r, 0, it)
        # 本地源显示完整文件名（含扩展名），方便辨认是否为视频
        if v.source_type == "local":
            name = os.path.basename(v.file_path)
        else:
            name = v.title or os.path.basename(v.file_path)
        name_item = QTableWidgetItem(name)
        name_item.setToolTip(v.file_path)  # 悬停显示完整路径与真实后缀
        table.setItem(r, 1, name_item)
        size = (self._format_size(v.meta.get("size_bytes")) if v.source_type == "local"
                else self._size(v.file_path))
        table.setItem(r, 2, QTableWidgetItem(size))

    @staticmethod
    def _format_size(n):
        if n is None:
            return "—"
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024 or unit == "GB":
                return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
            n /= 1024
        return "—"

    @staticmethod
    def _size(path: str) -> str:
        try:
            n = os.path.getsize(path)
            for unit in ("B", "KB", "MB", "GB"):
                if n < 1024 or unit == "GB":
                    return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
                n /= 1024
        except OSError:
            return "—"
        return "—"

    def on_add_to_queue(self):
        if self.tabs.currentIndex() == 0 and self._local_busy:
            return
        selected = []
        if self.tabs.currentIndex() == 0:
            table, videos = self.local_table, self._local_videos
        else:
            table, videos = self.jf_table, self._jf_videos
        for r in range(table.rowCount()):
            item = table.item(r, 0)
            if item and item.checkState() == Qt.Checked and r < len(videos):
                selected.append(videos[r])
        if selected:
            self.enqueue.emit(selected)
