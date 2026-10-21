"""后端注册表：project.yaml 里写名字，这里找到对应的类。"""
from __future__ import annotations

from ..util import ManjuError
from .image import ComfyUIImage, OpenAIImage, PlaceholderImage
from .motion import ComfyUIMotion, KenBurns
from .tts import EdgeTTS, HTTPTTS, OpenAITTS, SilentTTS

REGISTRY = {
    "image": {"placeholder": PlaceholderImage, "comfyui": ComfyUIImage, "openai": OpenAIImage},
    "motion": {"kenburns": KenBurns, "comfyui": ComfyUIMotion},
    "tts": {"silent": SilentTTS, "edge": EdgeTTS, "openai": OpenAITTS, "http": HTTPTTS},
}


def get_backend(kind: str, project):
    cfg = project.config.get(kind) or {}
    name = cfg.get("backend", "")
    cls = REGISTRY[kind].get(name)
    if not cls:
        raise ManjuError(f"{kind}.backend 不支持 {name!r}，可选：{', '.join(REGISTRY[kind])}")
    return cls(project, cfg)
