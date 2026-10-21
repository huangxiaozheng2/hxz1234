"""ComfyUI 客户端。

用法：在 ComfyUI 里搭好工作流 → 设置里打开开发者模式 → “导出（API 格式）”，
把需要每个镜头变化的输入改成占位符，例如：
    "text": "{{prompt}}"      "seed": "{{seed}}"      "image": "{{image}}"
整段字符串只有一个占位符时会保留原类型（数字还是数字）。
"""
from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path

from .. import http
from ..util import ManjuError

PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")
VIDEO_EXT = (".mp4", ".webm", ".mov", ".gif", ".webp")


def fill_template(obj, values: dict):
    """递归替换 {{key}}。缺少的占位符会一次性报出来。"""
    missing: set[str] = set()

    def walk(o):
        if isinstance(o, dict):
            return {k: walk(v) for k, v in o.items()}
        if isinstance(o, list):
            return [walk(v) for v in o]
        if isinstance(o, str):
            whole = PLACEHOLDER.fullmatch(o.strip())
            if whole:
                key = whole.group(1)
                if key not in values:
                    missing.add(key)
                    return o
                return values[key]

            def sub(m):
                if m.group(1) not in values:
                    missing.add(m.group(1))
                    return m.group(0)
                return str(values[m.group(1)])
            return PLACEHOLDER.sub(sub, o)
        return o

    out = walk(obj)
    if missing:
        raise ManjuError("工作流里有这些占位符没有提供值：" + ", ".join(sorted(missing)) +
                         "。可以在 project.yaml 对应的 comfyui.params 里补上。")
    return out


def placeholders_in(obj) -> set[str]:
    return set(PLACEHOLDER.findall(json.dumps(obj, ensure_ascii=False)))


class ComfyUI:
    def __init__(self, url: str, timeout: float = 600):
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.client_id = uuid.uuid4().hex

    def ping(self) -> dict:
        return http.get_json(f"{self.url}/system_stats", timeout=10)

    def upload(self, path: Path) -> str:
        """上传图片到 ComfyUI 的 input 目录，返回 LoadImage 节点可以用的文件名。"""
        mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        body, ctype = http.multipart({"overwrite": "true", "type": "input"},
                                     {"image": (path.name, path.read_bytes(), mime)})
        _, _, resp = http.request("POST", f"{self.url}/upload/image", data=body,
                                  headers={"Content-Type": ctype}, timeout=120)
        info = json.loads(resp)
        sub = info.get("subfolder") or ""
        return f"{sub}/{info['name']}" if sub else info["name"]

    def queue(self, workflow: dict) -> str:
        try:
            resp = http.post_json(f"{self.url}/prompt", {"prompt": workflow, "client_id": self.client_id}, timeout=60)
        except ManjuError as e:
            raise ManjuError(f"ComfyUI 拒绝了这个工作流（通常是模型文件名不对或缺少节点）：{e}") from e
        if resp.get("node_errors"):
            raise ManjuError(f"ComfyUI 工作流校验失败：{json.dumps(resp['node_errors'], ensure_ascii=False)[:800]}")
        return resp["prompt_id"]

    def wait(self, prompt_id: str, poll: float = 1.0) -> dict:
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            hist = http.get_json(f"{self.url}/history/{prompt_id}", timeout=30)
            entry = hist.get(prompt_id)
            if entry:
                status = entry.get("status") or {}
                if status.get("status_str") == "error":
                    msgs = [m for m in status.get("messages", []) if m and m[0] == "execution_error"]
                    detail = msgs[0][1].get("exception_message", "") if msgs else ""
                    raise ManjuError(f"ComfyUI 运行出错：{detail or status}")
                if status.get("completed", True) and entry.get("outputs") is not None:
                    return entry["outputs"]
            time.sleep(poll)
        raise ManjuError(f"ComfyUI 等待超时（{self.timeout} 秒），可以在配置里调大 timeout。")

    def download(self, file_info: dict) -> bytes:
        params = {"filename": file_info["filename"], "subfolder": file_info.get("subfolder", ""),
                  "type": file_info.get("type", "output")}
        _, _, body = http.request("GET", f"{self.url}/view", params=params, timeout=300)
        return body

    @staticmethod
    def output_files(outputs: dict, exts: tuple[str, ...]) -> list[dict]:
        """从 history 的 outputs 里找出指定后缀的文件（兼容 SaveImage / SaveVideo / VHS_VideoCombine）。"""
        found = []
        for node_out in outputs.values():
            for key in ("images", "gifs", "videos", "video"):
                for f in node_out.get(key, []) or []:
                    if isinstance(f, dict) and f.get("filename", "").lower().endswith(exts) and f.get("type") != "temp":
                        found.append(f)
        return found

    def run(self, workflow: dict, exts: tuple[str, ...]) -> bytes:
        outputs = self.wait(self.queue(workflow))
        files = self.output_files(outputs, exts)
        if not files:
            raise ManjuError(f"ComfyUI 跑完了，但没有找到 {'/'.join(exts)} 输出。请确认工作流里有 Save 节点。")
        return self.download(files[-1])


def load_workflow(path: Path) -> dict:
    if not path.exists():
        raise ManjuError(f"找不到 ComfyUI 工作流文件：{path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "nodes" in data and "links" in data:
        raise ManjuError(f"{path.name} 是 ComfyUI 的“界面格式”。请在 ComfyUI 里用“导出（API）”重新导出。")
    return data
