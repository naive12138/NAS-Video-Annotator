# -*- coding: utf-8 -*-
"""GUI 冒烟测试：离屏构造主窗口与各页面，验证核心 wiring（不联网、不加载模型）。"""
import os
import shutil
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")

_APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app")
_PROJECT = os.path.join(_APP, "..")
sys.path.insert(0, os.path.join(_PROJECT, ".deps"))
sys.path.insert(0, _APP)

from PySide6.QtWidgets import QApplication  # noqa: E402

from core.config import Config  # noqa: E402
from core.store import Store  # noqa: E402
from gui.main_window import MainWindow  # noqa: E402


def _tmp():
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tmp")
    os.makedirs(d, exist_ok=True)
    return d


class GuiSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.dir = os.path.join(_tmp(), f"gui_{self._testMethodName}")
        shutil.rmtree(self.dir, ignore_errors=True)
        os.makedirs(self.dir, exist_ok=True)
        self.cfg = Config()
        self.cfg.path = Path(self.dir) / "config.json"
        self.cfg._data["storage"]["db_path"] = str(Path(self.dir) / "gui.db")
        self.cfg._data["storage"]["frame_cache_dir"] = str(Path(self.dir) / "frames")
        self.store = Store(self.cfg.db_path)
        self.store.init_schema()

    def test_construct_and_settings_save(self):
        win = MainWindow(self.cfg, self.store)
        self.assertEqual(win.stack.count(), 6)
        win.settings.save()
        self.assertTrue((Path(self.dir) / "config.json").exists())

    def test_library_local_scan(self):
        videos_dir = os.path.join(self.dir, "videos")
        os.makedirs(videos_dir, exist_ok=True)
        with open(os.path.join(videos_dir, "a.mp4"), "w", encoding="utf-8") as f:
            f.write("x")
        self.cfg._data["local_paths"]["roots"] = [videos_dir]
        win = MainWindow(self.cfg, self.store)
        win.library.refresh_local()
        self.assertEqual(win.library.local_table.rowCount(), 1)

    def test_search_and_errors(self):
        win = MainWindow(self.cfg, self.store)
        vid = self.store.upsert_video({
            "source_type": "local", "file_path": str(Path(self.dir) / "x.mp4"), "title": "X",
        })
        self.store.save_annotation({
            "video_id": vid, "genre": "悬疑", "people_count_min": 1, "people_count_max": 2,
            "one_line": "x", "summary": "y", "tags": '["悬疑"]',
        })
        self.store.record_error(vid, "writeback", "同目录未找到同名 NFO", str(Path(self.dir) / "x.mp4"))
        win.search.run_search()
        self.assertEqual(win.search.table.rowCount(), 1)
        win.errors.refresh()
        self.assertEqual(win.errors.listw.count(), 1)

    def test_settings_model_fill_auto_select(self):
        win = MainWindow(self.cfg, self.store)
        s = win.settings
        # 已彻底移除 YOLO 检测字段
        self.assertFalse(hasattr(s, "detector_combo"))
        # “获取模型”后应填入下拉并自动选中第一个，可切换
        s._fill_models(["model-a", "model-b"])
        self.assertEqual(s.vision_combo.count(), 2)
        self.assertEqual(s.vision_combo.currentText(), "model-a")
        self.assertEqual(s.llm_combo.currentText(), "model-a")
        s.vision_combo.setCurrentIndex(1)
        self.assertEqual(s.vision_combo.currentText(), "model-b")


if __name__ == "__main__":
    unittest.main()
