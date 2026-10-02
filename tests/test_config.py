# -*- coding: utf-8 -*-
"""config.py 单元测试（不依赖 GUI / 原生模块，可直接运行）。"""
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

from core.config import Config, DEFAULTS  # noqa: E402


class ConfigTest(unittest.TestCase):
    def _tmp(self):
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tmp")
        os.makedirs(d, exist_ok=True)
        return d

    def test_missing_file_uses_defaults(self):
        cfg = Config.load(os.path.join(self._tmp(), "nope.json"))
        self.assertEqual(cfg.ollama["base_url"], "http://127.0.0.1:11434")
        self.assertEqual(cfg.output["txt_name"], "简介{filename}.txt")
        self.assertEqual(cfg.output["local_mode"], "nfo_first")
        self.assertEqual(cfg.runtime["workers"], 1)

    def test_save_and_reload_roundtrip(self):
        p = os.path.join(self._tmp(), "cfg.json")
        cfg = Config()
        cfg.output["local_mode"] = "txt_only"
        cfg.models["vision"] = "qwen3-vl:8b"
        cfg.save(p)

        cfg2 = Config.load(p)
        self.assertEqual(cfg2.output["local_mode"], "txt_only")
        self.assertEqual(cfg2.models["vision"], "qwen3-vl:8b")

    def test_partial_overrides_keep_defaults(self):
        p = os.path.join(self._tmp(), "partial.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"output": {"local_mode": "txt_only"}}, f)

        cfg = Config.load(p)
        self.assertEqual(cfg.output["local_mode"], "txt_only")
        # 未提供的键保留默认
        self.assertEqual(cfg.output["txt_mode"], "new")
        self.assertEqual(cfg.ollama["base_url"], "http://127.0.0.1:11434")

    def test_invalid_values_fall_back(self):
        cfg = Config({
            "output": {"txt_mode": "BAD", "txt_encoding": "BAD", "local_mode": "BAD"},
            "analysis": {"frame_interval_s": -5},
            "runtime": {"workers": 0},
            "ollama": {"base_url": "not-a-url"},
        })
        self.assertEqual(cfg.output["txt_mode"], "new")
        self.assertEqual(cfg.output["txt_encoding"], "utf-8-sig")
        self.assertEqual(cfg.output["local_mode"], "nfo_first")
        self.assertEqual(cfg.analysis["frame_interval_s"], DEFAULTS["analysis"]["frame_interval_s"])
        self.assertEqual(cfg.runtime["workers"], 1)
        self.assertEqual(cfg.ollama["base_url"], "http://127.0.0.1:11434")

    def test_storage_paths_resolved(self):
        cfg = Config()
        # 默认 storage 应包含非空的 db_path
        self.assertTrue(cfg.db_path.name.endswith(".db"))
        # db_path 可覆盖
        cfg._data["storage"]["db_path"] = "D:/custom/nasva.db"
        self.assertEqual(cfg.db_path, Path("D:/custom/nasva.db"))


if __name__ == "__main__":
    unittest.main()
