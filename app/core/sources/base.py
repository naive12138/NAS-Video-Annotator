# -*- coding: utf-8 -*-
"""视频源统一抽象：本地路径与 Jellyfin 都归一为 VideoSource（见计划书 §5）。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class VideoSource:
    source_type: str                 # 'local' | 'jellyfin'
    file_path: str                   # 本地可访问路径（UNC 或盘符）
    title: str
    jellyfin_item_id: str | None = None
    stream_url: str | None = None    # Jellyfin 源的直链流地址（分析用）
    meta: dict[str, Any] = field(default_factory=dict)


class VideoSourceAdapter(ABC):
    @abstractmethod
    def list_videos(self) -> list[VideoSource]:
        """列出该源下的全部视频。"""
