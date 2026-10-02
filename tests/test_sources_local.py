# -*- coding: utf-8 -*-
"""本地路径扫描单元测试（纯 pathlib，不依赖 ffmpeg）。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

from core.sources.base import VideoSource  # noqa: E402
from core.sources.local import LocalAdapter  # noqa: E402


def _tmp():
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tmp")
    os.makedirs(d, exist_ok=True)
    return d


class LocalAdapterTest(unittest.TestCase):
    def setUp(self):
        self.root = os.path.join(_tmp(), "scan")
        os.makedirs(os.path.join(self.root, "sub"), exist_ok=True)
        for name in ["a.mp4", "b.mkv", "c.txt", "sub/d.mov", "sub/e.MP4",
                     "f.jpg", "g.png", "h.jpeg", "i.webp", "j.gif", "k.srt"]:
            p = os.path.join(self.root, *name.split("/"))
            with open(p, "w", encoding="utf-8") as f:
                f.write("x")
        # 后缀是 .mp4 但内容其实是 JPG 的“伪装图片”，应被内容识别排除
        with open(os.path.join(self.root, "fake.mp4"), "wb") as f:
            f.write(b"\xff\xd8\xff\xe0\x00\x10JFIF")

    def test_scan_filters_by_extension(self):
        adapter = LocalAdapter([self.root], [".mp4", ".mkv", ".mov"])
        videos = adapter.list_videos()
        titles = sorted(v.title for v in videos)
        # 只收真视频；txt / 图片 / 字幕 / 伪装成 .mp4 的图片 全部排除
        self.assertEqual(titles, ["a", "b", "d", "e"])
        self.assertTrue(all(v.source_type == "local" for v in videos))

    def test_source_fields(self):
        adapter = LocalAdapter([self.root], [".mp4"])
        v = next(x for x in adapter.list_videos() if x.title == "a")
        self.assertEqual(v.source_type, "local")
        self.assertTrue(v.file_path.endswith("a.mp4"))

    def test_missing_root_returns_empty(self):
        adapter = LocalAdapter([os.path.join(self.root, "nope")], [".mp4"])
        self.assertEqual(adapter.list_videos(), [])


if __name__ == "__main__":
    unittest.main()
