"""项目目录、配置与缓存。

一个漫剧项目就是一个文件夹：
    project.yaml   配置（用哪些模型、画幅、字幕样式……）
    story.txt      原始故事（可选，用来让 LLM 写剧本）
    script.yaml    剧本（LLM 生成或手写，可随时修改）
    characters/    角色定妆照
    build/         中间产物（分镜图、配音、片段、字幕……）
    output/        成片
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import yaml

from .schema import Script, parse_script, script_to_dict
from .util import ManjuError, file_digest

STYLE_PRESETS = {
    "国漫厚涂": "Chinese donghua style, thick paint illustration, cinematic lighting, rich details, dramatic composition",
    "日漫赛璐璐": "anime style, cel shading, clean lineart, vibrant colors, detailed background",
    "韩漫条漫": "Korean webtoon style, soft shading, clean lineart, delicate colors, beautiful lighting",
    "水墨国风": "Chinese ink wash painting style, elegant brush strokes, muted colors, misty atmosphere",
    "3D国创": "3D Chinese animation style, stylized characters, soft global illumination, cinematic",
    "美漫": "American comic book style, bold ink lines, halftone shading, dynamic composition",
}

DEFAULT_NEGATIVE = ("lowres, blurry, bad anatomy, bad hands, extra fingers, deformed face, "
                    "text, watermark, signature, logo, jpeg artifacts")

DEFAULT_CONFIG: dict = {
    "title": "",
    "style": "国漫厚涂",
    "negative_prompt": DEFAULT_NEGATIVE,
    "video": {
        "resolution": [1080, 1920],     # 竖屏 9:16；横屏改成 [1920, 1080]
        "fps": 24,
        "min_shot_seconds": 2.5,        # 没有台词的镜头至少停留多久
        "head_pad": 0.35,               # 镜头开始后多久开始说话
        "tail_pad": 0.6,                # 最后一句说完后再停留多久
        "line_gap": 0.25,               # 两句台词之间的间隔
        "crf": 20,
    },
    "llm": {
        "backend": "none",              # openai（任意兼容 OpenAI 接口的服务）/ none（手写剧本）
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "api_key_env": "LLM_API_KEY",
        "temperature": 0.8,
        "json_mode": True,
        "target_shots": 12,
    },
    "image": {
        "backend": "placeholder",       # placeholder（分镜草稿）/ comfyui / openai / dashscope
        "size": [768, 1344],
        "on_content_rejected": "stop",  # 某个镜头没通过内容审核时：stop 停下 / placeholder 先用分镜卡代替
        "comfyui": {"url": "http://127.0.0.1:8188", "workflow": "", "params": {}, "timeout": 600},
        "openai": {"base_url": "", "model": "", "api_key_env": "IMAGE_API_KEY", "size": "768x1344", "extra": {}},
        "dashscope": {"base_url": "https://dashscope.aliyuncs.com", "model": "wanx2.1-t2i-turbo",
                      "api_key_env": "DASHSCOPE_API_KEY", "parameters": {}},
    },
    "motion": {
        "backend": "kenburns",          # kenburns（推拉摇移）/ comfyui（图生视频）
        "zoom": 0.15,                   # 推拉幅度
        "comfyui": {"url": "http://127.0.0.1:8188", "workflow": "", "params": {}, "timeout": 1800},
    },
    "tts": {
        "backend": "silent",            # silent（静音占位）/ edge / openai / http
        "speech_rate": 4.5,             # silent 模式估算语速：每秒几个字
        "voices": {
            "narrator": {"edge": "zh-CN-YunyangNeural", "openai": "alloy"},
            "default_female": {"edge": "zh-CN-XiaoxiaoNeural", "openai": "nova"},
            "default_male": {"edge": "zh-CN-YunxiNeural", "openai": "echo"},
        },
        "openai": {"base_url": "", "model": "tts-1", "api_key_env": "TTS_API_KEY"},
        "http": {"url": "", "method": "POST", "json": {}, "params": {}, "headers": {}, "timeout": 300},
    },
    "subtitle": {
        "enabled": True,
        "font": "Noto Sans CJK SC",
        "fonts_dir": "",
        "size": 0.042,                  # 字号占画面高度的比例
        "max_chars": 14,                # 每行最多几个汉字
        "bottom": 0.16,                 # 距底部的比例
        "show_speaker": False,
    },
    "bgm": {"file": "", "volume": 0.18, "ducking": True},
}


def deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_yaml(path: Path) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ManjuError(f"{path.name} 不是合法的 YAML：{e}") from e


class Cache:
    """记录每个产物是用什么输入生成的。输入没变就跳过，改了哪个镜头只重做哪个镜头。"""

    def __init__(self, path: Path):
        self.path = path
        self.data: dict = {}
        if path.exists():
            try:
                self.data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self.data = {}

    def fresh(self, out: Path, fingerprint: str) -> bool:
        return out.exists() and self.data.get(str(out)) == fingerprint

    def mark(self, out: Path, fingerprint: str) -> None:
        self.data[str(out)] = fingerprint
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")


class Project:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        cfg_path = self.root / "project.yaml"
        if not cfg_path.exists():
            raise ManjuError(f"{self.root} 里没有 project.yaml。先用 `manju init {root}` 创建项目。")
        self.config = deep_merge(DEFAULT_CONFIG, load_yaml(cfg_path))
        self.build = self.root / "build"
        self.output = self.root / "output"
        self.cache = Cache(self.build / ".cache.json")
        self._script: Script | None = None

    # ── 提醒（不影响出片、但需要用户知道的问题）────────────────────────────────
    @property
    def warnings_path(self) -> Path:
        return self.build / "warnings.json"

    def reset_warnings(self) -> None:
        self.warnings_path.unlink(missing_ok=True)

    def warn(self, stage: str, item: str, message: str) -> None:
        data = json.loads(self.warnings_path.read_text(encoding="utf-8")) if self.warnings_path.exists() else []
        data.append({"stage": stage, "item": item, "message": message})
        self.build.mkdir(parents=True, exist_ok=True)
        self.warnings_path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    # ── 路径 ──────────────────────────────────────────────────────────────────
    def path(self, rel: str | Path) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else self.root / p

    def dir(self, *parts: str) -> Path:
        d = self.build.joinpath(*parts)
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def script_path(self) -> Path:
        return self.root / "script.yaml"

    @property
    def story_path(self) -> Path:
        return self.root / "story.txt"

    # ── 剧本 ──────────────────────────────────────────────────────────────────
    def has_script(self) -> bool:
        return self.script_path.exists()

    def script(self) -> Script:
        if self._script is None:
            if not self.has_script():
                raise ManjuError("还没有 script.yaml。可以手写一个，或者配置好 llm 后运行 script 步骤从 story.txt 生成。")
            self._script = parse_script(load_yaml(self.script_path))
        return self._script

    def save_script(self, script: Script) -> None:
        text = yaml.safe_dump(script_to_dict(script), allow_unicode=True, sort_keys=False, width=1000)
        self.script_path.write_text(
            "# 剧本：可以直接修改，改完重新运行 `manju run`，只会重做受影响的镜头。\n" + text, encoding="utf-8")
        self._script = script

    # ── 风格与尺寸 ────────────────────────────────────────────────────────────
    @property
    def style_prompt(self) -> str:
        name = (self._script.style if self._script and self._script.style else "") or self.config.get("style", "")
        return STYLE_PRESETS.get(name, name)

    @property
    def resolution(self) -> tuple[int, int]:
        w, h = self.config["video"]["resolution"]
        return int(w), int(h)

    @property
    def title(self) -> str:
        if self.has_script():
            return self.script().title
        return self.config.get("title") or self.root.name

    def character_reference(self, cid: str) -> Path | None:
        """角色定妆照：剧本里指定的优先，其次是 characters/<id>.png。"""
        c = self.script().character(cid)
        if c and c.reference and self.path(c.reference).exists():
            return self.path(c.reference)
        p = self.root / "characters" / f"{cid}.png"
        return p if p.exists() else None

    def digest(self, path: Path | None) -> str:
        return file_digest(path) if path and path.exists() else ""
