# -*- coding: utf-8 -*-
"""回写模块：按视频来源自动选择写入位置。"""
from pathlib import Path

from .base import ResultWriter, WriteResult
from .txt_writer import TxtWriter
from .nfo_writer import NfoWriter
from .jellyfin_writer import JellyfinWriter


def writer_for(cfg, video) -> ResultWriter:
    """按视频来源与回写方式选择写入器：
    - Jellyfin 源 → 写 Jellyfin 简介栏（API Overview）
    - 本地源 → 按 local_mode：
        "nfo_first"=优先同名 .nfo，无则写 .txt；"txt_only"=始终写 .txt
    """
    if getattr(video, "source_type", None) == "jellyfin":
        return JellyfinWriter(cfg.jellyfin["base_url"], cfg.jellyfin["api_key"])

    local_mode = cfg.output.get("local_mode", "nfo_first")
    if local_mode == "nfo_first":
        nfo_path = Path(video.file_path).with_suffix(".nfo")
        if nfo_path.exists():
            return NfoWriter()
    return TxtWriter(
        name_template=cfg.output["txt_name"],
        mode=cfg.output["txt_mode"],
        encoding=cfg.output["txt_encoding"],
    )


__all__ = ["ResultWriter", "WriteResult", "TxtWriter", "NfoWriter",
           "JellyfinWriter", "writer_for"]
