# -*- coding: utf-8 -*-
"""Jellyfin 源视频回写 Overview（见计划书 §6.4）：POST /Items/{Id}。"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from ..sources.base import VideoSource
from .base import ResultWriter, WriteResult


class JellyfinWriter(ResultWriter):
    def __init__(self, base_url: str, api_key: str, timeout_s: float = 15.0):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key
        self.timeout_s = timeout_s

    def write(self, video: VideoSource, annotation: dict, condensed: str) -> WriteResult:
        item_id = video.jellyfin_item_id
        if not item_id:
            return WriteResult(False, "jellyfin", "缺少 Jellyfin 条目 ID", video.file_path)

        url = f"{self.base_url}/Items/{item_id}"
        payload = json.dumps({"Overview": condensed}).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload, method="POST",
            headers={
                "X-Emby-Token": self.api_key,
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
                r.read()
        except (urllib.error.URLError, OSError) as e:
            return WriteResult(False, "jellyfin", f"更新 Overview 失败：{e}", url)
        return WriteResult(True, "jellyfin", "已更新 Overview", url)
