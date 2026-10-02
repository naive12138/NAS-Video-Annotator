# -*- coding: utf-8 -*-
"""结果详情：展示标注 + 精简文本预览 + 立即回写按钮。"""
from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QGroupBox, QFormLayout,
)

from core import condense, writeback
from core.config import Config
from core.sources.base import VideoSource
from core.store import Store


class ResultDialog(QDialog):
    def __init__(self, cfg: Config, store: Store, row: dict, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.store = store
        self.row = row
        self.setWindowTitle("结果详情")
        self.resize(520, 480)

        self.video = row_to_video(row)
        self.annotation = row_to_annotation(row)
        self._build()

    def _build(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(12)

        head = QLabel(self.video.title or self.video.file_path)
        head.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        v.addWidget(head)

        form = QGroupBox("标注")
        f = QFormLayout(form)
        f.addRow("题材", QLabel(self.annotation["genre"] or "—"))
        f.addRow("人数", QLabel(f"{self.annotation['people_count_min']}~{self.annotation['people_count_max']} 人"))
        f.addRow("一句话", QLabel(self.annotation["one_line"] or "—"))
        v.addWidget(form)

        prev = QGroupBox("精简回写文本预览")
        pv = QVBoxLayout(prev)
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlainText(condense.condense(self.annotation))
        pv.addWidget(self.preview)
        v.addWidget(prev, 1)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.status = QLabel("")
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.write_btn = QPushButton("立即回写")
        self.write_btn.setObjectName("primary")
        self.write_btn.clicked.connect(self.on_writeback)
        close = QPushButton("关闭")
        close.clicked.connect(self.accept)
        bottom.addWidget(self.status, 1)
        bottom.addWidget(self.write_btn)
        bottom.addWidget(close)
        v.addLayout(bottom)

    def on_writeback(self):
        result, _ = writeback.writeback(
            self.cfg, self.store, self.video, self.annotation, self.row["video_id"]
        )
        mark = "✓" if result.ok else "✗"
        self.status.setText(f"{mark} {result.detail}")


def _parse_tags(tags):
    if not tags:
        return []
    try:
        v = json.loads(tags)
        return v if isinstance(v, list) else [str(v)]
    except (json.JSONDecodeError, TypeError):
        return [tags]


def row_to_video(row: dict) -> VideoSource:
    """从 store.search() 的一行还原 VideoSource（供回写使用）。"""
    return VideoSource(
        source_type=row["source_type"],
        file_path=row["file_path"],
        title=row["title"] or "",
        jellyfin_item_id=row.get("jellyfin_item_id"),
    )


def row_to_annotation(row: dict) -> dict:
    """从 store.search() 的一行还原标注字典（供回写使用）。"""
    return {
        "genre": row["genre"] or "",
        "people_count_min": row["people_count_min"],
        "people_count_max": row["people_count_max"],
        "one_line": row["one_line"] or "",
        "summary": row["summary"] or "",
        "tags": _parse_tags(row["tags"]),
    }
