# -*- coding: utf-8 -*-
"""关于对话框。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QFrame,
)


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于")
        self.setFixedSize(400, 380)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 34, 32, 26)
        root.setSpacing(10)

        logo = QLabel("NASVA")
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet("font-size: 34px; font-weight: bold; color: #7c6cff;")

        name = QLabel("NAS 视频内容分析与标注")
        name.setAlignment(Qt.AlignCenter)
        name.setStyleSheet("font-size: 15px; color: #e5e5f0;")

        ver = QLabel("v1.1.2 · 本地运行")
        ver.setAlignment(Qt.AlignCenter)
        ver.setStyleSheet("font-size: 12px; color: #8a8aa0;")

        root.addWidget(logo)
        root.addWidget(name)
        root.addWidget(ver)
        root.addSpacing(10)

        # 作者卡片
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background: #1b1b2a; border: 1px solid #2c2c40; border-radius: 12px; }"
        )
        cv = QVBoxLayout(card)
        cv.setContentsMargins(22, 18, 22, 18)
        cv.setSpacing(6)
        head = QLabel("作  者")
        head.setStyleSheet("color: #8a8aa0; font-size: 12px;")
        a1 = QLabel("javbus-naive9527")
        a1.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        a2 = QLabel("B站来杯果汁12138")
        a2.setStyleSheet("font-size: 14px; color: #e5e5f0;")
        cv.addWidget(head)
        cv.addWidget(a1)
        cv.addWidget(a2)
        root.addWidget(card)

        tagline = QLabel("全程本地 AI · 视频内容不出本机")
        tagline.setAlignment(Qt.AlignCenter)
        tagline.setStyleSheet("font-size: 12px; color: #22c55e;")
        root.addWidget(tagline)
        root.addStretch(1)

        close = QPushButton("关闭")
        close.setObjectName("primary")
        close.setFixedHeight(36)
        close.clicked.connect(self.accept)
        root.addWidget(close)
