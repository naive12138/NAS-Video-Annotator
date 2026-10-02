# -*- coding: utf-8 -*-
"""错误页：错误列表 + 选中显示文件名/原因/路径。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QLabel,
    QFrame, QPushButton, QSplitter, QTextEdit, QMessageBox,
)

from core.store import Store


class ErrorsPage(QWidget):
    def __init__(self, store: Store, parent=None):
        super().__init__(parent)
        self.store = store
        self._errors = []
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)
        title = QLabel("错误")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #ffffff;")
        sub = QLabel("回写失败 / 跳过 / 分析失败都会记录在这里")
        sub.setStyleSheet("color: #8a8aa0;")
        root.addWidget(title)
        root.addWidget(sub)

        bar = QHBoxLayout()
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh)
        self.clear_btn = QPushButton("删除全部")
        self.clear_btn.clicked.connect(self._clear_all)
        bar.addWidget(self.refresh_btn)
        bar.addWidget(self.clear_btn)
        bar.addStretch(1)
        root.addLayout(bar)

        split = QSplitter(Qt.Horizontal)
        self.listw = QListWidget()
        self.listw.currentRowChanged.connect(self._show_detail)
        split.addWidget(self.listw)

        detail = QFrame(); detail.setObjectName("detail")
        dv = QVBoxLayout(detail); dv.setContentsMargins(20, 20, 20, 20); dv.setSpacing(12)
        self.fname = QLabel("")
        self.fname.setStyleSheet("font-size: 16px; font-weight: bold; color: #ff6b6b;")
        self.fname.setTextInteractionFlags(Qt.TextSelectableByMouse)
        dv.addWidget(self.fname)
        dv.addWidget(self._label("原因"))
        self.reason = QTextEdit()
        self.reason.setReadOnly(True)
        self.reason.setMinimumHeight(120)
        dv.addWidget(self.reason)
        dv.addWidget(self._label("路径"))
        self.path = QLabel(""); self.path.setWordWrap(True)
        self.path.setStyleSheet("color: #c8c8d8;")
        self.path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        dv.addWidget(self.path)
        dv.addStretch(1)
        split.addWidget(detail)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 3)
        root.addWidget(split, 1)

    @staticmethod
    def _label(text):
        l = QLabel(text)
        l.setStyleSheet("color: #8a8aa0;")
        return l

    def refresh(self):
        self._errors = self.store.list_errors()
        self.listw.clear()
        for e in self._errors:
            name = e["path"].split("\\")[-1].split("/")[-1] if e["path"] else "(无文件)"
            self.listw.addItem(QListWidgetItem(f"{name} — {e['stage']}"))
        if self._errors:
            self.listw.setCurrentRow(0)

    def _clear_all(self):
        if not self._errors:
            return
        if QMessageBox.question(
            self, "确认清空", f"确认删除全部 {len(self._errors)} 条错误记录？"
        ) != QMessageBox.Yes:
            return
        self.store.delete_all_errors()
        self._errors = []
        self.listw.clear()
        self.fname.setText("")
        self.reason.setText("")
        self.path.setText("")

    def _show_detail(self, index):
        if not (0 <= index < len(self._errors)):
            return
        e = self._errors[index]
        name = e["path"].split("\\")[-1].split("/")[-1] if e["path"] else "(无文件)"
        self.fname.setText(name)
        self.reason.setText(e["reason"] or "")
        self.path.setText(e["path"] or "")
