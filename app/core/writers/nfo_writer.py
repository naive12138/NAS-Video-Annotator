# -*- coding: utf-8 -*-
"""本地路径视频回写同目录 NFO（Jellyfin 简介栏来源，见计划书 §6.4）。

检测该视频目录下存在的所有 NFO（movie.nfo 与同名 .nfo），有几个写几个；
一个都没有则返回 ok=False（跳过回写，由上层记录到错误框）。
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from ..sources.base import VideoSource
from .base import ResultWriter, WriteResult


def find_nfos(video: VideoSource) -> list[Path]:
    """查找该视频目录下已存在的所有 NFO（不会跨视频写串）：
    movie.nfo（Jellyfin 文件夹约定）与 {视频名}.nfo（侧车约定），有几个返回几个。
    """
    d = Path(video.file_path).parent
    found: list[Path] = []
    for p in (d / "movie.nfo", Path(video.file_path).with_suffix(".nfo")):
        if p.exists() and p not in found:
            found.append(p)
    return found


class NfoWriter(ResultWriter):
    def write(self, video: VideoSource, annotation: dict, condensed: str) -> WriteResult:
        nfo_paths = find_nfos(video)
        if not nfo_paths:
            return WriteResult(False, "nfo", "同目录未找到 NFO（movie.nfo 或同名 .nfo）",
                               str(Path(video.file_path).parent))
        summary = (annotation.get("summary") or "").strip()
        one_line = (annotation.get("one_line") or "").strip()
        try:
            for nfo_path in nfo_paths:
                tree = ET.parse(str(nfo_path))
                root = tree.getroot()
                # 保证 <plot>/<outline> 位于 <movie> 开头（与刮削器生成的 NFO 结构一致）
                _upsert_top(root, "plot", summary, 0)
                _upsert_top(root, "outline", one_line or summary, 1)
                ET.indent(tree, space="  ")
                tree.write(str(nfo_path), encoding="utf-8", xml_declaration=True)
            return WriteResult(True, "nfo", f"已写入 {len(nfo_paths)} 个 NFO 的 <plot>/<outline>",
                               str(Path(video.file_path).parent))
        except (ET.ParseError, OSError) as e:
            return WriteResult(False, "nfo", f"NFO 写入失败：{e}", str(Path(video.file_path).parent))


def _upsert_top(root: ET.Element, tag: str, text: str, index: int) -> ET.Element:
    """删除已有的同名子元素，并在指定位置重新插入（保证 plot/outline 位于开头）。"""
    for old in root.findall(tag):
        root.remove(old)
    el = ET.Element(tag)
    el.text = text
    root.insert(index, el)
    return el
