# -*- coding: utf-8 -*-
"""配置中心：软件内唯一的配置读写入口。

规则（见计划书 §2）：
- 默认路径 ``%APPDATA%\\NasVideoAnalyzer\\config.json``；
- 首次启动用 ``DEFAULTS`` 生成，用户只通过设置页修改；
- 其余模块只读，不写；保存前做校验，无效值回退默认。
"""
from __future__ import annotations

import json
import os
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

# 默认配置模板。storage 三项留空，在实例化时按平台 AppData 解析。
DEFAULTS: dict[str, Any] = {
    "ollama": {"base_url": "http://127.0.0.1:11434", "timeout_s": 3, "generate_timeout_s": 600},
    "models": {
        "vision": "qwen2.5vl:7b",
        "llm": "qwen2.5:7b",
        "asr": "small",
    },
    "local_paths": {
        "roots": [],
    },
    "jellyfin": {
        "enabled": False,
        "base_url": "http://192.168.1.10:8096",
        "api_key": "",
    },
    "analysis": {
        "frame_interval_s": 60,
        "frames_per_scene": 2,
        "scene_threshold": 27.0,
        "max_frames": 200,
        "max_scene_chars": 16000,
    },
    "output": {
        "txt_name": "简介{filename}.txt",  # "简介" 二字固定，{filename} 写时替换
        "txt_mode": "new",                # "append" | "new"
        "txt_encoding": "utf-8-sig",
        "local_mode": "nfo_first",        # 本地源回写方式："nfo_first"=优先NFO(无则txt) | "txt_only"=仅txt
        "debug_text": False,              # 参考文本测试：分析时在软件目录输出实时文本
    },
    "storage": {
        "data_dir": "",
        "frame_cache_dir": "",
        "db_path": "",
    },
    "runtime": {"workers": 1},
}


def _base_dir() -> Path:
    """数据根目录：打包后为 exe 所在目录；源码运行时为项目根目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def _data_dir() -> Path:
    return _base_dir() / "data"


def _default_storage() -> dict[str, str]:
    d = _data_dir()
    return {
        "data_dir": str(d),
        "frame_cache_dir": str(d / "frames"),
        "db_path": str(d / "nasva.db"),
        "asr_models_dir": str(d / "asr_models"),
    }


def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并：override 覆盖 base，缺失键保留默认值。"""
    out = deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class Config:
    """配置对象。支持 ``cfg.ollama`` / ``cfg.output["local_mode"]`` 形式的访问与修改。"""

    def __init__(self, data: dict[str, Any] | None = None):
        merged = _deep_merge(DEFAULTS, data or {})

        # storage 始终按 exe/项目根目录计算（便携模式），忽略配置文件里的旧绝对路径
        merged["storage"] = _default_storage()

        self._data = merged
        self.path: Path = self.default_path()
        self._validate()

    # ---- 加载 / 保存 ----
    @classmethod
    def default_path(cls) -> Path:
        return _data_dir() / "config.json"

    @classmethod
    def load(cls, path: str | Path | None = None) -> "Config":
        p = Path(path) if path else cls.default_path()
        raw: dict = {}
        if p.exists():
            try:
                loaded = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    raw = loaded
            except (json.JSONDecodeError, OSError):
                raw = {}
        cfg = cls(raw)
        cfg.path = p
        return cfg

    def save(self, path: str | Path | None = None) -> None:
        p = Path(path) if path else self.path
        p.parent.mkdir(parents=True, exist_ok=True)
        data = self.as_dict()
        data.pop("storage", None)  # storage 运行时自动计算，不持久化
        p.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.path = p

    # ---- 访问 ----
    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        data = self.__dict__.get("_data")
        if data is not None and name in data:
            return data[name]
        raise AttributeError(name)

    def get(self, section: str, key: str | None = None, default: Any = None) -> Any:
        sec = self._data.get(section)
        if key is None:
            return deepcopy(sec) if sec is not None else default
        if isinstance(sec, dict):
            return sec.get(key, default)
        return default

    def as_dict(self) -> dict[str, Any]:
        return deepcopy(self._data)

    def storage_path(self, key: str) -> Path:
        return Path(os.path.expandvars(self._data["storage"][key]))

    @property
    def db_path(self) -> Path:
        return self.storage_path("db_path")

    def asr_model_path(self, model_name: str) -> Path:
        """ASR 模型本地目录（data/asr_models/<模型名>）。"""
        return self.storage_path("asr_models_dir") / model_name

    # ---- 校验（无效值回退默认，不抛异常） ----
    def _validate(self) -> None:
        d = self._data

        out = d["output"]
        if out.get("txt_mode") not in ("append", "new"):
            out["txt_mode"] = DEFAULTS["output"]["txt_mode"]
        if out.get("txt_encoding") not in ("utf-8-sig", "utf-8"):
            out["txt_encoding"] = DEFAULTS["output"]["txt_encoding"]
        if not isinstance(out.get("txt_name"), str) or not out["txt_name"]:
            out["txt_name"] = DEFAULTS["output"]["txt_name"]
        if out.get("local_mode") not in ("nfo_first", "txt_only"):
            out["local_mode"] = DEFAULTS["output"]["local_mode"]

        # 正数校验
        for sec, key in [
            ("analysis", "frame_interval_s"),
            ("analysis", "frames_per_scene"),
            ("analysis", "scene_threshold"),
            ("analysis", "max_frames"),
            ("analysis", "max_scene_chars"),
            ("runtime", "workers"),
            ("ollama", "timeout_s"),
            ("ollama", "generate_timeout_s"),
        ]:
            try:
                v = d[sec][key]
                if not (isinstance(v, (int, float)) and v > 0):
                    raise ValueError
                if key in ("frames_per_scene", "workers", "max_frames", "max_scene_chars") and isinstance(v, float):
                    d[sec][key] = int(v)
            except (KeyError, ValueError, TypeError):
                d[sec][key] = DEFAULTS[sec][key]

        # URL 校验
        for sec, key in [("ollama", "base_url"), ("jellyfin", "base_url")]:
            v = d[sec].get(key, "")
            if not isinstance(v, str) or not v.startswith(("http://", "https://")):
                d[sec][key] = DEFAULTS[sec][key]

        # 列表校验
        if not isinstance(d["local_paths"].get("roots"), list):
            d["local_paths"]["roots"] = []
