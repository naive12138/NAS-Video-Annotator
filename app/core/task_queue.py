# -*- coding: utf-8 -*-
"""后台任务队列：线程池受限并发执行分析任务（见计划书 §7）。

单视频失败不影响其余任务；状态通过 on_status 回调上报给 GUI。
"""
from __future__ import annotations

import queue
import threading
from typing import Callable

from .pipeline import CancelledError


class TaskQueue:
    def __init__(
        self,
        pipeline_factory: Callable,
        workers: int = 1,
        on_status: Callable | None = None,
        on_progress: Callable | None = None,
    ):
        self._factory = pipeline_factory       # () -> 可调用 .run(video) 的对象
        self._workers = max(1, int(workers))
        self._on_status = on_status            # (video, status, message) -> None
        self._on_progress = on_progress        # (video, percent, message) -> None
        self._q: queue.Queue = queue.Queue()
        self._threads: list[threading.Thread] = []
        self._cancel_flags: dict[int, threading.Event] = {}

    def submit(self, video) -> None:
        self._q.put(video)

    def cancel(self, video) -> bool:
        """请求取消某个正在处理的任务；返回是否真的发起了取消。"""
        flag = self._cancel_flags.get(id(video))
        if flag is not None:
            flag.set()
            return True
        return False

    def start(self) -> None:
        for _ in range(self._workers):
            t = threading.Thread(target=self._worker, daemon=True)
            t.start()
            self._threads.append(t)

    def wait(self) -> None:
        """阻塞直到当前队列全部处理完。"""
        self._q.join()

    def stop(self) -> None:
        for _ in self._threads:
            self._q.put(None)
        for t in self._threads:
            t.join(timeout=2)

    def _emit(self, video, status: str, message: str = "") -> None:
        if self._on_status:
            try:
                self._on_status(video, status, message)
            except Exception:
                pass

    def _emit_progress(self, video, percent: int, message: str = "") -> None:
        if self._on_progress:
            try:
                self._on_progress(video, percent, message)
            except Exception:
                pass

    def _worker(self) -> None:
        while True:
            video = self._q.get()
            if video is None:
                break
            flag = threading.Event()
            self._cancel_flags[id(video)] = flag
            try:
                self._emit(video, "processing", "开始分析")
                pipe = self._factory()
                pipe.run(video,
                         on_progress=lambda p, m: self._emit_progress(video, p, m),
                         cancel_event=flag)
                self._emit(video, "done", "完成")
            except CancelledError:
                self._emit(video, "cancelled", "已取消")
            except Exception as e:
                self._emit(video, "failed", str(e))
            finally:
                self._cancel_flags.pop(id(video), None)
                self._q.task_done()
