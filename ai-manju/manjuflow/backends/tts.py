"""配音后端。

silent  不发声，按语速估算时长，用来先排时间轴、出动态分镜。
edge    微软 Edge 在线语音（免费，需要 pip install edge-tts，需联网）。
openai  兼容 OpenAI /audio/speech 的服务（很多本地 TTS 都提供这个接口）。
http    通用 HTTP 接口模板，可对接 GPT-SoVITS、CosyVoice、IndexTTS 等自部署服务。

音色在 project.yaml 的 tts.voices 里配置，按以下顺序匹配：
角色的 voice 字段 → 角色 id → default_male / default_female（按性别）→ narrator。
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from .. import ffmpeg, http
from ..util import ManjuError
from .comfyui import fill_template


class SilentTTS:
    name = "silent"

    def __init__(self, project, cfg: dict):
        self.rate = float(cfg.get("speech_rate", 4.5))

    def synthesize(self, text: str, voice: dict, emotion: str, out: Path) -> None:
        chars = sum(1 for c in text if not c.isspace())
        ffmpeg.silence_wav(out, max(0.6, chars / self.rate + 0.2))


class EdgeTTS:
    name = "edge"

    def __init__(self, project, cfg: dict):
        try:
            import edge_tts  # noqa: F401
        except ImportError as e:
            raise ManjuError("使用 edge 配音需要先安装：pip install edge-tts") from e

    def synthesize(self, text: str, voice: dict, emotion: str, out: Path) -> None:
        import edge_tts
        name = voice.get("edge") or "zh-CN-XiaoxiaoNeural"
        comm = edge_tts.Communicate(text, name, rate=voice.get("rate", "+0%"), pitch=voice.get("pitch", "+0Hz"))
        try:
            asyncio.run(comm.save(str(out)))
        except Exception as e:  # edge-tts 的网络错误类型较多，统一提示
            raise ManjuError(f"Edge 配音失败（需要能访问微软语音服务）：{e}") from e


class OpenAITTS:
    name = "openai"

    def __init__(self, project, cfg: dict):
        c = cfg.get("openai") or {}
        self.base_url = (c.get("base_url") or "").rstrip("/")
        self.model = c.get("model") or "tts-1"
        env = c.get("api_key_env") or ""
        self.key = c.get("api_key") or (os.environ.get(env) if env else "") or ""
        if not self.base_url:
            raise ManjuError("tts.openai.base_url 需要填写。")

    def synthesize(self, text: str, voice: dict, emotion: str, out: Path) -> None:
        payload = {"model": voice.get("model", self.model), "input": text,
                   "voice": voice.get("openai") or voice.get("voice") or "alloy", "response_format": "wav"}
        if voice.get("speed"):
            payload["speed"] = voice["speed"]
        headers = {"Authorization": f"Bearer {self.key}"} if self.key else {}
        _, _, body = http.request("POST", f"{self.base_url}/audio/speech", json_body=payload, headers=headers, timeout=300)
        out.write_bytes(body)


class HTTPTTS:
    """通用模板：url / json / params / headers 里都可以用 {{text}} {{emotion}} 以及音色里的任意字段。"""
    name = "http"

    def __init__(self, project, cfg: dict):
        self.c = cfg.get("http") or {}
        if not self.c.get("url"):
            raise ManjuError("tts.http.url 需要填写，例如 GPT-SoVITS 的 http://127.0.0.1:9880/tts")

    def synthesize(self, text: str, voice: dict, emotion: str, out: Path) -> None:
        values = {"text": text, "emotion": emotion or "", **{k: v for k, v in voice.items()}}
        url = fill_template(self.c["url"], values)
        method = (self.c.get("method") or "POST").upper()
        body = fill_template(self.c.get("json") or {}, values) or None
        params = fill_template(self.c.get("params") or {}, values) or None
        headers = fill_template(self.c.get("headers") or {}, values)
        status, hdrs, data = http.request(method, url, json_body=body if method != "GET" else None,
                                          params=params, headers=headers, timeout=float(self.c.get("timeout", 300)))
        ctype = (hdrs.get("Content-Type") or hdrs.get("content-type") or "").lower()
        if "json" in ctype or "text" in ctype:
            raise ManjuError(f"配音接口没有返回音频，而是：{data[:300].decode('utf-8', 'replace')}")
        out.write_bytes(data)


def pick_voice(voices: dict, character, speaker: str) -> dict:
    if speaker == "narrator" or character is None:
        return voices.get("narrator") or voices.get("default_female") or {}
    for key in (character.voice, character.id):
        if key and key in voices:
            return voices[key]
    if character.gender.startswith("m") and "default_male" in voices:
        return voices["default_male"]
    return voices.get("default_female") or voices.get("narrator") or {}
