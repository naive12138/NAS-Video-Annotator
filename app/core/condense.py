# -*- coding: utf-8 -*-
"""把标注对象精简成一段回写文本（见计划书 §6.4）。"""
from __future__ import annotations

from typing import Any


def condense(annotation: dict[str, Any]) -> str:
    genre = (annotation.get("genre") or "").strip()
    pmin = annotation.get("people_count_min")
    pmax = annotation.get("people_count_max")
    one_line = (annotation.get("one_line") or "").strip()
    summary = (annotation.get("summary") or "").strip()
    tags = annotation.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]

    lines: list[str] = []
    if genre:
        lines.append(f"题材：{genre}")
    if pmin is not None and pmax is not None:
        lines.append(f"人数：{pmin}~{pmax} 人")
    if one_line:
        lines.append(f"简介：{one_line}")
    if summary:
        lines.append(f"剧情：{summary}")
    if tags:
        lines.append(f"标签：{'、'.join(str(t) for t in tags)}")
    return "\n".join(lines)
