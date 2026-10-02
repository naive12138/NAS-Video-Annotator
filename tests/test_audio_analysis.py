# -*- coding: utf-8 -*-
"""audio_analysis.py 单元测试（方案 A/B，不加载模型、不联网）。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

from core import audio_analysis as AA  # noqa: E402


class SilentTimesTest(unittest.TestCase):
    def test_peak_relative(self):
        rms = [(0.0, 1000), (1.0, 10), (2.0, 2000), (3.0, 20)]
        self.assertEqual(AA.silent_times(rms, floor_ratio=0.05), [1.0, 3.0])

    def test_empty(self):
        self.assertEqual(AA.silent_times([]), [])


class MergeScenesTest(unittest.TestCase):
    def test_merge_without_silence(self):
        scenes = [(0, 3), (3, 6), (6, 10), (10, 20)]
        silent = [9.0]  # 静音在 9s，接近第三段边界 10s
        merged = AA.merge_scenes_by_audio(scenes, silent, tol=2.0)
        self.assertEqual(merged, [(0, 10), (10, 20)])

    def test_keep_with_silence(self):
        scenes = [(0, 5), (5, 10)]
        silent = [5.0]
        self.assertEqual(AA.merge_scenes_by_audio(scenes, silent, tol=2.0), [(0, 5), (5, 10)])

    def test_max_span_cap(self):
        scenes = [(0, 60), (60, 120), (120, 180)]
        silent = [99999.0]  # 远离所有边界 → 本应合并，但被 max_span 限制
        merged = AA.merge_scenes_by_audio(scenes, silent, tol=2.0, max_span=120.0)
        self.assertEqual(merged, [(0, 120), (120, 180)])

    def test_no_silent_returns_original(self):
        scenes = [(0, 3), (3, 6)]
        self.assertEqual(AA.merge_scenes_by_audio(scenes, []), scenes)


class BuildAudioClueTest(unittest.TestCase):
    def test_speech_and_silence(self):
        clue = AA.build_audio_clue([(0.0, 30.0), (3500.0, 3600.0)], [(30.0, 3500.0)], 3600.0)
        self.assertIn("有对白", clue)
        self.assertIn("片头", clue)
        self.assertIn("片尾", clue)
        self.assertIn("静音段", clue)

    def test_no_speech(self):
        clue = AA.build_audio_clue([], [], 3600.0)
        self.assertEqual(clue, "全片未识别到对白（可能无台词，或转写失败）")


if __name__ == "__main__":
    unittest.main()
