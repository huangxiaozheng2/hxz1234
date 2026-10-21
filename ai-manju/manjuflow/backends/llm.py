"""LLM 后端：任何兼容 OpenAI Chat Completions 接口的服务都可以用。

常见配置（base_url / model）：
    DeepSeek          https://api.deepseek.com/v1                         deepseek-chat
    通义千问           https://dashscope.aliyuncs.com/compatible-mode/v1   qwen-plus
    Ollama（本地）     http://127.0.0.1:11434/v1                          qwen2.5:14b 等
    vLLM / LM Studio  http://127.0.0.1:8000/v1                           你加载的模型名
"""
from __future__ import annotations

import json
import os
import re

from .. import http
from ..util import ManjuError


class OpenAICompatLLM:
    def __init__(self, cfg: dict):
        self.base_url = (cfg.get("base_url") or "").rstrip("/")
        self.model = cfg.get("model") or ""
        self.temperature = float(cfg.get("temperature", 0.8))
        self.json_mode = bool(cfg.get("json_mode", True))
        self.timeout = float(cfg.get("timeout", 300))
        env = cfg.get("api_key_env") or ""
        self.api_key = cfg.get("api_key") or (os.environ.get(env) if env else "") or ""
        if not self.base_url or not self.model:
            raise ManjuError("llm.base_url 和 llm.model 需要在 project.yaml 里填好。")
        if not self.api_key and not http.is_local(http.urlparse(self.base_url).hostname):
            raise ManjuError(f"没有找到 API Key：请设置环境变量 {env}（或在 llm.api_key 里填写）。")

    def chat(self, messages: list[dict], json_mode: bool | None = None) -> str:
        payload = {"model": self.model, "messages": messages, "temperature": self.temperature}
        if self.json_mode if json_mode is None else json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        data = http.post_json(f"{self.base_url}/chat/completions", payload, headers=headers, timeout=self.timeout)
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            raise ManjuError(f"LLM 返回格式不认识：{str(data)[:300]}") from e


def extract_json(text: str) -> dict:
    """从 LLM 输出里取出 JSON（兼容 ```json 代码块、前后多余文字、<think> 段落）。"""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S)
    if m:
        text = m.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ManjuError("LLM 没有返回 JSON 内容。")
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError as e:
        raise ManjuError(f"LLM 返回的 JSON 不合法：{e}") from e
