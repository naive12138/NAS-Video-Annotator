# -*- coding: utf-8 -*-
"""media.py 的 ffmpeg/ffprobe 解析与调用测试（mock _run）。"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

import core.media as M  # noqa: E402


class MediaResolveTest(unittest.TestCase):
    def test_probe_uses_resolved_full_path(self):
        with mock.patch.object(M, "_find", return_value="C:/fake/ffprobe.exe"), \
             mock.patch.object(M, "_run", return_value=(0, b'{"format":{},"streams":[]}', b"")) as run:
            M.probe("x.mp4")
        self.assertEqual(run.call_args[0][0][0], "C:/fake/ffprobe.exe")

    def test_extract_frames_uses_resolved_full_path(self):
        with mock.patch.object(M, "_find", return_value="C:/fake/ffmpeg.exe"), \
             mock.patch.object(M, "_run", return_value=(0, b"", b"")) as run:
            M.extract_frames("x.mp4", os.path.join(os.path.dirname(__file__), "_tmp", "f"), [0.0])
        self.assertEqual(run.call_args[0][0][0], "C:/fake/ffmpeg.exe")

    def test_probe_error_raises(self):
        with mock.patch.object(M, "_find", return_value="C:/fake/ffprobe.exe"), \
             mock.patch.object(M, "_run", return_value=(1, b"", b"boom")):
            with self.assertRaises(M.MediaError) as ctx:
                M.probe("x.mp4")
            self.assertIn("boom", str(ctx.exception))

    def test_missing_raises_media_error(self):
        with mock.patch.object(M, "_find", return_value=None):
            with self.assertRaises(M.MediaError):
                M.probe("x.mp4")


if __name__ == "__main__":
    unittest.main()
