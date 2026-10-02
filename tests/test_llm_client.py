# -*- coding: utf-8 -*-
"""LLM 客户端（Ollama 原生 / OpenAI 兼容）自动探测与调用测试。"""
import json
import os
import sys
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

from core.models.ollama_client import OllamaClient  # noqa: E402


class _Resp:
    def __init__(self, obj):
        self._obj = obj

    def read(self):
        return json.dumps(self._obj).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _openai_urlopen(req, timeout=None):
    url = req.full_url
    if "/api/tags" in url:
        raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
    if "/v1/models" in url:
        return _Resp({"data": [{"id": "qwen2.5vl:7b"}, {"id": "llama3.1:8b"}]})
    if "/v1/chat/completions" in url:
        return _Resp({"choices": [{"message": {"content": '{"genre":"悬疑"}'}}]})
    raise AssertionError(f"unexpected url {url}")


def _ollama_urlopen(req, timeout=None):
    url = req.full_url
    if "/api/tags" in url:
        return _Resp({"models": [{"name": "qwen2.5vl:7b"}]})
    if "/api/version" in url:
        return _Resp({"version": "0.1.0"})
    if "/api/generate" in url:
        return _Resp({"response": "hi"})
    raise AssertionError(f"unexpected url {url}")


class LlmClientTest(unittest.TestCase):
    def test_openai_style_detection(self):
        with mock.patch("urllib.request.urlopen", side_effect=_openai_urlopen):
            c = OllamaClient("http://127.0.0.1:8080")
            self.assertEqual(c.api_style, "openai")
            self.assertEqual(c.model_names(), ["qwen2.5vl:7b", "llama3.1:8b"])
            self.assertTrue(c.is_model_installed("qwen2.5vl"))
            self.assertEqual(c.generate("qwen2.5vl:7b", "hi")["response"], '{"genre":"悬疑"}')

    def test_ollama_style_detection(self):
        with mock.patch("urllib.request.urlopen", side_effect=_ollama_urlopen):
            c = OllamaClient("http://127.0.0.1:11434")
            self.assertEqual(c.api_style, "ollama")
            self.assertEqual(c.model_names(), ["qwen2.5vl:7b"])
            self.assertEqual(c.generate("qwen2.5vl:7b", "hi")["response"], "hi")

    def test_generate_uses_generate_timeout(self):
        captured = {}

        def _capture(req, timeout=None):
            url = req.full_url
            if "/api/tags" in url:
                raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
            if "/v1/models" in url:
                return _Resp({"data": [{"id": "qwen2.5vl:7b"}]})
            if "/v1/chat/completions" in url:
                captured["timeout"] = timeout
                return _Resp({"choices": [{"message": {"content": "hi"}}]})
            raise AssertionError(f"unexpected url {url}")

        with mock.patch("urllib.request.urlopen", side_effect=_capture):
            c = OllamaClient("http://127.0.0.1:8080", generate_timeout_s=1234)
            c.generate("qwen2.5vl:7b", "hi")
        self.assertEqual(captured["timeout"], 1234)


if __name__ == "__main__":
    unittest.main()
