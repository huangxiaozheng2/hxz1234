"""命令行入口：manju init / run / status / doctor / styles"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__, http
from .pipeline import ORDER, run
from .project import STYLE_PRESETS, Project
from .schema import voice_items
from .util import ManjuError, eprint

# 项目模板。__TITLE__ / __STYLE__ / __SHOTS__ 会在创建时替换。
DRAFT_TEMPLATE = """# 漫剧项目配置（草稿模式：不需要显卡和 API Key）。完整选项见 README「配置说明」。
title: __TITLE__
style: __STYLE__            # 画风预设（manju styles 查看），也可以直接写英文提示词

video:
  resolution: [1080, 1920]   # 竖屏；横屏改成 [1920, 1080]
  fps: 24

llm:                         # 从 story.txt 自动写剧本；手写 script.yaml 可以不配
  backend: none              # 改成 openai 启用
  base_url: https://api.deepseek.com/v1
  model: deepseek-chat
  api_key_env: LLM_API_KEY   # 从这个环境变量读取 API Key
  target_shots: __SHOTS__

image:
  backend: placeholder       # placeholder（分镜草稿）/ comfyui / openai / dashscope
  size: [768, 1344]
  comfyui:
    url: http://127.0.0.1:8188
    workflow: workflows/sdxl_t2i.json
    params:
      ckpt: sd_xl_base_1.0.safetensors
      steps: 28
      cfg: 6.5

motion:
  backend: kenburns          # kenburns（推拉摇移）/ comfyui（图生视频）

tts:
  backend: silent            # silent（静音占位）/ edge / openai / http
  voices:
    narrator: {edge: zh-CN-YunyangNeural}
    female_pool: [{edge: zh-CN-XiaoxiaoNeural}, {edge: zh-CN-XiaoyiNeural}]
    male_pool: [{edge: zh-CN-YunxiNeural}, {edge: zh-CN-YunjianNeural}]

subtitle:
  enabled: true
  font: Noto Sans CJK SC

bgm:
  file: ""                   # 背景音乐，例如 assets/bgm.mp3
  volume: 0.18
"""

DASHSCOPE_TEMPLATE = """# 漫剧项目配置（阿里云百炼版）：剧本用通义千问，画面用通义万相，配音用免费的微软语音。
# 需要环境变量 DASHSCOPE_API_KEY（阿里云百炼控制台 → API-KEY）。完整选项见 README「配置说明」。
title: __TITLE__
style: __STYLE__            # 画风预设（manju styles 查看），也可以直接写英文提示词

video:
  resolution: [1080, 1920]
  fps: 24

llm:
  backend: openai
  base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
  model: qwen-plus
  api_key_env: DASHSCOPE_API_KEY
  target_shots: __SHOTS__

image:
  backend: dashscope
  size: [768, 1344]
  on_content_rejected: placeholder   # 某个镜头没通过内容审核时先用分镜卡代替，不中断整条片子
  dashscope:
    model: wanx2.1-t2i-turbo
    api_key_env: DASHSCOPE_API_KEY

motion:
  backend: kenburns

tts:
  backend: edge              # 需要 pip install edge-tts，并且能访问微软语音服务
  voices:
    narrator: {edge: zh-CN-YunyangNeural}
    female_pool: [{edge: zh-CN-XiaoxiaoNeural}, {edge: zh-CN-XiaoyiNeural}]
    male_pool: [{edge: zh-CN-YunxiNeural}, {edge: zh-CN-YunjianNeural}]

subtitle:
  enabled: true
  font: Noto Sans CJK SC

bgm:
  file: ""
  volume: 0.18
