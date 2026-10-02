# -*- coding: utf-8 -*-
"""全局深色主题样式表。"""

QSS = """
QMainWindow, QWidget { background: #14141f; color: #e5e5f0; }
QGroupBox { border: 1px solid #2c2c40; border-radius: 8px; margin-top: 14px; padding: 14px 12px 12px 12px; font-weight: bold; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 12px; padding: 0 4px; color: #e5e5f0; background: #14141f; }
QLineEdit, QComboBox { background: #16161f; border: 1px solid #33334a; border-radius: 6px; padding: 6px 8px; color: #e5e5f0; min-height: 24px; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView { background: #1b1b2a; color: #e5e5f0; selection-background-color: #7c6cff; border: 1px solid #33334a; }
QPushButton { background: #3c3c58; color: #e5e5f0; border: 1px solid #444466; border-radius: 6px; padding: 7px 16px; }
QPushButton:hover { background: #46466a; }
QPushButton#nav { background: transparent; border: none; color: #c8c8d8; text-align: left; padding-left: 16px; border-radius: 8px; font-size: 14px; }
QPushButton#nav:hover { background: #232336; }
QPushButton#nav:checked { background: #2a2a3d; color: #ffffff; border-left: 3px solid #7c6cff; }
QPushButton#primary { background: #6366f1; border: none; color: #ffffff; font-weight: bold; }
QPushButton#primary:hover { background: #7477f5; }
QPushButton#green { background: #22c55e; border: none; color: #ffffff; font-weight: bold; }
QPushButton#green:hover { background: #25d366; }
QRadioButton { color: #e5e5f0; spacing: 8px; font-size: 14px; }
QRadioButton::indicator { width: 20px; height: 20px; border-radius: 10px; border: 2px solid #6b6b82; background: #16161f; }
QRadioButton::indicator:hover { border-color: #9a9ab5; }
QRadioButton::indicator:checked { border: 2px solid #7c6cff; background: #7c6cff; }
QCheckBox { color: #e5e5f0; spacing: 8px; }
QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px; border: 2px solid #6b6b82; background: #16161f; }
QCheckBox::indicator:checked { border: 2px solid #7c6cff; background: #7c6cff; }
QLabel { color: #e5e5f0; }
QTabWidget::pane { border: 1px solid #2c2c40; border-radius: 6px; top: -1px; }
QTabBar::tab { background: #232336; color: #c8c8d8; padding: 8px 20px; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px; }
QTabBar::tab:selected { background: #2a2a3d; color: #ffffff; }
QTableWidget { background: #1b1b2a; color: #e5e5f0; border: 1px solid #2c2c40; border-radius: 6px; gridline-color: #232336; }
QHeaderView::section { background: #232336; color: #c8c8d8; border: none; padding: 8px; }
QTableWidget::item { padding: 6px; }
QProgressBar { background: #16161f; border: 1px solid #33334a; border-radius: 4px; color: #e5e5f0; text-align: center; }
QProgressBar::chunk { background: #22c55e; border-radius: 4px; }
QListWidget { background: #1b1b2a; border: 1px solid #2c2c40; border-radius: 6px; color: #e5e5f0; }
QListWidget::item { padding: 10px 12px; }
QListWidget::item:selected { background: #2a2a3d; color: #ffffff; border-left: 3px solid #7c6cff; }
QFrame#detail { background: #1b1b2a; border: 1px solid #2c2c40; border-radius: 8px; }
"""
