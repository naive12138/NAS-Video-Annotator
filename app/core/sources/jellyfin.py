# -*- coding: utf-8 -*-
"""Jellyfin 视频源适配：通过 API 拉取媒体库列表（见计划书 §5）。"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from .base import VideoSource, VideoSourceAdapter


class JellyfinAdapter(VideoSourceAdapter):
    def __init__(self, base_url: str, api_key: str, timeout_s: float = 60.0):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key
        self.timeout_s = timeout_s

    def _get_json(self, path: str) -> dict:
        url = self.base_url + path
        req = urllib.request.Request(url, headers={"X-Emby-Token": self.api_key})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
                return json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError) as e:
            hint = ""
            msg = str(e).lower()
            if "timed out" in msg or "timeout" in msg:
                hint = "（可能地址/端口不对、Jellyfin 未运行，或局域网不可达）"
            raise RuntimeError(f"Jellyfin 请求失败（{url}）：{e}{hint}") from e

    def list_videos(self) -> list[VideoSource]:
        path = (
            "/Items?IncludeItemTypes=Movie,Episode,Video"
            "&Recursive=true&Fields=Path,MediaSources"
        )
        data = self._get_json(path)
        result: list[VideoSource] = []
        for it in data.get("Items", []):
            path_ = it.get("Path") or ""
            if not path_:
                sources = it.get("MediaSources") or []
                path_ = sources[0].get("Path", "") if sources else ""
            if not path_:
                continue
            item_id = it.get("Id") or ""
            stream_url = (
                f"{self.base_url}/Videos/{item_id}/stream?static=true&api_key={self.api_key}"
                if item_id else None
            )
            result.append(VideoSource(
                source_type="jellyfin",
                file_path=path_,
                title=it.get("Name") or "",
                jellyfin_item_id=item_id,
                stream_url=stream_url,
            ))
        return result
