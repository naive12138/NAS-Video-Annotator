# -*- coding: utf-8 -*-
"""faster-whisper 语音转写 + 模型手动下载（国内镜像）。

转写模型不再运行时自动从 HuggingFace 下载；改为在设置页手动下载到
data/asr_models/<模型名>/，转写时按本地目录加载。
"""
from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path

# 一个 faster-whisper(CTranslate2) 模型目录所需的文件
_MODEL_FILES = ["config.json", "tokenizer.json"]
_VOCAB_FILES = ["vocabulary.json", "vocabulary.txt"]  # 词表命名兼容两种
_MIRROR_BASES = [
    "https://hf-mirror.com",      # 国内镜像（优先）
    "https://huggingface.co",     # 官方源（回退）
]


class ASRError(Exception):
    pass


def _repo_id(model_name: str) -> str:
    return f"Systran/faster-whisper-{model_name}"


def model_dir(cfg, model_name: str) -> Path:
    return cfg.asr_model_path(model_name)


def is_model_ready(cfg, model_name: str) -> bool:
    """判断本地是否已有可加载的 ASR 模型目录。"""
    d = model_dir(cfg, model_name)
    return (d / "model.bin").exists() and (d / "config.json").exists() \
        and (d / "tokenizer.json").exists()


def _download(url: str, dest: Path, on_progress=None) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "NASVA/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            while True:
                chunk = r.read(1024 * 256)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if on_progress and total:
                    on_progress(done, total)


def _download_one(url: str, dest: Path, on_progress=None) -> None:
    last_err: Exception | None = None
    for base in _MIRROR_BASES:
        try:
            _download(f"{base}/{url}", dest, on_progress)
            return
        except (urllib.error.URLError, OSError) as e:
            last_err = e
    raise RuntimeError(str(last_err) if last_err else "下载失败")


def download_model(cfg, model_name: str, on_progress=None) -> Path:
    """从国内镜像下载 ASR 模型到本地目录（已在本地则跳过）。"""
    dest = model_dir(cfg, model_name)
    if is_model_ready(cfg, model_name):
        return dest
    repo = _repo_id(model_name)
    dest.mkdir(parents=True, exist_ok=True)

    # 小文件：config / tokenizer
    for fname in _MODEL_FILES:
        _download_one(f"{repo}/resolve/main/{fname}", dest / fname)

    # 词表：vocabulary.json / vocabulary.txt 二选一
    vocab_ok = False
    for fname in _VOCAB_FILES:
        try:
            _download_one(f"{repo}/resolve/main/{fname}", dest / fname)
            vocab_ok = True
            break
        except RuntimeError:
            continue
    if not vocab_ok:
        raise RuntimeError("词表 vocabulary 下载失败（已尝试 vocabulary.json / vocabulary.txt）")

    # model.bin 较大（几百 MB），最后下载并回传进度
    _download_one(f"{repo}/resolve/main/model.bin", dest / "model.bin", on_progress)
    return dest


def transcribe(audio_path: str | Path, model_path: str | Path,
               device: str = "cpu", compute_type: str | None = None) -> tuple[list[dict], dict]:
    """转写音轨，返回 (片段列表, 识别信息)。

    片段列表形如 [{"start": s, "end": e, "text": t}, ...]；识别信息含 language/duration/device。
    device 为 'cpu' 或 'cuda'；compute_type 为 None 时按设备自动选择。
    model_path 为本地模型目录；未下载时抛 ASRError，由上层静默跳过。
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise ASRError("未安装 faster-whisper") from e

    if compute_type is None:
        compute_type = "float16" if device == "cuda" else "int8"

    p = Path(model_path)
    if not (p / "model.bin").exists():
        raise ASRError(f"ASR 模型未下载（{p}），请在“设置”页下载")

    # 自己读 WAV 成 float32 数组，绕开 av 解码（av 版本兼容问题可能把音频读成静音）
    samples, sample_rate = _read_wav_samples(str(audio_path))

    def _load(dev: str, ct: str):
        return WhisperModel(str(p), device=dev, compute_type=ct)

    used_device = device
    try:
        model = _load(device, compute_type)
        segments, info = model.transcribe(samples)
    except Exception:
        # GPU 不可用/初始化失败时回退 CPU，避免整个转写失败
        if device != "cpu":
            used_device = "cpu"
            model = _load("cpu", "int8")
            segments, info = model.transcribe(samples)
        else:
            raise

    segs = _segments_to_dicts(segments)
    model_bin = p / "model.bin"
    model_mb = round(model_bin.stat().st_size / (1024 * 1024), 1) if model_bin.exists() else 0.0
    info_dict = {
        "language": getattr(info, "language", ""),
        "language_probability": getattr(info, "language_probability", None),
        "duration": getattr(info, "duration", None),
        "audio_seconds": round(len(samples) / sample_rate, 2) if sample_rate else 0.0,
        "model_size_mb": model_mb,
        "device": used_device,
    }
    return segs, info_dict


def _read_wav_samples(wav_path: str) -> tuple:
    """用标准库 wave + numpy 读 WAV 为 float32 单声道样本，返回 (样本数组, 采样率)。"""
    import wave
    import numpy as np

    with wave.open(wav_path, "rb") as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        sw = w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if sw == 2:
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sw == 1:
        x = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    else:
        x = np.zeros(0, dtype=np.float32)
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x, sr


def _segments_to_dicts(segments) -> list[dict]:
    """把 faster-whisper 的 segments 转成字典列表，兼容 text 为 None/空串的情况。"""
    result: list[dict] = []
    for s in segments:
        text = (getattr(s, "text", None) or "").strip()
        if text:
            result.append({
                "start": round(float(s.start), 2),
                "end": round(float(s.end), 2),
                "text": text,
            })
    return result
