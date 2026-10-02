# -*- coding: utf-8 -*-
"""应用入口：python app/main.py 启动桌面界面。"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))          # app/
_PROJECT = os.path.dirname(_ROOT)                            # 项目根
sys.path.insert(0, os.path.join(_PROJECT, ".deps"))          # PySide6
sys.path.insert(0, _ROOT)                                     # core / gui

from PySide6.QtGui import QFont  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from core.config import Config  # noqa: E402
from core.store import Store  # noqa: E402
from gui.main_window import MainWindow  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei", 10))
    from gui.theme import QSS
    app.setStyleSheet(QSS)

    cfg = Config.load()
    if not cfg.path.exists():
        cfg.save()  # 首次启动：在 exe 同目录 data/ 下生成默认配置

    # 让 faster-whisper 的模型缓存也落在 exe 同目录（而不是用户主目录）
    hf_cache = str(cfg.storage_path("data_dir") / "hf_cache")
    os.environ["HF_HOME"] = hf_cache
    os.environ.setdefault("XDG_CACHE_HOME", hf_cache)

    store = Store(cfg.db_path)
    store.init_schema()

    # 启动时清理上次可能残留的帧缓存（抽帧图片/临时音轨）
    frame_dir = cfg.storage_path("frame_cache_dir")
    shutil.rmtree(frame_dir, ignore_errors=True)
    frame_dir.mkdir(parents=True, exist_ok=True)

    win = MainWindow(cfg, store)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
