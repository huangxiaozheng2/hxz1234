"""通用小工具：哈希、文字换行、字体查找、日志。"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


class ManjuError(Exception):
    """工作流里可以直接展示给用户的错误。"""


def log(stage: str, msg: str) -> None:
    print(f"[{stage}] {msg}", flush=True)


def stable_hash(*parts) -> str:
    """对任意可 JSON 序列化的内容算一个稳定的短哈希，用于缓存判断。"""
    h = hashlib.sha256()
    for p in parts:
        if isinstance(p, Path):
            p = file_digest(p) if p.exists() else f"missing:{p}"
        h.update(json.dumps(p, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:16]


def file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def seed_from(text: str) -> int:
    """由字符串得到固定种子，同一个镜头每次重跑画面不变。"""
    return int(hashlib.md5(text.encode("utf-8")).hexdigest()[:8], 16)


def is_wide(ch: str) -> bool:
    return ord(ch) > 0x2E80


def text_width(s: str) -> float:
    """中文算 1，英文/数字算 0.5。"""
    return sum(1 if is_wide(c) else 0.5 for c in s)


NO_LINE_START = set("，。！？、；：）」』》”’…,.!?;:)")


def wrap_cjk(text: str, max_width: float) -> list[str]:
    """按显示宽度把中文断行，标点不放在行首。"""
    lines, cur = [], ""
    for ch in text:
        if text_width(cur + ch) > max_width and cur and ch not in NO_LINE_START:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


_FONT_CACHE: dict[str, str | None] = {}


def find_cjk_font(preferred: str | None = None) -> str | None:
    """找一个能显示中文的字体文件路径（给 Pillow 用）。"""
    key = preferred or ""
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    found = None
    if preferred and Path(preferred).exists():
        found = preferred
    if not found and shutil.which("fc-match"):
        for name in [preferred, "Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Zen Hei", "PingFang SC", "Microsoft YaHei"]:
            if not name:
                continue
            try:
                out = subprocess.run(["fc-match", "-f", "%{file}|%{lang}", f"{name}:lang=zh-cn"],
                                     capture_output=True, text=True, timeout=5).stdout
            except (OSError, subprocess.SubprocessError):
                break
            path, _, langs = out.partition("|")
            if path and "zh" in langs:
                found = path
                break
    if not found:
        candidates = [
            "C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf",
            "/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Medium.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        ]
        found = next((c for c in candidates if Path(c).exists()), None)
    _FONT_CACHE[key] = found
    return found


def need_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise ManjuError(f"没有找到 {name}，请先安装（https://ffmpeg.org/download.html）并加入 PATH。")
    return path


def eprint(*a) -> None:
    print(*a, file=sys.stderr, flush=True)
