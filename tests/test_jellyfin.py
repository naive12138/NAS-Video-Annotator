# -*- coding: utf-8 -*-
"""Jellyfin 适配与回写的单元测试（mock urllib，不联网）。"""
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

from core.sources.base import VideoSource  # noqa: E402
from core.sources.jellyfin import JellyfinAdapter  # noqa: E402
from core.writers.jellyfin_writer import JellyfinWriter  # noqa: E402


class FakeResp:
    def __init__(self, obj):
        self._obj = obj

    def read(self):
        return json.dumps(self._obj).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class JellyfinAdapterTest(unittest.TestCase):
    def test_list_videos(self):
        payload = {"Items": [
            {"Id": "i1", "Name": "电影A", "Path": "Z:/a.mp4"},
            {"Id": "i2", "Name": "电影B", "Path": "", "MediaSources": [{"Path": "Z:/b.mp4"}]},
            {"Id": "i3", "Name": "无路径"},
        ]}
        with mock.patch("urllib.request.urlopen", return_value=FakeResp(payload)):
            videos = JellyfinAdapter("http://x", "key").list_videos()
        self.assertEqual(len(videos), 2)
        self.assertEqual(videos[0].jellyfin_item_id, "i1")
        self.assertEqual(videos[0].source_type, "jellyfin")

    def test_stream_url(self):
        payload = {"Items": [{"Id": "i1", "Name": "A", "Path": "/config/a.mp4"}]}
        with mock.patch("urllib.request.urlopen", return_value=FakeResp(payload)):
            videos = JellyfinAdapter("http://x", "key").list_videos()
        self.assertEqual(videos[0].stream_url,
                         "http://x/Videos/i1/stream?static=true&api_key=key")
        self.assertEqual(videos[0].file_path, "/config/a.mp4")


class JellyfinWriterTest(unittest.TestCase):
    def test_write_ok(self):
        v = VideoSource("jellyfin", "Z:/a.mp4", "a", jellyfin_item_id="i1")
        with mock.patch("urllib.request.urlopen", return_value=FakeResp({})) as m:
            r = JellyfinWriter("http://x", "key").write(v, {}, "剧情")
        self.assertTrue(r.ok)
        self.assertIn("/Items/i1", m.call_args[0][0].full_url)

    def test_write_missing_item_id(self):
        v = VideoSource("jellyfin", "Z:/a.mp4", "a")
        r = JellyfinWriter("http://x", "key").write(v, {}, "剧情")
        self.assertFalse(r.ok)


if __name__ == "__main__":
    unittest.main()
