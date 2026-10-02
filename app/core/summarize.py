# -*- coding: utf-8 -*-
"""内容汇总：把场景描述 + 转写文本交给文本 LLM，解析出题材/剧情/标签（见计划书 §6.3）。"""
from __future__ import annotations

import json
import re
from typing import Callable

VISION_PROMPT = (
    "用自然、口语化的中文描述这张视频画面，像随手记笔记一样，别用生硬的书面套话。"
    "画面里有什么就写什么，不回避、不美化、不省略露骨/成人情节，也不做道德评判。"
    "顺便数一下画面里有几个人。"
    "只输出 JSON（不要输出其他文字）："
    '{"description": "对画面的具体描述，中文，不超过80字", '
    '"people": 画面里的人数(整数，没看到人就填0)}'
)

TRANSLATE_PROMPT = (
    "把下面的文本翻译成中文，只输出译文本身，不要任何解释、说明或前缀：\n\n{text}"
)


def build_summary_prompt(scene_descriptions: list[str],
                         transcript_text: str = "",
                         max_chars: int = 6000,
                         max_scene_chars: int = 16000,
                         audio_clue: str = "") -> str:
    parts: list[str] = []
    if scene_descriptions:
        parts.append("场景描述（按时间顺序）：")
        for i, d in enumerate(_sample_scenes(scene_descriptions, max_scene_chars), 1):
            parts.append(f"{i}. {d}")
    if transcript_text:
        parts.append("字幕/转写：")
        parts.append(transcript_text[:max_chars])
    if audio_clue:
        parts.append("音频线索：")
        parts.append(audio_clue)
    body = "\n".join(parts)
    return (
        "你是写剧情简介的老手。根据下面这些画面描述和字幕，用自然、流畅的中文把剧情讲清楚，"
        "就像看完片子随口跟人聊剧情那样。\n"
        "要求：\n"
        "- 只写真实剧情，不回避、不美化、不省略露骨/成人情节，也不做道德评判；\n"
        "- 开头结尾若有广告、片头片尾水印等与正片无关的内容就忽略，只写正片；\n"
        "- 去掉 AI 腔和套话：别用“值得注意的是”“综上所述”“整体而言”“本片讲述了”这类开头，"
        "别堆砌空泛成语和“不仅……而且……”这类句式，句子长短交错、说人话；\n"
        "- 题材和标签用常见叫法，别自造生僻词。\n"
        "只输出 JSON（不要输出其他文字）：\n"
        f"{body}\n\n"
        '格式：{"genre": "题材", "genre_confidence": 0到1的小数, '
        '"summary": "分段剧情概括", "tags": ["标签1","标签2"]}'
    )


def _sample_scenes(descs: list[str], max_chars: int) -> list[str]:
    """按字符预算均匀抽样场景描述，避免快剪视频产生过大的汇总提示词导致本地模型超时。"""
    if not descs:
        return []
    total = sum(len(f"{i}. {d}") for i, d in enumerate(descs, 1))
    if total <= max_chars:
        return list(descs)
    n = len(descs)
    k = max(1, int(n * max_chars / total))
    if k >= n:
        return list(descs)
    idxs = {round(i * (n - 1) / (k - 1)) for i in range(k)}
    return [descs[i] for i in sorted(idxs)]


def parse_annotation(raw: str) -> dict:
    """从 LLM 输出解析标注；JSON 解析失败则降级为纯文本。"""
    raw = (raw or "").strip()
    if not raw:
        return _empty()

    # 去掉 ```json ... ``` 代码围栏
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, re.S)
    if m:
        raw = m.group(1).strip()

    obj = None
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            try:
                obj = json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                obj = None

    if isinstance(obj, dict):
        return _normalize(obj)
    return _empty(text=raw)


def parse_vision(raw: str) -> tuple[str, int | None]:
    """解析视觉模型的 JSON 输出，返回 (description, people_count)；失败降级为纯文本。"""
    raw = (raw or "").strip()
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, re.S)
    if m:
        raw = m.group(1).strip()
    obj = None
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            try:
                obj = json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                obj = None
    if isinstance(obj, dict):
        desc = str(obj.get("description", "") or "").strip()
        people = obj.get("people")
        try:
            people = int(people)
        except (TypeError, ValueError):
            people = None
        return desc, people
    return raw, None


def summarize(scene_descriptions: list[str], transcript_text: str,
              llm: Callable[[str], str], max_chars: int = 6000,
              audio_clue: str = "", max_scene_chars: int = 16000) -> dict:
    prompt = build_summary_prompt(scene_descriptions, transcript_text, max_chars,
                                  max_scene_chars=max_scene_chars, audio_clue=audio_clue)
    return parse_annotation(llm(prompt))


def _empty(text: str = "") -> dict:
    return {
        "genre": "",
        "genre_conf": 0.0,
        "one_line": text,
        "summary": text,
        "tags": [],
    }


def _normalize(obj: dict) -> dict:
    tags = obj.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in re.split(r"[,，、]", tags) if t.strip()]
    return {
        "genre": str(obj.get("genre", "") or "").strip(),
        "genre_conf": _to_float(obj.get("genre_confidence", obj.get("confidence", 0.0))),
        "one_line": str(obj.get("one_line", "") or "").strip(),
        "summary": str(obj.get("summary", "") or "").strip(),
        "tags": [str(t).strip() for t in tags if str(t).strip()],
    }


def _to_float(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def is_chinese_text(text: str) -> bool:
    """粗略判断文本是否为中文：含日文假名视为非中文；含中文汉字且无假名视为中文。"""
    text = (text or "").strip()
    if not text:
        return True
    if any('\u3040' <= c <= '\u30ff' for c in text):      # 日文平/片假名
        return False
    if any('\u4e00' <= c <= '\u9fff' for c in text):      # 中文汉字
        return True
    return False


def translate_to_chinese(text: str, llm: Callable[[str], str]) -> str:
    """把文本翻译成中文（本地 LLM），返回译文。"""
    prompt = TRANSLATE_PROMPT.format(text=text)
    return (llm(prompt) or "").strip()


TRANSCRIPT_SUMMARY_PROMPT = (
    "把下面的字幕/对白内容总结成一段简短的中文剧情概括，尽量精简、抓住主线，"
    "只输出概括文字本身，不要任何解释或前缀：\n\n{text}"
)


def summarize_transcript(text: str, llm: Callable[[str], str]) -> str:
    """把（翻译后的）音频文本总结成简短剧情概括，缓解上下文过长问题。"""
    if not (text or "").strip():
        return ""
    prompt = TRANSCRIPT_SUMMARY_PROMPT.format(text=text)
    return (llm(prompt) or "").strip()
