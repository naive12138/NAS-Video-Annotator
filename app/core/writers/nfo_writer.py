# -*- coding: utf-8 -*-
"""本地路径视频回写同目录同名 .nfo（Jellyfin 简介栏来源，见计划书 §6.4）。

有同名 NFO → 写入 <plot>（完整精简文本）与 <outline>（一句话简介），其余字段原样保留；
无 NFO → 返回 ok=False（跳过回写，由上层记录到错误框）。
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from ..sources.base import VideoSource
from .base import ResultWriter, WriteResult


class NfoWriter(ResultWriter):
    def write(self, video: VideoSource, annotation: dict, condensed: str) -> WriteResult:
        nfo_path = Path(video.file_path).with_suffix(".nfo")
        if not nfo_path.exists():
            return WriteResult(False, "nfo", "同目录未找到同名 NFO 文件", str(nfo_path))
        try:
            tree = ET.parse(str(nfo_path))
            root = tree.getroot()
            _set_or_create(root, "plot", condensed)
            _set_or_create(root, "outline", (annotation.get("one_line") or "").strip())
            ET.indent(tree, space="  ")
            tree.write(str(nfo_path), encoding="utf-8", xml_declaration=True)
            return WriteResult(True, "nfo", "已写入 <plot>/<outline>", str(nfo_path))
        except (ET.ParseError, OSError) as e:
            return WriteResult(False, "nfo", f"NFO 写入失败：{e}", str(nfo_path))


def _set_or_create(root: ET.Element, tag: str, text: str) -> ET.Element:
    el = root.find(tag)
    if el is None:
        el = ET.SubElement(root, tag)
    el.text = text
    return el
