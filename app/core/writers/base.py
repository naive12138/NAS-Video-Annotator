# -*- coding: utf-8 -*-
"""回写器抽象。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..sources.base import VideoSource


@dataclass
class WriteResult:
    ok: bool
    target: str          # 'txt' | 'nfo' | 'jellyfin'
    detail: str          # 结果说明 / 错误原因
    path: str = ""


class ResultWriter(ABC):
    @abstractmethod
    def write(self, video: VideoSource, annotation: dict, condensed: str) -> WriteResult:
        """把精简文本写入目标位置；失败返回 ok=False 与原因，不抛异常。"""
