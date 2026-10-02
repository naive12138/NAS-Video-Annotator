# -*- coding: utf-8 -*-
"""task_queue.py 单元测试。"""
import threading
import time
import unittest

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

from core.pipeline import CancelledError  # noqa: E402
from core.task_queue import TaskQueue  # noqa: E402


class _FakePipeline:
    def __init__(self, done, results):
        self.done = done
        self.results = results

    def run(self, video, on_progress=None, cancel_event=None):
        time.sleep(0.01)
        self.done.append(video)
        if "bad" in video:
            raise RuntimeError("boom")


class _CancellablePipeline:
    """一直运行，直到收到取消信号才抛 CancelledError。"""

    def __init__(self):
        self.started = threading.Event()

    def run(self, video, on_progress=None, cancel_event=None):
        self.started.set()
        while True:
            if cancel_event is not None and cancel_event.is_set():
                raise CancelledError()
            time.sleep(0.005)


class TaskQueueTest(unittest.TestCase):
    def test_processes_all(self):
        done = []
        tq = TaskQueue(lambda: _FakePipeline(done, {}), workers=2)
        for i in range(6):
            tq.submit(f"v{i}")
        tq.start()
        tq.wait()
        self.assertEqual(sorted(done), [f"v{i}" for i in range(6)])

    def test_failure_does_not_block_others(self):
        done = []
        statuses = []
        tq = TaskQueue(
            lambda: _FakePipeline(done, {}), workers=1,
            on_status=lambda v, s, m: statuses.append((v, s)),
        )
        tq.submit("good")
        tq.submit("bad")
        tq.start()
        tq.wait()
        self.assertIn("good", done)
        self.assertIn(("bad", "failed"), statuses)
        self.assertIn(("good", "done"), statuses)

    def test_cancel_running_task(self):
        statuses = []
        fake = _CancellablePipeline()
        tq = TaskQueue(lambda: fake, workers=1,
                       on_status=lambda v, s, m: statuses.append((v, s)))
        tq.submit("job")
        tq.start()
        self.assertTrue(fake.started.wait(2))
        self.assertTrue(tq.cancel("job"))
        tq.wait()
        self.assertIn(("job", "cancelled"), statuses)


if __name__ == "__main__":
    unittest.main()
