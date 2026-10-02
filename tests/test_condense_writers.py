# -*- coding: utf-8 -*-
"""condense.py 与 writers/ 的单元测试。"""
import os
import shutil
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

from core.condense import condense  # noqa: E402
from core.config import Config  # noqa: E402
from core.sources.base import VideoSource  # noqa: E402
from core.writers import TxtWriter, NfoWriter, JellyfinWriter, writer_for  # noqa: E402


def _tmp():
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tmp")
    os.makedirs(d, exist_ok=True)
    return d


def _fresh_subdir(name):
    d = os.path.join(_tmp(), name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, exist_ok=True)
    return d


class CondenseTest(unittest.TestCase):
    def test_full(self):
        out = condense({
            "genre": "悬疑", "people_count_min": 2, "people_count_max": 3,
            "one_line": "侦探", "summary": "悬案", "tags": ["悬疑", "犯罪"],
        })
        self.assertIn("题材：悬疑", out)
        self.assertIn("人数：2~3 人", out)
        self.assertIn("简介：侦探", out)
        self.assertIn("标签：悬疑、犯罪", out)

    def test_partial(self):
        out = condense({"genre": "纪录片"})
        self.assertEqual(out, "题材：纪录片")


class TxtWriterTest(unittest.TestCase):
    def setUp(self):
        self.dir = _fresh_subdir("txtw")
        self.video = VideoSource("local", os.path.join(self.dir, "movie.mp4"), "movie")

    def test_new_creates(self):
        w = TxtWriter("简介{filename}.txt", "new")
        r = w.write(self.video, {}, "内容")
        self.assertTrue(r.ok)
        self.assertTrue(os.path.exists(os.path.join(self.dir, "简介movie.txt")))

    def test_new_numbering_on_conflict(self):
        with open(os.path.join(self.dir, "简介movie.txt"), "w", encoding="utf-8") as f:
            f.write("旧")
        w = TxtWriter("简介{filename}.txt", "new")
        w.write(self.video, {}, "内容")
        self.assertTrue(os.path.exists(os.path.join(self.dir, "简介movie(1).txt")))

    def test_append(self):
        p = os.path.join(self.dir, "简介movie.txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write("旧")
        w = TxtWriter("简介{filename}.txt", "append")
        w.write(self.video, {}, "新")
        with open(p, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("旧", content)
        self.assertIn("新", content)


class NfoWriterTest(unittest.TestCase):
    def setUp(self):
        self.dir = _fresh_subdir("nfow")
        self.video = VideoSource("local", os.path.join(self.dir, "movie.mp4"), "movie")

    def _write_nfo(self, content):
        p = os.path.join(self.dir, "movie.nfo")
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        return p

    def test_write_preserves_other_fields(self):
        self._write_nfo(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<movie><title>旧标题</title><plot>旧剧情</plot><outline>旧简介</outline>"
            "<tag>x</tag></movie>"
        )
        w = NfoWriter()
        r = w.write(self.video, {"one_line": "一句话"}, "新剧情")
        self.assertTrue(r.ok)
        with open(os.path.join(self.dir, "movie.nfo"), encoding="utf-8") as f:
            content = f.read()
        self.assertIn("新剧情", content)
        self.assertIn("一句话", content)
        self.assertIn("旧标题", content)
        self.assertIn("<tag>x</tag>", content)

    def test_no_nfo_skips(self):
        w = NfoWriter()
        r = w.write(self.video, {}, "x")
        self.assertFalse(r.ok)
        self.assertIn("NFO", r.detail)


class WriterForTest(unittest.TestCase):
    def test_local_without_nfo_uses_txt(self):
        v = VideoSource("local", os.path.join(_tmp(), "no_nfo.mp4"), "x")
        self.assertIsInstance(writer_for(Config(), v), TxtWriter)

    def test_local_with_nfo_uses_nfo(self):
        d = _fresh_subdir("nfo_dispatch")
        v = VideoSource("local", os.path.join(d, "movie.mp4"), "x")
        with open(os.path.join(d, "movie.nfo"), "w", encoding="utf-8") as f:
            f.write("<movie></movie>")
        self.assertIsInstance(writer_for(Config(), v), NfoWriter)

    def test_local_txt_only_with_nfo_uses_txt(self):
        d = _fresh_subdir("txt_only_dispatch")
        v = VideoSource("local", os.path.join(d, "movie.mp4"), "x")
        with open(os.path.join(d, "movie.nfo"), "w", encoding="utf-8") as f:
            f.write("<movie></movie>")
        cfg = Config({"output": {"local_mode": "txt_only"}})
        self.assertIsInstance(writer_for(cfg, v), TxtWriter)

    def test_jellyfin_source_uses_api(self):
        v = VideoSource("jellyfin", "x.mp4", "x", jellyfin_item_id="123")
        self.assertIsInstance(writer_for(Config(), v), JellyfinWriter)


if __name__ == "__main__":
    unittest.main()
