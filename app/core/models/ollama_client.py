# -*- coding: utf-8 -*-
"""本地模型服务客户端：同时支持 Ollama 原生 API 与 OpenAI 兼容 API（llama.cpp/vLLM/LM Studio 等）。

自动探测接口类型：
- Ollama : GET /api/tags, POST /api/generate
- OpenAI : GET /v1/models, POST /v1/chat/completions（视觉走 image_url base64）
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class OllamaError(Exception):
    """模型服务连接 / 调用失败时抛出。"""


def model_name_matches(wanted: str, installed_names: list[str]) -> bool:
    """判断配置的模型名是否命中已安装模型列表。

    支持精确匹配（含 tag），或省略 tag 的前缀匹配。
    """
    w = (wanted or "").strip()
    if not w:
        return False
    for n in installed_names:
        n = (n or "").strip()
        if n == w or n.startswith(w + ":"):
            return True
    return False


class OllamaClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434", timeout_s: float = 3.0,
                 generate_timeout_s: float | None = None):
        self.base_url = (base_url or "").rstrip("/")
        self.timeout_s = timeout_s
        # 推理（生成）用更长超时；连接/模型列表等快速调用仍用 timeout_s
        self.generate_timeout_s = generate_timeout_s if generate_timeout_s is not None else max(timeout_s, 600.0)
        self._style: str | None = None  # 'ollama' | 'openai'

    # ---- HTTP 基础 ----
    def _get(self, path: str) -> dict[str, Any]:
        req = urllib.request.Request(self.base_url + path)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
                return json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise OllamaError(str(e)) from e

    def _post(self, path: str, payload: dict, timeout_s: float | None = None) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_s or self.timeout_s) as r:
                return json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise OllamaError(str(e)) from e

    # ---- 自动探测接口类型 ----
    def _detect_style(self) -> str:
        if self._style:
            return self._style
        last: Exception | None = None
        try:
            data = self._get("/api/tags")
            if isinstance(data, dict) and "models" in data:
                self._style = "ollama"
                return self._style
        except OllamaError as e:
            last = e
        try:
            data = self._get("/v1/models")
            if isinstance(data, dict) and "data" in data:
                self._style = "openai"
                return self._style
        except OllamaError as e:
            last = e
        raise OllamaError(
            "无法识别模型服务接口（既不是 Ollama 的 /api/tags，也不是 OpenAI 兼容的 /v1/models）。"
            f"最后错误：{last}"
        )

    @property
    def api_style(self) -> str:
        return self._detect_style()

    # ---- 就绪检测相关（快速，不推理） ----
    def server_version(self) -> str:
        if self._detect_style() == "ollama":
            return self._get("/api/version").get("version", "")
        return "openai-compatible"

    def list_models(self) -> list[dict]:
        if self._detect_style() == "ollama":
            return self._get("/api/tags").get("models", [])
        return self._get("/v1/models").get("data", [])

    def model_names(self) -> list[str]:
        if self._detect_style() == "ollama":
            return [m.get("name", "") for m in self._get("/api/tags").get("models", [])]
        return [m.get("id", "") for m in self._get("/v1/models").get("data", [])]

    def is_model_installed(self, name: str) -> bool:
        return model_name_matches(name, self.model_names())

    def unload(self, model: str) -> None:
        """卸载模型以释放显存/上下文缓存。仅 Ollama 支持；OpenAI 兼容接口忽略。"""
        if self._detect_style() != "ollama":
            return
        try:
            self._post("/api/generate", {
                "model": model, "prompt": "", "keep_alive": 0, "stream": False,
            }, timeout_s=max(self.timeout_s, 10.0))
        except OllamaError:
            pass

    # ---- 生成（推理，耗时） ----
    def generate(
        self,
        model: str,
        prompt: str,
        images: list[str] | None = None,   # 视觉模型的 base64 图片
        stream: bool = False,
        options: dict | None = None,
    ) -> dict[str, Any]:
        if self._detect_style() == "ollama":
            return self._generate_ollama(model, prompt, images, stream, options)
        return self._generate_openai(model, prompt, images)

    def _generate_ollama(self, model, prompt, images, stream, options) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": model, "prompt": prompt, "stream": stream}
        if images:
            payload["images"] = images
        if options:
            payload["options"] = options
        return self._post("/api/generate", payload, timeout_s=max(self.generate_timeout_s, 60.0))

    def _generate_openai(self, model, prompt, images) -> dict[str, Any]:
        content: list[dict] = []
        if images:
            for img in images:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img}"},
                })
        content.append({"type": "text", "text": prompt})
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "stream": False,
        }
        data = self._post("/v1/chat/completions", payload, timeout_s=max(self.generate_timeout_s, 120.0))
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            content = ""
        if not isinstance(content, str):
            content = str(content) if content else ""
        return {"response": content}
