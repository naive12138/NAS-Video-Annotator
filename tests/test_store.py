# -*- coding: utf-8 -*-
"""store.py 单元测试（SQLite，纯 stdlib）。"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

from core.store import Store  # noqa: E402


def _tmp():
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tmp")
    os.makedirs(d, exist_ok=True)
    return d


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.db = os.path.join(_tmp(), f"test_{self._testMethodName}.db")
        if os.path.exists(self.db):
            os.remove(self.db)
        self.store = Store(self.db)
        self.store.init_schema()

    def tearDown(self):
        self.store.close()

    def _video(self):
        return self.store.upsert_video({
            "source_type": "local",
            "file_path": r"Z:\media\a.mp4",
            "title": "电影A",
            "duration_sec": 5400.0,
        })

    def test_init_schema_creates_all_tables(self):
        conn = self.store._connect()
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for t in ["videos", "analysis_runs", "scenes", "frames", "transcripts",
                  "annotations", "writebacks", "errors"]:
            self.assertIn(t, tables)

    def test_upsert_video_dedup(self):
        v1 = self.store.upsert_video({"source_type": "local", "file_path": "Z:/a.mp4", "title": "A"})
        v2 = self.store.upsert_video({"source_type": "local", "file_path": "Z:/a.mp4", "title": "A2"})
        self.assertEqual(v1, v2)
        self.assertEqual(self.store.get_video(v1)["title"], "A2")
        self.assertEqual(len(self.store.list_videos()), 1)

    def test_run_roundtrip(self):
        vid = self._video()
        rid = self.store.save_run({"video_id": vid, "status": "processing", "model_name": "qwen2.5:7b"})
        self.store.update_run(rid, status="done")
        conn = self.store._connect()
        row = conn.execute("SELECT * FROM analysis_runs WHERE id=?", (rid,)).fetchone()
        self.assertEqual(row["status"], "done")

    def test_annotation_roundtrip(self):
        vid = self._video()
        aid = self.store.save_annotation({
            "video_id": vid, "genre": "悬疑",
            "people_count_min": 2, "people_count_max": 3,
            "one_line": "x", "summary": "y", "tags": json.dumps(["悬疑", "犯罪"]),
        })
        ann = self.store.get_annotation(vid)
        self.assertEqual(ann["genre"], "悬疑")
        self.store.update_annotation(aid, {"genre": "动作"})
        ann2 = self.store.get_annotation(vid)
        self.assertEqual(ann2["genre"], "动作")
        self.assertEqual(ann2["is_edited"], 1)

    def test_delete_annotation(self):
        vid = self._video()
        aid = self.store.save_annotation({"video_id": vid, "genre": "悬疑"})
        self.store.delete_annotation(aid)
        self.assertIsNone(self.store.get_annotation(vid))

    def test_delete_all_annotations(self):
        vid = self._video()
        self.store.save_annotation({"video_id": vid, "genre": "A"})
        self.store.save_annotation({"video_id": vid, "genre": "B"})
        n = self.store.delete_all_annotations()
        self.assertEqual(n, 2)
        self.assertIsNone(self.store.get_annotation(vid))

    def test_writebacks_and_errors(self):
        vid = self._video()
        self.store.record_writeback(vid, "txt", True, "ok")
        self.store.record_writeback(vid, "nfo", False, "无 NFO")
        self.store.record_error(vid, "writeback", "同目录未找到同名 NFO", r"Z:\media\a.mp4")
        self.assertEqual(len(self.store.list_writebacks(vid)), 2)
        errs = self.store.list_errors()
        self.assertEqual(len(errs), 1)
        self.assertIn("NFO", errs[0]["reason"])

    def test_delete_all_errors(self):
        self.store.record_error(None, "test", "e1", "p1")
        self.store.record_error(None, "test", "e2", "p2")
        self.assertEqual(self.store.delete_all_errors(), 2)
        self.assertEqual(self.store.list_errors(), [])

    def test_search_filters(self):
        v1 = self._video()
        self.store.save_annotation({
            "video_id": v1, "genre": "悬疑", "people_count_min": 2, "people_count_max": 3,
            "one_line": "侦探", "summary": "悬案", "tags": json.dumps(["悬疑"]),
        })
        v2 = self.store.upsert_video({"source_type": "jellyfin", "file_path": "J:/b.mp4", "title": "B"})
        self.store.save_annotation({
            "video_id": v2, "genre": "纪录片", "people_count_min": 1, "people_count_max": 2,
            "one_line": "城市", "summary": "日常", "tags": json.dumps(["纪录片"]),
        })
        self.assertEqual(len(self.store.search()), 2)
        self.assertEqual(len(self.store.search(genre="悬疑")), 1)
        self.assertEqual(len(self.store.search(source_type="jellyfin")), 1)
        self.assertEqual(len(self.store.search(query="侦探")), 1)

    def test_export_formats(self):
        vid = self._video()
        self.store.save_annotation({
            "video_id": vid, "genre": "悬疑", "people_count_min": 2, "people_count_max": 3,
            "one_line": "x", "summary": "y", "tags": json.dumps(["悬疑"]),
        })
        for fmt in ["json", "csv", "md"]:
            p = self.store.export(fmt, os.path.join(_tmp(), f"exp_{self._testMethodName}.{fmt}"))
            self.assertTrue(os.path.exists(p))
            self.assertGreater(os.path.getsize(p), 0)


if __name__ == "__main__":
    unittest.main()
