"""GitHub Actions 用：在运行页面上写一份看得懂的摘要（成片信息、分镜表、下载方法）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:   # 前面的安装步骤失败时也要能写出摘要
    yaml = None

CAMERA_CN = {"static": "固定", "push_in": "推", "pull_out": "拉", "pan_left": "左摇",
             "pan_right": "右摇", "tilt_up": "上摇", "tilt_down": "下摇"}


def cell(text) -> str:
    return str(text or "").replace("|", "｜").replace("\n", " ").strip()


def load(path: Path, kind: str):
    if not path.exists() or (kind == "yaml" and yaml is None):
        return None
    try:
        text = path.read_text(encoding="utf-8")
        return json.loads(text) if kind == "json" else yaml.safe_load(text)
    except Exception:   # 文件写了一半等情况，摘要里少显示一点即可
        return None


def main() -> None:
    work = Path(sys.argv[1] if len(sys.argv) > 1 else "work")
    artifact = sys.argv[2] if len(sys.argv) > 2 else "manju"
    info = load(work / "ci.json", "json") or {}
    script = load(work / "script.yaml", "yaml") or {}
    timeline = load(work / "build" / "timeline.json", "json") or {}
    warnings = load(work / "build" / "warnings.json", "json") or []
    videos = sorted((work / "output").glob("*.mp4")) if (work / "output").exists() else []

    title = script.get("title") or "AI 漫剧"
    out = [f"## 《{cell(title)}》"]
    if script.get("logline"):
        out.append(f"> {cell(script['logline'])}")
    out.append("")
    if videos:
        out.append(f"**成片已生成**：时长 {timeline.get('total', 0):.1f} 秒，{len(timeline.get('shots', []))} 个镜头。")
        out.append(f"**下载**：滚动到本页最下方的 **Artifacts**，点 `{artifact}` 下载压缩包。解压后 `output` 文件夹里的 "
                   "mp4 就是成片；`build/storyboard.html` 是分镜表，`build/images` 是每个镜头的原图。")
    else:
        out.append("**这次没有生成成片。** 请点开上面「生成漫剧」步骤，查看日志里以 ✗ 开头的那一行。")
    out.append("")

    if info:
        n_images = len(list((work / "build" / "images").glob("*.png"))) if (work / "build" / "images").exists() else 0
        n_chars = len(list((work / "characters").glob("*.png"))) if (work / "characters").exists() else 0
        paid = 0 if info.get("draft") else max(0, n_images + n_chars - len(warnings))
        out += ["| 模式 | 画风 | 剧本来源 | 通义万相出图 |", "|---|---|---|---|",
                f"| {'草稿（分镜卡）' if info.get('draft') else '正式'} | {cell(info.get('style'))} | "
                f"{cell(info.get('source'))} | {paid} 张 |", ""]

    shots_by_id = {s["id"]: s for s in timeline.get("shots", [])}
    names = {c.get("id"): c.get("name") for c in script.get("characters") or []}
    rows = []
    for sc in script.get("scenes") or []:
        for sh in sc.get("shots") or []:
            t = shots_by_id.get(sh.get("id"), {})
            said = []
            if sh.get("narration"):
                said.append(f"旁白：{sh['narration']}")
            for ln in sh.get("lines") or []:
                said.append(f"{names.get(ln.get('speaker'), ln.get('speaker'))}：{ln.get('text')}")
            dur = f"{t['duration']:.1f}s" if "duration" in t else ""
            rows.append(f"| {len(rows) + 1} | {cell(sh.get('shot'))} · {CAMERA_CN.get(sh.get('camera'), cell(sh.get('camera')))} | "
                        f"{cell(sh.get('description') or sh.get('visual'))} | {cell('<br>'.join(said))} | {dur} |")
    if rows:
        out += ["### 分镜", "| # | 镜头 | 画面 | 旁白 / 台词 | 时长 |", "|---|---|---|---|---|", *rows, ""]

    if warnings:
        out.append("### 需要注意")
        out += [f"- {cell(w.get('item'))}：{cell(w.get('message'))}" for w in warnings]
        out.append("")
    if info.get("style") and not info.get("style_known"):
        out.append(f"> 画风「{cell(info['style'])}」不是内置预设，已直接当作提示词使用。")
    print("\n".join(out))


if __name__ == "__main__":
    main()
