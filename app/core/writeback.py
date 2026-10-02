# -*- coding: utf-8 -*-
"""回写执行：精简 → 选写入器 → 写入 → 落库（成功/失败都记录）。"""
from __future__ import annotations

from . import condense
from .sources.base import VideoSource
from .store import Store
from .writers import writer_for


def writeback(cfg, store: Store, video: VideoSource, annotation: dict, video_id: int):
    """执行回写，返回 (WriteResult, condensed_text)。"""
    condensed = condense.condense(annotation)
    writer = writer_for(cfg, video)
    result = writer.write(video, annotation, condensed)
    store.record_writeback(video_id, result.target, result.ok, result.detail)
    if not result.ok:
        store.record_error(video_id, "writeback", result.detail, result.path or video.file_path)
    return result, condensed
