"""让分镜图动起来。

kenburns  用 ffmpeg 做推、拉、摇、移，CPU 就能跑，最稳定。
comfyui   图生视频（Wan2.x / HunyuanVideo / LTX-Video 等），用你自己导出的工作流，
          占位符：{{image}} {{prompt}} {{negative}} {{seed}} {{width}} {{height}} {{frames}} {{fps}} {{seconds}}
"""
from __future__ import annotations

from pathlib import Path

from .. import ffmpeg
from ..util import ManjuError
from .comfyui import VIDEO_EXT, ComfyUI, fill_template, load_workflow


class KenBurns:
    name = "kenburns"

    def __init__(self, project, cfg: dict):
        self.zoom = float(cfg.get("zoom", 0.15))
        self.crf = int(project.config["video"].get("crf", 20))

    def animate(self, image: Path, out: Path, seconds: float, size, fps: int, camera: str,
                prompt: str = "", negative: str = "", seed: int = 0) -> None:
        ffmpeg.kenburns(image, out, seconds, size, fps, camera, self.zoom, self.crf)


class ComfyUIMotion:
    name = "comfyui"

    def __init__(self, project, cfg: dict):
        c = cfg.get("comfyui") or {}
        if not c.get("workflow"):
            raise ManjuError("motion.comfyui.workflow 没有填，请导出你的图生视频工作流（API 格式）。")
        self.workflow = load_workflow(project.path(c["workflow"]))
        self.params = c.get("params") or {}
        self.client = ComfyUI(c.get("url", "http://127.0.0.1:8188"), float(c.get("timeout", 1800)))
        self.crf = int(project.config["video"].get("crf", 20))
        self.gen_fps = int(self.params.get("fps", 16))

    def animate(self, image: Path, out: Path, seconds: float, size, fps: int, camera: str,
                prompt: str = "", negative: str = "", seed: int = 0) -> None:
        # 多数图生视频模型一次只能生成几秒，帧数按“4n+1”取整（Wan 系列的要求），不够的部分定格补齐
        max_frames = int(self.params.get("max_frames", 81))
        frames = min(max_frames, int(seconds * self.gen_fps) // 4 * 4 + 1)
        values = {"image": self.client.upload(image), "prompt": prompt, "negative": negative, "seed": seed,
                  "width": size[0], "height": size[1], "frames": frames, "fps": self.gen_fps,
                  "seconds": round(seconds, 2), **self.params}
        raw = self.client.run(fill_template(self.workflow, values), VIDEO_EXT)
        tmp = out.with_name(out.stem + "_raw" + ".mp4")
        tmp.write_bytes(raw)
        ffmpeg.conform_clip(tmp, out, seconds, size, fps, self.crf)