"""

PRESETS = {"draft": DRAFT_TEMPLATE, "dashscope": DASHSCOPE_TEMPLATE}


def cmd_init(a) -> int:
    root = Path(a.dir)
    if (root / "project.yaml").exists():
        raise ManjuError(f"{root} 已经是一个项目了")
    root.mkdir(parents=True, exist_ok=True)
    (root / "characters").mkdir(exist_ok=True)
    (root / "assets").mkdir(exist_ok=True)
    q = lambda v: json.dumps(v, ensure_ascii=False)   # 加引号，标题里有冒号等符号也不会弄坏 YAML
    text = (PRESETS[a.preset].replace("__TITLE__", q(a.title or root.name))
            .replace("__STYLE__", q(a.style)).replace("__SHOTS__", str(a.shots)))
    (root / "project.yaml").write_text(text, encoding="utf-8")
    wf_src = Path(__file__).resolve().parent.parent / "workflows"
    if wf_src.exists():
        shutil.copytree(wf_src, root / "workflows", dirs_exist_ok=True)
    if a.story:
        shutil.copy(a.story, root / "story.txt")
    elif not (root / "story.txt").exists():
        (root / "story.txt").write_text("把小说片段或故事梗概粘贴到这里。\n", encoding="utf-8")
    print(f"已创建项目 {root}\n下一步：\n"
          f"  1. 把故事写进 {root / 'story.txt'}，在 project.yaml 里配置 llm，运行 manju run {root} --only script\n"
          f"     （或者参考 examples/demo/script.yaml 手写剧本）\n"
          f"  2. 运行 manju run {root} 生成成片")
    return 0


def _stages(a) -> list[str] | None:
    if a.only:
        return [s.strip() for s in a.only.split(",") if s.strip()]
    if a.from_stage:
        if a.from_stage not in ORDER:
            raise ManjuError(f"没有 {a.from_stage} 这个步骤，可选：{', '.join(ORDER)}")
        return ORDER[ORDER.index(a.from_stage):]
    return None


def cmd_run(a) -> int:
    p = Project(a.dir)
    run(p, _stages(a), force=a.force)
    return 0


def cmd_status(a) -> int:
    p = Project(a.dir)
    print(f"项目：{p.root}")
    print(f"后端：LLM={p.config['llm']['backend']}  出图={p.config['image']['backend']}  "
          f"运镜={p.config['motion']['backend']}  配音={p.config['tts']['backend']}")
    if not p.has_script():
        print("剧本：还没有 script.yaml")
        return 0
    s = p.script()
    shots = s.all_shots()
    items = voice_items(s)
    def count(d, names): return sum((p.build / d / n).exists() for n in names)
    print(f"剧本：《{s.title}》 {len(s.characters)} 个角色 · {len(s.scenes)} 场 · {len(shots)} 个镜头 · {len(items)} 段配音")
    print(f"定妆照：{sum(p.character_reference(c.id) is not None for c in s.characters)}/{len(s.characters)}")
    print(f"分镜图：{count('images', [f'{x.id}.png' for x in shots])}/{len(shots)}")
    print(f"配音：  {count('audio', [f'{x.key}.wav' for x in items])}/{len(items)}")
    print(f"片段：  {count('clips', [f'{x.id}.mp4' for x in shots])}/{len(shots)}")
    outs = sorted(p.output.glob("*.mp4")) if p.output.exists() else []
    print("成片：  " + (", ".join(str(o) for o in outs) if outs else "还没有"))
    return 0


def cmd_doctor(a) -> int:
    ok = True

    def check(name, good, hint=""):
        nonlocal ok
        ok &= bool(good)
        print(f"  {'✓' if good else '✗'} {name}" + ("" if good else f"  —— {hint}"))

    print(f"ManjuFlow {__version__} · Python {sys.version.split()[0]}")
    ff = shutil.which("ffmpeg")
    check("ffmpeg", ff, "请安装 ffmpeg 并加入 PATH")
    if ff:
        filters = subprocess.run([ff, "-hide_banner", "-filters"], capture_output=True, text=True).stdout
        check("ffmpeg 支持字幕（libass）", " ass " in filters, "需要带 libass 的 ffmpeg 版本")
        check("ffmpeg 支持 zoompan / sidechaincompress", " zoompan " in filters and " sidechaincompress " in filters, "ffmpeg 版本太旧")
    check("ffprobe", shutil.which("ffprobe"), "通常随 ffmpeg 一起安装")
    if a.dir:
        p = Project(a.dir)
        print(f"项目 {p.root}")
        for kind in ("image", "motion"):
            c = p.config[kind]
            if c.get("backend") == "comfyui":
                url = c["comfyui"].get("url", "")
                try:
                    http.get_json(url.rstrip("/") + "/system_stats", timeout=5)
                    check(f"{kind}: ComfyUI {url}", True)
                except ManjuError as e:
                    check(f"{kind}: ComfyUI {url}", False, str(e))
                wf = c["comfyui"].get("workflow")
                check(f"{kind}: 工作流 {wf}", wf and p.path(wf).exists(), "文件不存在")
        if p.config["tts"]["backend"] == "edge":
            try:
                import edge_tts  # noqa: F401
                check("tts: edge-tts", True)
            except ImportError:
                check("tts: edge-tts", False, "pip install edge-tts")
        if p.has_script():
            try:
                p.script()
                check("script.yaml 格式", True)
            except ManjuError as e:
                check("script.yaml 格式", False, str(e))
    return 0 if ok else 1


def cmd_styles(a) -> int:
    for k, v in STYLE_PRESETS.items():
        print(f"{k:　<6} {v}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="manju", description="ManjuFlow 漫剧工坊：从故事到成片的开源 AI 漫剧工作流")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="创建新项目")
    s.add_argument("dir")
    s.add_argument("--title", default="")
    s.add_argument("--style", default="国漫厚涂")
    s.add_argument("--story", help="故事文本文件，会复制为 story.txt")
    s.add_argument("--preset", choices=sorted(PRESETS), default="draft",
                   help="配置模板：draft 草稿模式（默认，不需要显卡和 Key）/ dashscope 阿里云百炼")
    s.add_argument("--shots", type=int, default=12, help="让 LLM 写多少个镜头（默认 12）")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("run", help="运行工作流（默认全部步骤，已完成且没变化的会跳过）")
    s.add_argument("dir")
    s.add_argument("--only", help=f"只运行这些步骤，逗号分隔：{','.join(ORDER)}")
    s.add_argument("--from", dest="from_stage", help="从某一步开始往后运行")
    s.add_argument("--force", action="store_true", help="忽略缓存，强制重做")
    s.set_defaults(func=cmd_run)

    s = sub.add_parser("status", help="查看项目进度")
    s.add_argument("dir")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("doctor", help="检查环境和后端连通性")
    s.add_argument("dir", nargs="?")
    s.set_defaults(func=cmd_doctor)

    s = sub.add_parser("styles", help="列出内置画风预设")
    s.set_defaults(func=cmd_styles)

    a = ap.parse_args(argv)
    try:
        return a.func(a)
    except ManjuError as e:
        eprint(f"✗ {e}")
        return 2
    except KeyboardInterrupt:
        eprint("已中断。再次运行会从中断的地方继续。")
        return 130
