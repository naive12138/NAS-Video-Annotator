# -*- coding: utf-8 -*-
"""媒体处理：ffprobe 元数据 / 抽帧 / 场景切分 / 音轨提取。

依赖外部二进制 ffmpeg/ffprobe 与 Python 包 PySceneDetect，运行时才需要，
缺失时抛出 MediaError 并给出可读提示。
"""
from __future__ import annotations

import atexit
import json
import shutil
import subprocess
import sys
from pathlib import Path

# 隐藏子进程的 CMD 窗口（仅 Windows 有效；其它平台为 0，无副作用）
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class MediaError(Exception):
    pass


_EXTRA_BIN_DIRS: set[Path] = set()


def register_bin_dir(path) -> None:
    """注册额外的二进制搜索目录（如应用下载的 ffmpeg 所在目录）。"""
    if path:
        _EXTRA_BIN_DIRS.add(Path(path))


def _find(exe: str) -> str | None:
    p = shutil.which(exe)
    if p:
        return p
    name = f"{exe}.exe"
    for d in _EXTRA_BIN_DIRS:
        cand = d / name
        if cand.exists():
            return str(cand)
    adjacent = Path(sys.executable).parent / name
    if adjacent.exists():
        return str(adjacent)
    return None


def _require(exe: str) -> str:
    path = _find(exe)
    if not path:
        raise MediaError(f"未找到 {exe}，请在“设置”页一键下载 FFmpeg，或安装后加入 PATH")
    return path


def _decode(raw) -> str:
    """把 subprocess 输出安全转成字符串（兼容 None/bytes/str）。"""
    if not raw:
        return ""
    if isinstance(raw, str):
        return raw
    try:
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return str(raw)


_RUNNING_PROCS: set = set()


def _kill_running_procs():
    for p in list(_RUNNING_PROCS):
        try:
            p.kill()
        except Exception:
            pass


atexit.register(_kill_running_procs)


def _run(cmd):
    """运行 ffmpeg/ffprobe，跟踪进程以便退出时统一终止。返回 (returncode, stdout, stderr)。"""
    p = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        creationflags=_CREATE_NO_WINDOW,
    )
    _RUNNING_PROCS.add(p)
    try:
        out, err = p.communicate()
        return p.returncode, out, err
    finally:
        _RUNNING_PROCS.discard(p)


def probe(file_path: str | Path) -> dict:
    """用 ffprobe 提取视频元数据，返回 videos 表所需字段。"""
    ffprobe = _require("ffprobe")
    cmd = [ffprobe, "-v", "error", "-print_format", "json",
           "-show_format", "-show_streams", str(file_path)]
    returncode, out, err = _run(cmd)
    if returncode != 0:
        raise MediaError(_decode(err) or "ffprobe 失败")

    data = json.loads(_decode(out) or "{}")
    fmt = data.get("format", {})
    video_stream = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "video"), {}
    )

    fps = None
    for key in ("avg_frame_rate", "r_frame_rate"):
        v = video_stream.get(key)
        if v and "/" in v:
            num, den = v.split("/")
            try:
                if float(den) != 0:
                    fps = float(num) / float(den)
                    break
            except ValueError:
                continue

    return {
        "duration_sec": _to_float(fmt.get("duration")),
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
        "fps": fps,
        "codec": video_stream.get("codec_name"),
        "size_bytes": _to_int(fmt.get("size")),
    }


def extract_frames(file_path: str | Path, out_dir: str | Path,
                   times: list[float]) -> list[Path]:
    """按时间点各抽 1 帧，返回生成的图片路径列表。"""
    ffmpeg = _require("ffmpeg")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i, t in enumerate(times):
        out = out_dir / f"frame_{i:05d}_{t:07.2f}.jpg"
        cmd = [ffmpeg, "-y", "-ss", f"{t:.3f}", "-i", str(file_path),
               "-frames:v", "1", "-q:v", "2", str(out)]
        returncode, _out, err = _run(cmd)
        if returncode != 0:
            raise MediaError(_decode(err) or f"抽帧失败 @ {t}s")
        paths.append(out)
    return paths


def extract_audio(file_path: str | Path, out_path: str | Path) -> Path:
    """提取 16kHz 单声道音轨（供 ASR），返回音频文件路径。"""
    ffmpeg = _require("ffmpeg")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg, "-y", "-i", str(file_path), "-vn",
           "-ac", "1", "-ar", "16000", str(out_path)]
    returncode, _out, err = _run(cmd)
    if returncode != 0:
        raise MediaError(_decode(err) or "音轨提取失败")
    return out_path


def detect_scenes(file_path: str | Path, threshold: float = 27.0) -> list[tuple[float, float]]:
    """用 PySceneDetect 切分场景，返回 [(start_sec, end_sec), ...]。"""
    try:
        from scenedetect import ContentDetector, detect
    except ImportError as e:
        raise MediaError("未安装 PySceneDetect") from e

    scenes = detect(str(file_path), ContentDetector(threshold=threshold))
    return [(s[0].get_seconds(), s[1].get_seconds()) for s in scenes]


def _to_float(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _to_int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
