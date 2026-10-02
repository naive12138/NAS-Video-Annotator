# -*- coding: utf-8 -*-
"""回写同目录 .txt（见计划书 §6.4）。

文件名默认 ``简介{视频文件名}.txt``（"简介"二字固定）；append=继续写入，new=新建且重名顺延 (1)(2)…。
"""
from __future__ import annotations

from pathlib import Path

from ..sources.base import VideoSource
from .base import ResultWriter, WriteResult


class TxtWriter(ResultWriter):
    def __init__(self, name_template: str = "简介{filename}.txt",
                 mode: str = "new", encoding: str = "utf-8-sig"):
        self.name_template = name_template
        self.mode = mode          # 'append' | 'new'
        self.encoding = encoding

    def _resolve_path(self, video: VideoSource) -> Path:
        stem = Path(video.file_path).stem
        filename = self.name_template.replace("{filename}", stem)
        return Path(video.file_path).with_name(filename)

    def write(self, video: VideoSource, annotation: dict, condensed: str) -> WriteResult:
        path = self._resolve_path(video)
        try:
            if self.mode == "append" and path.exists():
                with path.open("a", encoding=self.encoding) as f:
                    f.write("\n---\n" + condensed)
                return WriteResult(True, "txt", "已追加写入", str(path))
            if path.exists():
                path = self._next_available(path)
            path.write_text(condensed, encoding=self.encoding)
            return WriteResult(True, "txt", "已写入", str(path))
        except OSError as e:
            return WriteResult(False, "txt", f"写入失败：{e}", str(path))

    @staticmethod
    def _next_available(path: Path) -> Path:
        i = 1
        candidate = path.with_name(f"{path.stem}({i}){path.suffix}")
        while candidate.exists():
            i += 1
            candidate = path.with_name(f"{path.stem}({i}){path.suffix}")
        return candidate
