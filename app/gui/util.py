# -*- coding: utf-8 -*-
"""后台线程工具：run_async(fn, on_done) 在线程里执行 fn，结果回到 on_done(result, error)。"""
from __future__ import annotations

import threading
from typing import Callable

from PySide6.QtCore import QObject, Signal


class _Worker(QObject):
    done = Signal(object, object)  # (result, error_str)

    def __init__(self, fn: Callable):
        super().__init__()
        self._fn = fn

    def run(self):
        try:
            self.done.emit(self._fn(), None)
        except Exception as e:  # noqa: BLE001
            self.done.emit(None, str(e))


def run_async(fn: Callable, on_done: Callable):
    """在线程执行 fn()，完成后回调 on_done(result, error_str)。返回 worker 引用（需持有）。"""
    w = _Worker(fn)
    w.done.connect(lambda res, err: on_done(res, err))
    threading.Thread(target=w.run, daemon=True).start()
    return w
