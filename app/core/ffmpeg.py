# -*- coding: utf-8 -*-
"""FFmpeg 检测与一键下载：下载官方构建并解压 ffmpeg.exe/ffprobe.exe 到应用 bin 目录。"""
from __future__ import annotations

import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

FFMPEG_ZIP_URLS = [
    # gyan.dev：ffmpeg.org 官方推荐的 Windows 构建，国内更易访问（essentials 包较小）
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
    # BtbN：GitHub 上的最新构建（作为回退）
    "https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win64-lgpl.zip",
]


def bin_dir(cfg) -> Path:
    return cfg.storage_path("data_dir") / "bin"


def _find(exe: str, cfg) -> Path | None:
    """按顺序在多个位置查找 ffmpeg/ffprobe。"""
    name = f"{exe}.exe"
    candidates: list[Path] = []
    found = shutil.which(exe)
    if found:
        candidates.append(Path(found))
    data = cfg.storage_path("data_dir")
    exe_dir = Path(sys.executable).resolve().parent
    candidates += [
        data / "bin" / name,      # data\bin\
        data / name,              # data\
        exe_dir / name,           # exe 同目录
        exe_dir / "_internal" / name,  # _internal\
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def find_ffmpeg(cfg) -> Path | None:
    return _find("ffmpeg", cfg)


def find_ffprobe(cfg) -> Path | None:
    return _find("ffprobe", cfg)


def status(cfg) -> dict:
    ff = find_ffmpeg(cfg)
    fp = find_ffprobe(cfg)
    return {
        "ffmpeg": str(ff) if ff else None,
        "ffprobe": str(fp) if fp else None,
        "ok": bool(ff and fp),
    }


def ensure_ffmpeg(cfg, on_progress=None) -> tuple[str, str]:
    """确保 ffmpeg/ffprobe 可用；缺失则下载并解压。返回 (ffmpeg_path, ffprobe_path)。"""
    ff, fp = find_ffmpeg(cfg), find_ffprobe(cfg)
    if ff and fp:
        return str(ff), str(fp)
    bd = bin_dir(cfg)
    bd.mkdir(parents=True, exist_ok=True)
    zip_path = bd / "ffmpeg.zip"

    last_err: Exception | None = None
    for url in FFMPEG_ZIP_URLS:
        try:
            _download(url, zip_path, on_progress)
            last_err = None
            break
        except Exception as e:  # noqa: BLE001
            last_err = e
    if last_err is not None:
        raise RuntimeError(
            f"下载失败（{last_err}）。可手动下载 ffmpeg/ffprobe 后放到 exe 同目录或加入 PATH"
        )

    try:
        _extract(zip_path, bd)
    finally:
        zip_path.unlink(missing_ok=True)
    return str(bd / "ffmpeg.exe"), str(bd / "ffprobe.exe")


def _download(url: str, dest: Path, on_progress=None) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "NASVA/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        with open(dest, "wb") as f:
            while True:
                chunk = r.read(1024 * 256)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if on_progress and total:
                    on_progress(done, total)


def _extract(zip_path: Path, dest: Path) -> None:
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            name = info.filename.replace("\\", "/")
            base = name.rsplit("/", 1)[-1]
            if base in ("ffmpeg.exe", "ffprobe.exe") and "/bin/" in name:
                (dest / base).write_bytes(z.read(info))
