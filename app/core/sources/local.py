# -*- coding: utf-8 -*-
"""本地路径视频源：递归扫描目录，按扩展名 + 文件内容双重过滤视频。"""
from __future__ import annotations

import os
import time
from pathlib import Path
from threading import Event
from typing import Callable

from .base import VideoSource, VideoSourceAdapter

# 固定视频扩展名白名单：只有这些才算视频
VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".ts", ".m4v",
    ".wmv", ".flv", ".rmvb", ".mpg", ".mpeg", ".m2ts",
    ".webm", ".3gp", ".vob", ".m2t", ".mts", ".m2v",
    ".f4v", ".divx", ".asf", ".ogm", ".ogv",
}


def _is_image_content(head: bytes) -> bool:
    """根据文件头魔数判断是不是图片（用于排除被错误命名为视频后缀的图片）。"""
    if head.startswith(b"\xff\xd8\xff"):            # JPEG
        return True
    if head.startswith(b"\x89PNG\r\n\x1a\n"):      # PNG
        return True
    if head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):  # GIF
        return True
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":  # WebP
        return True
    if head.startswith(b"BM"):                       # BMP
        return True
    return False


class LocalAdapter(VideoSourceAdapter):
    def __init__(self, roots: list[str | Path], extensions: list[str] | None = None):
        self.roots = [Path(r) for r in roots]
        # 固定只认视频格式，忽略外部传入的扩展名
        self.extensions = VIDEO_EXTENSIONS
        self.warning_count = 0

    def list_videos(
        self, *, on_progress: Callable[[str, int, int], None] | None = None,
        on_batch: Callable[[list[VideoSource]], None] | None = None,
        cancel_event: Event | None = None,
    ) -> list[VideoSource]:
        """用 os.walk 流式遍历；后缀是视频、但内容其实是图片的文件会被排除。"""
        result: list[VideoSource] = []
        batch: list[VideoSource] = []
        self.warning_count = 0
        current = ""
        last_notice = time.monotonic()

        def cancelled():
            return cancel_event is not None and cancel_event.is_set()

        def report(force=False):
            nonlocal last_notice, batch
            now = time.monotonic()
            if force or now - last_notice >= 0.1:
                if batch and on_batch:
                    on_batch(batch)
                    batch = []
                if on_progress:
                    on_progress(current, len(result), self.warning_count)
                last_notice = now

        def walk_error(_error):
            self.warning_count += 1

        for root in self.roots:
            if cancelled():
                break
            current = str(root)
            report()
            try:
                is_directory = root.is_dir()
            except OSError:
                is_directory = False
            if not is_directory:
                self.warning_count += 1
                continue
            for dirpath, _dirnames, filenames in os.walk(root, onerror=walk_error):
                if cancelled():
                    break
                current = dirpath
                report()
                for name in filenames:
                    if cancelled():
                        break
                    p = Path(dirpath) / name
                    if p.suffix.lower() not in self.extensions:
                        report()
                        continue
                    try:
                        if self._looks_like_image(p):
                            report()
                            continue
                        if cancelled():
                            break
                        size = p.stat().st_size
                    except OSError:
                        self.warning_count += 1
                        report()
                        continue
                    if cancelled():
                        break
                    video = VideoSource(
                        source_type="local",
                        file_path=str(p),
                        title=p.stem,
                        meta={"size_bytes": size},
                    )
                    result.append(video)
                    if on_batch:
                        batch.append(video)
                        if len(batch) >= 50:
                            on_batch(batch)
                            batch = []
                    report()
        # Deliver the last partial batch even when cancellation was requested.
        report(force=True)
        return result

    @staticmethod
    def _looks_like_image(path: Path) -> bool:
        with open(path, "rb") as f:
            head = f.read(12)
        return _is_image_content(head)
