# -*- coding: utf-8 -*-
"""音频辅助分析（方案 A / B，明确不做方案 C 的音频事件分类）。

只用标准库 wave + numpy，不引入任何新模型：
- A：按音频静音/停顿合并被误切的快剪场景；
- B：生成“音频结构”文字线索，辅助 LLM 识别片头片尾、判断剧情节奏。
"""
from __future__ import annotations

import bisect
import wave
from pathlib import Path


def _read_mono(wav_path) -> tuple[int, "object"]:
    """读取 WAV 为单声道 float 样本，返回 (采样率, numpy 数组)。"""
    import numpy as np

    with wave.open(str(wav_path), "rb") as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        sw = w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if sw == 2:
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    elif sw == 1:
        x = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) * 256.0
    else:
        x = np.zeros(0, dtype=np.float32)
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return sr, x


def rms_curve(wav_path, window_sec: float = 1.0) -> list[tuple[float, float]]:
    """按窗口计算 RMS 能量曲线，返回 [(窗口起始秒, rms), ...]。"""
    import numpy as np

    sr, x = _read_mono(wav_path)
    if len(x) == 0 or sr <= 0:
        return []
    ws = max(1, int(sr * window_sec))
    out: list[tuple[float, float]] = []
    for i in range(0, len(x), ws):
        seg = x[i:i + ws]
        if len(seg) == 0:
            break
        rms = float(np.sqrt(np.mean(seg.astype(np.float64) ** 2)))
        out.append((round(i / sr, 2), rms))
    return out


def silent_times(rms: list[tuple[float, float]], floor_ratio: float = 0.05) -> list[float]:
    """从能量曲线挑出静音窗口的起始时间（相对峰值低于阈值视为静音）。"""
    if not rms:
        return []
    peak = max(v for _, v in rms) or 1.0
    thr = peak * floor_ratio
    return sorted(t for t, v in rms if v < thr)


def merge_scenes_by_audio(scenes, silent: list[float], tol: float = 2.0,
                          max_span: float = 120.0) -> list[tuple[float, float]]:
    """A：合并“边界附近没有音频停顿”的相邻场景。

    快剪蒙太奇往往音频连续、却被视觉检测切成很多小段；这里把边界时间附近
    tol 秒内没有静音窗口的相邻场景合并，但单个合并后跨度不超过 max_span，
    避免把整段视频并成一个。
    """
    scenes = [tuple(s) for s in scenes]
    if len(scenes) < 2 or not silent:
        return scenes
    silent_sorted = sorted(float(t) for t in silent)
    merged: list[tuple[float, float]] = []
    for s, e in scenes:
        if merged:
            ps, pe = merged[-1]
            near_silence = _has_near(silent_sorted, pe, tol)
            span = e - ps
            if not near_silence and span <= max_span:
                merged[-1] = (ps, max(pe, e))
                continue
        merged.append((s, e))
    return merged


def _has_near(sorted_vals: list[float], t: float, tol: float) -> bool:
    i = bisect.bisect_left(sorted_vals, t - tol)
    return i < len(sorted_vals) and sorted_vals[i] <= t + tol


def silence_segments(silent: list[float], gap: float = 1.5) -> list[tuple[float, float]]:
    """把静音窗口起始时间聚成连续静音段 [(start, end), ...]（窗口按 1 秒计）。"""
    if not silent:
        return []
    ts = sorted(float(t) for t in silent)
    segs: list[tuple[float, float]] = []
    start = prev = ts[0]
    for t in ts[1:]:
        if t - prev > gap:
            segs.append((start, prev + 1.0))
            start = t
        prev = t
    segs.append((start, prev + 1.0))
    return segs


def build_audio_clue(silence_segs, speech_segs, duration: float) -> str:
    """B：生成给 LLM 的音频结构文字线索。"""
    parts: list[str] = []
    speech = sorted((float(s), float(e)) for s, e in speech_segs)
    if speech:
        first, last = speech[0][0], speech[-1][1]
        parts.append(f"有对白时段约 {_fmt(first)}~{_fmt(last)}")
        if first > 5:
            parts.append(f"开头 {_fmt(0)}~{_fmt(first)} 无对白，可能是片头/广告")
        if duration - last > 5:
            parts.append(f"结尾 {_fmt(last)}~{_fmt(duration)} 无对白，可能是片尾/广告")
    else:
        parts.append("全片未识别到对白（可能无台词，或转写失败）")
    if silence_segs:
        shown = "、".join(f"{_fmt(a)}~{_fmt(b)}" for a, b in silence_segs[:5])
        parts.append("静音段：" + shown + ("等" if len(silence_segs) > 5 else ""))
    return "；".join(parts) if parts else ""


def _fmt(sec: float) -> str:
    sec = max(0, int(round(sec)))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
