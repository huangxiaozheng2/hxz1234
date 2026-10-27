"""出图后端。

placeholder  不用显卡：画一张“分镜卡”，用来先看节奏、对台词、试配音（动态分镜）。
comfyui      本地开源模型（SDXL / FLUX / Qwen-Image / Kolors……），用你自己导出的工作流。
openai       任何兼容 OpenAI /images/generations 的服务。
dashscope    阿里云百炼 · 通义万相（不需要显卡，按张计费）。
"""
from __future__ import annotations

import base64
import os
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .. import http
from ..util import ManjuError, find_cjk_font, seed_from, wrap_cjk
from .comfyui import IMAGE_EXT, ComfyUI, load_workflow, placeholders_in, fill_template

# 场景时间 → 草稿底色
PALETTES = {
    "night": ((24, 32, 64), (60, 46, 92)),
    "dusk": ((122, 64, 60), (214, 140, 90)),
    "dawn": ((96, 120, 160), (230, 190, 160)),
    "day": ((120, 170, 200), (236, 224, 196)),
}
CHAR_COLORS = [(214, 94, 82), (82, 150, 214), (232, 176, 74), (110, 180, 120), (170, 110, 200), (90, 190, 190)]


class PlaceholderImage:
    name = "placeholder"
    version = 3   # 草稿版式改动时加 1，旧草稿会自动重画

    def __init__(self, project, cfg: dict):
        self.font_path = find_cjk_font(project.config["subtitle"].get("font"))

    def _font(self, size: int):
        if self.font_path:
            return ImageFont.truetype(self.font_path, size)
        return ImageFont.load_default()

    def generate(self, prompt: str, negative: str, size: tuple[int, int], seed: int, out: Path,
                 refs: list[Path] | None = None, meta: dict | None = None) -> None:
        meta = meta or {}
        w, h = size
        top, bottom = PALETTES.get(meta.get("time", ""), ((70, 60, 80), (150, 120, 120)))
        img = Image.new("RGB", (w, h))
        d = ImageDraw.Draw(img)
        for y in range(h):
            t = y / max(1, h - 1)
            d.line([(0, y), (w, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))

        u = w / 100  # 以宽度的 1% 为单位排版
        # 三分构图辅助线
        for i in (1, 2):
            d.line([(w * i / 3, 0), (w * i / 3, h)], fill=(180, 180, 190), width=1)
            d.line([(0, h * i / 3), (w, h * i / 3)], fill=(180, 180, 190), width=1)

        if meta.get("kind") == "portrait":
            self._portrait(d, w, h, u, meta)
        else:
            self._shot(d, w, h, u, meta, prompt)
        out.parent.mkdir(parents=True, exist_ok=True)
        img.save(out)

    def _silhouette(self, d, cx, cy, r, color, label, font):
        d.ellipse([cx - r, cy - r * 2.2, cx + r, cy - r * 0.2], fill=color)
        d.rounded_rectangle([cx - r * 1.6, cy, cx + r * 1.6, cy + r * 3], radius=int(r), fill=color)
        tw = d.textlength(label, font=font)
        d.text((cx - tw / 2, cy + r * 3.3), label, font=font, fill=(255, 255, 255))

    def _shot(self, d, w, h, u, meta, prompt):
        # 版式避开两块区域：运镜时会被裁掉的四边（约 13%），以及底部的字幕区
        f_big, f_mid, f_small = self._font(int(u * 5.6)), self._font(int(u * 4.2)), self._font(int(u * 3.2))
        top = h * 0.14
        d.rounded_rectangle([u * 14, top, u * 86, top + u * 13], radius=int(u * 2), fill=(0, 0, 0))
        d.text((u * 17, top + u * 1.8), meta.get("shot_id", ""), font=f_mid, fill=(255, 214, 120))
        tag = f"{meta.get('shot_type', '')} · {meta.get('camera_cn', '')}"
        d.text((u * 17, top + u * 7.5), tag, font=f_small, fill=(230, 230, 230))
        y = top + u * 18
        for ln in wrap_cjk(meta.get("description") or prompt, 12)[:3]:
            tw = d.textlength(ln, font=f_big)
            d.text(((w - tw) / 2, y), ln, font=f_big, fill=(255, 255, 255), stroke_width=int(u * 0.45), stroke_fill=(0, 0, 0))
            y += u * 7.5
        chars = meta.get("characters") or []
        n = len(chars)
        for i, (name, color) in enumerate(chars):
            cx = w * (i + 1) / (n + 1)
            self._silhouette(d, cx, h * 0.52, u * (8 if n <= 2 else 5.5), color, name, f_mid)
        foot = "分镜草稿 · 接入 ComfyUI 后替换为 AI 画面"
        d.text(((w - d.textlength(foot, font=f_small)) / 2, h * 0.075), foot, font=f_small, fill=(225, 225, 225))

    def _portrait(self, d, w, h, u, meta):
        f_big, f_small = self._font(int(u * 9)), self._font(int(u * 3.6))
        self._silhouette(d, w / 2, h * 0.42, u * 14, meta.get("color", CHAR_COLORS[0]), "", f_small)
        name = meta.get("name", "")
        tw = d.textlength(name, font=f_big)
        d.text(((w - tw) / 2, h * 0.72), name, font=f_big, fill=(255, 255, 255))
        y = h * 0.8
        for ln in wrap_cjk(meta.get("appearance", ""), 44)[:6]:
            tw = d.textlength(ln, font=f_small)
            d.text(((w - tw) / 2, y), ln, font=f_small, fill=(235, 235, 235))
            y += u * 5


class ComfyUIImage:
    name = "comfyui"

    def __init__(self, project, cfg: dict):
        c = cfg.get("comfyui") or {}
        if not c.get("workflow"):
            raise ManjuError("image.comfyui.workflow 没有填。可以先用 workflows/sdxl_t2i.json。")
        self.workflow = load_workflow(project.path(c["workflow"]))
        self.params = c.get("params") or {}
        self.client = ComfyUI(c.get("url", "http://127.0.0.1:8188"), float(c.get("timeout", 600)))
        self.needs_ref = "ref_image" in placeholders_in(self.workflow)

    def generate(self, prompt, negative, size, seed, out: Path, refs=None, meta=None) -> None:
        values = {"prompt": prompt, "negative": negative, "seed": seed, "width": size[0], "height": size[1], **self.params}
        if self.needs_ref:
            if not refs:
                raise ManjuError("工作流需要 {{ref_image}}（角色参考图），但这个镜头没有角色定妆照。先运行 characters 步骤。")
            values["ref_image"] = self.client.upload(refs[0])
        data = self.client.run(fill_template(self.workflow, values), IMAGE_EXT)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)


