"""GitHub Actions 用：根据「Run workflow」里填的内容，准备一个漫剧项目目录。

环境变量：
    STORY        直接粘贴的故事
    STORY_FILE   仓库里的故事文件路径（优先于 STORY）
    STYLE        画风
    SHOTS        镜头数
    DRAFT        "true" 时只出分镜卡，不调用通义万相
    HEAD_MSG     推送触发时的提交说明：[manju-draft] 草稿；[manju-llm] 用示例故事走一遍 AI 改编
    DASHSCOPE_API_KEY  只检查有没有，不会打印
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANJU = HERE.parent                       # ai-manju/
REPO = Path(os.environ.get("GITHUB_WORKSPACE") or MANJU.parent)
sys.path.insert(0, str(MANJU))

from manjuflow.cli import main as manju          # noqa: E402
from manjuflow.project import STYLE_PRESETS      # noqa: E402

DEMO = MANJU / "examples" / "demo"


def fail(msg: str) -> None:
    print(f"::error::{msg}")
    sys.exit(1)


def main() -> None:
    work = Path(sys.argv[1] if len(sys.argv) > 1 else "work")
    head = os.environ.get("HEAD_MSG", "")
    draft = os.environ.get("DRAFT", "").lower() == "true" or "[manju-draft]" in head
    style = (os.environ.get("STYLE") or "").strip() or "国漫厚涂"
    has_key = bool(os.environ.get("DASHSCOPE_API_KEY", "").strip())

    try:
        shots = int((os.environ.get("SHOTS") or "10").strip())
    except ValueError:
        fail("镜头数量要填数字，例如 10。")
    if not 3 <= shots <= 30:
        fail("镜头数量请填 3 到 30 之间的数字。")

    story, source = "", "demo"
    story_file = (os.environ.get("STORY_FILE") or "").strip()
    if story_file:
        path = (REPO / story_file).resolve()
        if REPO.resolve() not in path.parents or not path.is_file():
            fail(f"找不到故事文件 {story_file}。请填仓库里的相对路径，例如 ai-manju/stories/我的故事.txt")
        story, source = path.read_text(encoding="utf-8").strip(), f"文件 {story_file}"
    elif (os.environ.get("STORY") or "").strip():
        story, source = os.environ["STORY"].strip(), "粘贴的故事"
    elif "[manju-llm]" in head:
        story, source = (DEMO / "story.txt").read_text(encoding="utf-8").strip(), "示例故事（AI 改编）"
    if story and len(story) < 30:
        fail("故事太短了，至少写几句话（30 字以上），AI 才能改编成分镜。")

    if (story or not draft) and not has_key:
        fail("没有找到 DASHSCOPE_API_KEY。请在仓库的 Settings → Secrets and variables → Actions 里添加，"
             "名字填 DASHSCOPE_API_KEY，值填阿里云百炼的 API Key。只想先看效果可以勾选「草稿模式」并且不填故事。")

    title = "末班车" if not story else "AI漫剧"
    code = manju(["init", str(work), "--preset", "dashscope", "--title", title, "--style", style, "--shots", str(shots)])
    if code:
        fail("创建项目失败")

    cfg = work / "project.yaml"
    text = cfg.read_text(encoding="utf-8")
    if draft:
        text = text.replace("  backend: dashscope", "  backend: placeholder", 1)
    cfg.write_text(text, encoding="utf-8")

    if story:
        (work / "story.txt").write_text(story + "\n", encoding="utf-8")
    else:
        demo = (DEMO / "script.yaml").read_text(encoding="utf-8")
        demo = re.sub(r"^style:.*$", "style: " + json.dumps(style, ensure_ascii=False), demo, count=1, flags=re.M)
        (work / "script.yaml").write_text(demo, encoding="utf-8")
        (work / "story.txt").write_text((DEMO / "story.txt").read_text(encoding="utf-8"), encoding="utf-8")

    info = {"draft": draft, "source": "示例剧本《末班车》" if source == "demo" else source, "style": style,
            "style_known": style in STYLE_PRESETS, "shots": shots}
    (work / "ci.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    mode = "草稿模式（分镜卡，不调用通义万相）" if draft else "正式模式（通义万相出图）"
    print(f"::notice::{mode} · 画风 {style} · 剧本来源：{info['source']}" + (f" · 目标 {shots} 个镜头" if story else ""))


if __name__ == "__main__":
    main()
