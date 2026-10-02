# -*- coding: utf-8 -*-
"""readiness.py 与 ollama_client 的纯逻辑单元测试（不联网、不加载模型）。"""
import os
import shutil
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

from core.config import Config  # noqa: E402
from core.models.ollama_client import model_name_matches  # noqa: E402
import core.readiness as R  # noqa: E402


def _tmp():
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tmp")
    os.makedirs(d, exist_ok=True)
    return d


class ModelNameMatchTest(unittest.TestCase):
    def test_exact_match(self):
        self.assertTrue(model_name_matches("qwen2.5vl:7b", ["qwen2.5vl:7b", "llava:7b"]))

    def test_prefix_without_tag(self):
        self.assertTrue(model_name_matches("qwen2.5vl", ["qwen2.5vl:7b"]))

    def test_no_false_partial_match(self):
        self.assertFalse(model_name_matches("qwen2.5", ["qwen2.5vl:7b"]))

    def test_empty_wanted(self):
        self.assertFalse(model_name_matches("", ["qwen2.5vl:7b"]))


class ReadinessTest(unittest.TestCase):
    def test_check_all_structure(self):
        fake = mock.MagicMock()
        fake.server_version.return_value = "0.1.0"
        fake.model_names.return_value = ["qwen2.5vl:7b", "qwen2.5:7b"]
        with mock.patch.object(R, "OllamaClient", return_value=fake):
            res = R.check_all(Config())
        self.assertEqual(len(res), 4)
        for item in res:
            self.assertIn("item", item)
            self.assertIn("ready", item)
            self.assertIn("reason", item)
        # 视觉/文本模型已“安装” → ready
        self.assertTrue(res[1]["ready"])
        self.assertTrue(res[2]["ready"])

    def test_check_all_server_down(self):
        fake = mock.MagicMock()
        fake.server_version.side_effect = R.OllamaError("conn refused")
        with mock.patch.object(R, "OllamaClient", return_value=fake):
            res = R.check_all(Config())
        self.assertFalse(res[0]["ready"])
        self.assertIn("模型服务", res[0]["item"])

    def test_check_asr_model_ready(self):
        cfg = Config()
        tmp = os.path.join(_tmp(), "asr_models")
        shutil.rmtree(tmp, ignore_errors=True)  # 清理上次残留
        cfg._data["storage"]["asr_models_dir"] = tmp
        name = cfg.models["asr"]
        self.assertFalse(R.check_asr_model(cfg)["ready"])
        d = os.path.join(tmp, name)
        os.makedirs(d, exist_ok=True)
        for f in ("model.bin", "config.json", "tokenizer.json"):
            with open(os.path.join(d, f), "w", encoding="utf-8") as fh:
                fh.write("x")
        self.assertTrue(R.check_asr_model(cfg)["ready"])


if __name__ == "__main__":
    unittest.main()
