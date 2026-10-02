# -*- coding: utf-8 -*-
"""模型就绪检测（设置页“测试”按钮的后端）。

原则（见计划书 §3）：只判断“是否就绪”，不运行任何推理、不测模型质量/速度。
返回结构统一为 ``{"item": str, "ready": bool, "reason": str}``。
"""
from __future__ import annotations

from .config import Config
from .models.ollama_client import OllamaClient, OllamaError, model_name_matches
from .models.asr import is_model_ready


def _client(cfg: Config) -> OllamaClient:
    return OllamaClient(cfg.ollama["base_url"], cfg.ollama["timeout_s"])


def check_ollama_server(cfg: Config) -> dict:
    try:
        _client(cfg).server_version()
        return {"item": "模型服务", "ready": True, "reason": ""}
    except OllamaError as e:
        return {"item": "模型服务", "ready": False, "reason": f"模型服务不可用（{e}）"}


def check_ollama_model(cfg: Config, model_name: str, label: str) -> dict:
    try:
        names = _client(cfg).model_names()
    except OllamaError as e:
        return {"item": label, "ready": False, "reason": f"无法连接模型服务获取模型列表（{e}）"}
    if model_name_matches(model_name, names):
        return {"item": label, "ready": True, "reason": ""}
    return {"item": label, "ready": False, "reason": f"模型 {model_name} 未安装"}


def check_asr_model(cfg: Config) -> dict:
    name = cfg.models["asr"]
    if is_model_ready(cfg, name):
        return {"item": f"ASR 模型 {name}", "ready": True, "reason": ""}
    return {"item": f"ASR 模型 {name}", "ready": False,
            "reason": f"ASR 模型 {name} 未下载（请在“设置”页点击“下载模型”）"}


def check_all(cfg: Config) -> list[dict]:
    """逐项就绪检测，整体应在数秒内完成，且不执行任何推理。"""
    return [
        check_ollama_server(cfg),
        check_ollama_model(cfg, cfg.models["vision"], "视觉模型"),
        check_ollama_model(cfg, cfg.models["llm"], "文本模型"),
        check_asr_model(cfg),
    ]
