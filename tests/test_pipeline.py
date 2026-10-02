# -*- coding: utf-8 -*-
"""pipeline.py 编排单元测试（mock 所有重量级媒体/模型调用）。"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

import core.pipeline as P  # noqa: E402
from core.config import Config  # noqa: E402
from core.sources.base import VideoSource  # noqa: E402
from core.store import Store  # noqa: E402


def _tmp():
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tmp")
    os.makedirs(d, exist_ok=True)
    return d


class FakeClient:
    def generate(self, model, prompt, images=None, **kw):
        if "vision" in model:
            return {"response": '{"description": "夜景街头，两人追逐", "people": 2}'}
        return {"response": '{"genre":"悬疑","genre_confidence":0.9,'
                            '"summary":"一场紧张的追逐戏","tags":["悬疑","犯罪"]}'}


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.db = os.path.join(_tmp(), f"pipeline_{self._testMethodName}.db")
        if os.path.exists(self.db):
            os.remove(self.db)
        self.store = Store(self.db)
        self.cfg = Config()
        self.cfg._data["storage"]["db_path"] = self.db

    def tearDown(self):
        self.store.close()

    def test_run_end_to_end(self):
        video_path = os.path.join(_tmp(), "movie.mp4")
        with open(video_path, "w", encoding="utf-8") as f:
            f.write("x")
        video = VideoSource("local", video_path, "movie")

        pipe = P.Pipeline(
            self.cfg, self.store,
            client=FakeClient(),
            transcribe=lambda p, m="small": [{"start": 0, "end": 1, "text": "你好"}],
        )

        with mock.patch.object(P.media, "probe", return_value={"duration_sec": 10.0}), \
             mock.patch.object(P.media, "detect_scenes", return_value=[(0.0, 10.0)]), \
             mock.patch.object(P.media, "extract_frames",
                               side_effect=lambda p, d, t: [Path(d) / f"f{i}.jpg" for i in range(len(t))]), \
             mock.patch.object(P.media, "extract_audio", return_value=Path("x.wav")), \
             mock.patch.object(pipe, "_describe_frame",
                               return_value=("夜景街头", 2, '{"description": "夜景街头，两人追逐", "people": 2}')):
            ann = pipe.run(video)

        self.assertEqual(ann["genre"], "悬疑")
        self.assertEqual(ann["summary"], "一场紧张的追逐戏")
        self.assertEqual(ann["people_count_min"], 2)
        self.assertEqual(self.store.get_video(1)["status"], "done")
        self.assertEqual(self.store.get_annotation(1)["genre"], "悬疑")
        self.assertEqual(self.store.get_annotation(1)["summary"], "一场紧张的追逐戏")
        # 回写（txt 模式默认）已记录
        self.assertEqual(len(self.store.list_writebacks(1)), 1)
        self.assertEqual(len(self.store.list_errors()), 0)

    def test_run_failure_marks_failed(self):
        video_path = os.path.join(_tmp(), "movie2.mp4")
        with open(video_path, "w", encoding="utf-8") as f:
            f.write("x")
        video = VideoSource("local", video_path, "movie2")
        pipe = P.Pipeline(self.cfg, self.store, client=FakeClient())

        with mock.patch.object(P.media, "probe", side_effect=P.media.MediaError("无 ffprobe")):
            with self.assertRaises(P.media.MediaError):
                pipe.run(video)

        self.assertEqual(self.store.get_video(1)["status"], "failed")
        self.assertEqual(len(self.store.list_errors()), 1)


if __name__ == "__main__":
    unittest.main()