class OpenAIImage:
    name = "openai"

    def __init__(self, project, cfg: dict):
        c = cfg.get("openai") or {}
        self.base_url = (c.get("base_url") or "").rstrip("/")
        self.model = c.get("model") or ""
        self.size = c.get("size") or ""
        self.extra = c.get("extra") or {}
        env = c.get("api_key_env") or ""
        self.key = c.get("api_key") or (os.environ.get(env) if env else "") or ""
        if not self.base_url or not self.model:
            raise ManjuError("image.openai.base_url 和 model 需要填写。")

    def generate(self, prompt, negative, size, seed, out: Path, refs=None, meta=None) -> None:
        payload = {"model": self.model, "prompt": prompt, "n": 1,
                   "size": self.size or f"{size[0]}x{size[1]}", **self.extra}
        headers = {"Authorization": f"Bearer {self.key}"} if self.key else {}
        data = http.post_json(f"{self.base_url}/images/generations", payload, headers=headers, timeout=600)
        items = data.get("data") or data.get("images") or []
        if not items:
            raise ManjuError(f"出图接口没有返回图片：{str(data)[:300]}")
        item = items[0]
        if item.get("b64_json"):
            raw = base64.b64decode(item["b64_json"])
        elif item.get("url"):
            _, _, raw = http.request("GET", item["url"], timeout=300)
        else:
            raise ManjuError(f"出图接口返回格式不认识：{str(item)[:200]}")
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".download")
        tmp.write_bytes(raw)
        Image.open(tmp).convert("RGB").save(out)
        tmp.unlink()


class ContentRejected(ManjuError):
    """画面描述或生成结果没有通过平台的内容审核。"""


DASHSCOPE_ERRORS = {
    "InvalidApiKey": "阿里云百炼 API Key 无效，请检查 DASHSCOPE_API_KEY 是否填对",
    "Arrearage": "阿里云账户欠费或余额不足，请到阿里云控制台充值",
    "AccessDenied": "这个 Key 没有调用该模型的权限，请在百炼控制台确认已开通通义万相",
    "Model.AccessDenied": "这个 Key 没有调用该模型的权限，请在百炼控制台确认已开通通义万相",
    "ModelNotFound": "模型名不存在，请检查 image.dashscope.model",
}


