# -*- coding: utf-8 -*-
"""检索页：按题材/人数/关键词筛选，导出，双击查看详情并可立即回写。"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QLineEdit, QComboBox, QHeaderView, QMessageBox,
)

from core import writeback
from core.config import Config
from core.store import Store
from .result_detail import ResultDialog, row_to_video, row_to_annotation


class SearchPage(QWidget):
    def __init__(self, cfg: Config, store: Store, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.store = store
        self._rows = []
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)
        title = QLabel("检索")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #ffffff;")
        sub = QLabel("按题材、人数、关键词筛选已分析的视频")
        sub.setStyleSheet("color: #8a8aa0;")
        root.addWidget(title)
        root.addWidget(sub)

        bar = QHBoxLayout(); bar.setSpacing(10)
        self.kw = QLineEdit(); self.kw.setPlaceholderText("关键词…")
        self.genre = QComboBox(); self.genre.addItems(["全部题材", "剧情", "悬疑", "纪录片", "家庭"])
        self.people = QComboBox(); self.people.addItems(["全部人数", "1 人", "2~3 人", "4 人以上"])
        self.source = QComboBox(); self.source.addItems(["全部来源", "local", "jellyfin"])
        search = QPushButton("搜索"); search.setObjectName("primary"); search.clicked.connect(self.run_search)
        bar.addWidget(self.kw, 1); bar.addWidget(self.genre); bar.addWidget(self.people)
        bar.addWidget(self.source); bar.addWidget(search)
        root.addLayout(bar)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["文件名", "题材", "人数", "剧情概括", "来源", "操作"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setColumnWidth(5, 190)
        self.table.verticalHeader().setDefaultSectionSize(52)
        self.table.verticalHeader().setVisible(False)
        self.table.cellDoubleClicked.connect(self._open_detail)
        root.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        clear_btn = QPushButton("清空全部标注")
        clear_btn.clicked.connect(self._clear_all)
        bottom.addWidget(clear_btn)
        bottom.addStretch(1)
        root.addLayout(bottom)

    def run_search(self):
        genre = None if self.genre.currentIndex() == 0 else self.genre.currentText()
        source = None if self.source.currentIndex() == 0 else self.source.currentText()
        pmin = pmax = None
        if self.people.currentIndex() == 1:
            pmin, pmax = 1, 1
        elif self.people.currentIndex() == 2:
            pmin, pmax = 2, 3
        elif self.people.currentIndex() == 3:
            pmin, pmax = 4, None

        self._rows = self.store.search(
            query=self.kw.text().strip() or None,
            genre=genre, source_type=source, people_min=pmin, people_max=pmax,
        )
        self._fill_table(self._rows)

    def _fill_table(self, rows):
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            name = row["title"] or row["file_path"]
            if row.get("asr_failed"):
                name += "（音频转换失败）"
            self.table.setItem(r, 0, QTableWidgetItem(name))
            self.table.setItem(r, 1, QTableWidgetItem(row["genre"] or ""))
            self.table.setItem(r, 2, QTableWidgetItem(f"{row['people_count_min']}~{row['people_count_max']} 人"))
            self.table.setItem(r, 3, QTableWidgetItem(row["summary"] or ""))
            self.table.setItem(r, 4, QTableWidgetItem(row["source_type"]))
            cell = QWidget()
            cl = QHBoxLayout(cell)
            cl.setContentsMargins(4, 2, 4, 2)
            cl.setSpacing(8)
            wbtn = QPushButton("回写")
            wbtn.clicked.connect(lambda _=False, ri=r: self._do_writeback(ri))
            dbtn = QPushButton("删除")
            dbtn.clicked.connect(lambda _=False, ri=r: self._do_delete(ri))
            for b in (wbtn, dbtn):
                b.setFixedSize(72, 34)
            cl.addWidget(wbtn)
            cl.addWidget(dbtn)
            cl.addStretch(1)
            self.table.setCellWidget(r, 5, cell)

    def _open_detail(self, row, _col):
        if 0 <= row < len(self._rows):
            dlg = ResultDialog(self.cfg, self.store, self._rows[row], self)
            dlg.exec()

    def _do_writeback(self, row_index):
        if not (0 <= row_index < len(self._rows)):
            return
        row = self._rows[row_index]
        result, _ = writeback.writeback(
            self.cfg, self.store,
            row_to_video(row), row_to_annotation(row), row["video_id"],
        )
        mark = "✓" if result.ok else "✗"
        QMessageBox.information(self, "回写结果", f"{mark} {result.detail}")

    def _do_delete(self, row_index):
        if not (0 <= row_index < len(self._rows)):
            return
        row = self._rows[row_index]
        name = row["title"] or row["file_path"]
        if QMessageBox.question(self, "确认删除", f"确认删除这条标注？\n{name}") != QMessageBox.Yes:
            return
        self.store.delete_annotation(row["ann_id"])
        self.run_search()

    def _clear_all(self):
        if not self._rows:
            return
        if QMessageBox.question(
            self, "确认清空", f"确认删除全部 {len(self._rows)} 条标注？此操作不可撤销。"
        ) != QMessageBox.Yes:
            return
        self.store.delete_all_annotations()
        self.run_search()
