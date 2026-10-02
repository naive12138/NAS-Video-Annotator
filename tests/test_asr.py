# -*- coding: utf-8 -*-
"""asr 片段处理测试（不加载真实模型）。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

from core.models.asr import _segments_to_dicts  # noqa: E402


class _Seg:
    def __init__(self, start, end, text):
        self.start = start
        self.end = end
        self.text = text


class AsrTest(unittest.TestCase):
    def test_none_and_empty_text_skipped(self):
        segs = [_Seg(0, 1, "你好"), _Seg(1, 2, None), _Seg(2, 3, ""), _Seg(3, 4, " 世界 ")]
        out = _segments_to_dicts(segs)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["text"], "你好")
        self.assertEqual(out[1]["text"], "世界")

    def test_no_crash_on_missing_text_attr(self):
        class NoText:
            def __init__(self, start, end):
                self.start = start
                self.end = end
        out = _segments_to_dicts([NoText(0, 1)])
        self.assertEqual(out, [])


if __name__ == "__main__":
    unittest.main()