class DashScopeImage:
    """阿里云百炼 · 通义万相文生图（异步任务：提交 → 轮询 → 下载）。"""
    name = "dashscope"

    def __init__(self, project, cfg: dict):
        c = cfg.get("dashscope") or {}
        self.base = (c.get("base_url") or "https://dashscope.aliyuncs.com").rstrip("/")
        self.model = c.get("model") or "wanx2.1-t2i-turbo"
        self.size = c.get("size") or ""
        self.parameters = c.get("parameters") or {}
        self.poll = float(c.get("poll_interval", 3))
        self.timeout = float(c.get("timeout", 300))
        env = c.get("api_key_env") or "DASHSCOPE_API_KEY"
        self.key = c.get("api_key") or os.environ.get(env, "")
        if not self.key:
            raise ManjuError(f"没有找到阿里云百炼 API Key：请设置环境变量 {env}。")

    def _explain(self, code: str, message: str) -> ManjuError:
        text = f"{code} {message}".strip()
        if "DataInspection" in code or "inappropriate" in message.lower() or "IPInfringement" in code:
            return ContentRejected(text)
        for k, hint in DASHSCOPE_ERRORS.items():
            if code == k or code.startswith(k + "."):
                return ManjuError(f"通义万相出图失败：{hint}（{text}）")
        low = message.lower()
        if "model" in low and ("not exist" in low or "not found" in low):
            return ManjuError(f"通义万相出图失败：模型 {self.model} 不存在或不可用，请检查 image.dashscope.model（{text}）")
        return ManjuError(f"通义万相出图失败：{text}")

    def generate(self, prompt, negative, size, seed, out: Path, refs=None, meta=None) -> None:
        auth = {"Authorization": f"Bearer {self.key}"}
        payload = {
            "model": self.model,
            "input": {"prompt": prompt[:800], "negative_prompt": (negative or "")[:500]},
            "parameters": {"size": self.size or f"{size[0]}*{size[1]}", "n": 1, "seed": int(seed) % 2147483647,
                           "prompt_extend": False, "watermark": False, **self.parameters},
        }
        try:
            resp = http.retry(lambda: http.post_json(
                f"{self.base}/api/v1/services/aigc/text2image/image-synthesis", payload,
                headers={**auth, "X-DashScope-Async": "enable"}, timeout=60), what="提交出图任务")
        except http.HTTPStatusError as e:
            body = e.json()
            raise self._explain(body.get("code", f"HTTP {e.status}"), body.get("message", e.body[:200])) from e
        task_id = (resp.get("output") or {}).get("task_id")
        if not task_id:
            raise ManjuError(f"通义万相没有返回任务号：{str(resp)[:300]}")

        deadline = time.time() + self.timeout
        while True:
            time.sleep(self.poll)
            r = http.retry(lambda: http.get_json(f"{self.base}/api/v1/tasks/{task_id}", headers=auth, timeout=30),
                           what="查询出图进度")
            o = r.get("output") or {}
            status = o.get("task_status")
            if status == "SUCCEEDED":
                results = o.get("results") or []
                urls = [x["url"] for x in results if isinstance(x, dict) and x.get("url")]
                if not urls:
                    bad = next((x for x in results if isinstance(x, dict) and x.get("code")), {})
                    raise self._explain(bad.get("code", "NoResult"), bad.get("message", "任务成功但没有返回图片"))
                break
            if status in ("FAILED", "CANCELED", "UNKNOWN"):
                raise self._explain(o.get("code", status), o.get("message", ""))
            if time.time() > deadline:
                raise ManjuError(f"通义万相出图超时（{self.timeout:.0f} 秒），任务号 {task_id}")

        _, _, raw = http.retry(lambda: http.request("GET", urls[0], timeout=120), what="下载图片")
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".download")
        tmp.write_bytes(raw)
        Image.open(tmp).convert("RGB").save(out)
        tmp.unlink()


def char_color(index: int) -> tuple[int, int, int]:
    return CHAR_COLORS[index % len(CHAR_COLORS)]


def shot_seed(project_seed_key: str, explicit: int | None) -> int:
    return explicit if explicit is not None else seed_from(project_seed_key)
