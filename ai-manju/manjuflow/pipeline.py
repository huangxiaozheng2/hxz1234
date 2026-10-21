"""工作流的各个步骤。

script → characters → images → voice → timeline → clips → subtitles → storyboard → compose

每一步都会检查输入有没有变化，没变就跳过。改了某个镜头的画面描述，只会重画那一张图、
重做那一段片段；改了某句台词，只会重配那一句。
"""
from __future__ import annotations

import html
import json
import shutil
import time
from pathlib import Path

from . import ffmpeg
from .backends import get_backend
from .backends.image import char_color
from .backends.llm import OpenAICompatLLM, extract_json
from .backends.tts import pick_voice
from .project import Project
from .prompts import SCRIPT_FIX, SCRIPT_SYSTEM, SCRIPT_USER, build_image_prompt, build_portrait_prompt, describe
from .schema import NARRATOR, parse_script, voice_items
from .subtitles import build_ass, build_srt
from .timing import build_timeline
from .util import ManjuError, log, seed_from, stable_hash

CAMERA_CN = {"static": "固定", "push_in": "推", "pull_out": "拉", "pan_left": "左摇",
             "pan_right": "右摇", "tilt_up": "上摇", "tilt_down": "下摇"}


# ── 1. 剧本 ────────────────────────────────────────────────────────────────────
def stage_script(p: Project, force: bool = False) -> None:
    if p.has_script() and not force:
        log("script", f"已有 script.yaml：{describe(p.script())}（要重新生成请加 --force）")
        return
    cfg = p.config["llm"]
    if cfg.get("backend") != "openai":
        raise ManjuError("没有 script.yaml，且 llm.backend 不是 openai。请手写剧本，或在 project.yaml 里配置 LLM。")
    if not p.story_path.exists():
        raise ManjuError("没有找到 story.txt。把小说或故事梗概放进 story.txt 再运行。")
    story = p.story_path.read_text(encoding="utf-8").strip()
    n = int(cfg.get("target_shots", 12))
    llm = OpenAICompatLLM(cfg)
    messages = [{"role": "system", "content": SCRIPT_SYSTEM},
                {"role": "user", "content": SCRIPT_USER.format(story=story, target_shots=n, target_seconds=n * 4)}]
    last_err = None
    for attempt in range(3):
        log("script", f"请 {llm.model} 改编剧本…（第 {attempt + 1} 次）")
        reply = llm.chat(messages)
        try:
            data = extract_json(reply)
            data.setdefault("style", p.config.get("style", ""))
            script = parse_script(data)
            break
        except ManjuError as e:
            last_err = e
            messages += [{"role": "assistant", "content": reply}, {"role": "user", "content": SCRIPT_FIX.format(error=e)}]
    else:
        raise ManjuError(f"LLM 连续 3 次都没有给出合格的剧本：{last_err}")
    p.save_script(script)
    log("script", f"已写入 script.yaml：{describe(script)}。建议先看一遍再继续。")


# ── 2. 角色定妆照 ──────────────────────────────────────────────────────────────
def stage_characters(p: Project, force: bool = False) -> None:
    script = p.script()
    backend = get_backend("image", p)
    size = tuple(p.config["image"]["size"])
    for i, c in enumerate(script.characters):
        if c.reference:
            if not p.path(c.reference).exists():
                raise ManjuError(f"角色 {c.name} 的定妆照 {c.reference} 不存在")
            log("characters", f"{c.name}：使用指定的定妆照 {c.reference}")
            continue
        out = p.root / "characters" / f"{c.id}.png"
        prompt = build_portrait_prompt(p.style_prompt, c)
        seed = c.seed if c.seed is not None else seed_from("char:" + c.id)
        fp = stable_hash("portrait", backend.name, getattr(backend, "version", 1), prompt, seed, size, p.config["image"].get(backend.name))
        if not force and p.cache.fresh(out, fp):
            continue
        if out.exists() and not p.cache.data.get(str(out)) and not force:
            log("characters", f"{c.name}：characters/{c.id}.png 是你自己放的，保留不动")
            continue
        log("characters", f"生成定妆照：{c.name}")
        backend.generate(prompt, p.config["negative_prompt"], size, seed, out,
                         meta={"kind": "portrait", "name": c.name, "appearance": c.appearance, "color": char_color(i)})
        p.cache.mark(out, fp)
    log("characters", f"{len(script.characters)} 个角色就绪（定妆照在 characters/ 目录，可以替换成你满意的图）")


# ── 3. 分镜画面 ────────────────────────────────────────────────────────────────
def stage_images(p: Project, force: bool = False) -> None:
    script = p.script()
    backend = get_backend("image", p)
    size = tuple(p.config["image"]["size"])
    out_dir = p.dir("images")
    shots = script.all_shots()
    done = 0
    for k, shot in enumerate(shots, 1):
        chars = [c for c in (script.character(cid) for cid in shot.characters) if c]
        prompt = build_image_prompt(p.style_prompt, shot, chars)
        seed = shot.seed if shot.seed is not None else seed_from("shot:" + shot.id)
        refs = [r for r in (p.character_reference(c.id) for c in chars) if r]
        out = out_dir / f"{shot.id}.png"
        fp = stable_hash("image", backend.name, getattr(backend, "version", 1), prompt, p.config["negative_prompt"], seed, size,
                         p.config["image"].get(backend.name), [p.digest(r) for r in refs],
                         shot.description if backend.name == "placeholder" else "")
        if not force and p.cache.fresh(out, fp):
            continue
        log("images", f"[{k}/{len(shots)}] {shot.id} {shot.description or shot.visual}"[:80])
        meta = {"kind": "shot", "shot_id": shot.id, "shot_type": shot.shot, "camera_cn": CAMERA_CN.get(shot.camera, ""),
                "description": shot.description or shot.visual, "time": shot.scene.time if shot.scene else "",
                "characters": [(c.name, char_color(script.characters.index(c))) for c in chars]}
        backend.generate(prompt, p.config["negative_prompt"], size, seed, out, refs=refs, meta=meta)
        p.cache.mark(out, fp)
        (out_dir / f"{shot.id}.prompt.txt").write_text(prompt, encoding="utf-8")
        done += 1
    log("images", f"共 {len(shots)} 个镜头，本次生成 {done} 张")


# ── 4. 配音 ────────────────────────────────────────────────────────────────────
def stage_voice(p: Project, force: bool = False) -> None:
    script = p.script()
    backend = get_backend("tts", p)
    voices = p.config["tts"].get("voices") or {}
    out_dir = p.dir("audio")
    items = voice_items(script)
    done = 0
    for k, it in enumerate(items, 1):
        ch = script.character(it.speaker) if it.speaker != NARRATOR else None
        voice = pick_voice(voices, ch, it.speaker)
        out = out_dir / f"{it.key}.wav"
        fp = stable_hash("voice", backend.name, it.text, it.emotion, voice,
                         p.config["tts"].get(backend.name) if backend.name != "silent" else p.config["tts"]["speech_rate"])
        if not force and p.cache.fresh(out, fp):
            continue
        who = "旁白" if it.speaker == NARRATOR else (ch.name if ch else it.speaker)
        log("voice", f"[{k}/{len(items)}] {who}：{it.text}")
        raw = out_dir / f"{it.key}.raw"
        backend.synthesize(it.text, voice, it.emotion, raw)
        ffmpeg.to_wav(raw, out)
        raw.unlink(missing_ok=True)
        p.cache.mark(out, fp)
        done += 1
    log("voice", f"共 {len(items)} 段配音，本次生成 {done} 段")


# ── 5. 时间轴 + 整条音轨 ───────────────────────────────────────────────────────
def stage_timeline(p: Project, force: bool = False) -> dict:
    script = p.script()
    audio_dir = p.build / "audio"
    durations = {}
    segs = []
    for it in voice_items(script):
        f = audio_dir / f"{it.key}.wav"
        if not f.exists():
            raise ManjuError(f"缺少配音 {f.name}，请先运行 voice 步骤。")
        durations[it.key] = ffmpeg.wav_duration(f)
    tl = build_timeline(script, durations, p.config["video"])
    for shot in tl["shots"]:
        for it in shot["items"]:
            segs.append((it["start"], audio_dir / f"{it['key']}.wav"))
    ffmpeg.assemble_track(segs, tl["total"], p.build / "voice_track.wav")
    (p.build / "timeline.json").write_text(json.dumps(tl, ensure_ascii=False, indent=1), encoding="utf-8")
    log("timeline", f"总时长 {tl['total']:.1f} 秒，{len(tl['shots'])} 个镜头")
    return tl


def _timeline(p: Project) -> dict:
    f = p.build / "timeline.json"
    if not f.exists():
        return stage_timeline(p)
    return json.loads(f.read_text(encoding="utf-8"))


# ── 6. 镜头片段 ────────────────────────────────────────────────────────────────
def stage_clips(p: Project, force: bool = False) -> None:
    script = p.script()
    tl = {s["id"]: s for s in _timeline(p)["shots"]}
    backend = get_backend("motion", p)
    size, fps = p.resolution, int(p.config["video"]["fps"])
    out_dir = p.dir("clips")
    shots = script.all_shots()
    done = 0
    for k, shot in enumerate(shots, 1):
        img = p.build / "images" / f"{shot.id}.png"
        if not img.exists():
            raise ManjuError(f"缺少分镜图 {img.name}，请先运行 images 步骤。")
        secs = tl[shot.id]["duration"]
        out = out_dir / f"{shot.id}.mp4"
        chars = [c for c in (script.character(cid) for cid in shot.characters) if c]
        prompt = build_image_prompt(p.style_prompt, shot, chars)
        seed = shot.seed if shot.seed is not None else seed_from("shot:" + shot.id)
        fp = stable_hash("clip", backend.name, p.digest(img), shot.camera, secs, size, fps,
                         p.config["motion"], p.config["video"].get("crf"))
        if not force and p.cache.fresh(out, fp):
            continue
        log("clips", f"[{k}/{len(shots)}] {shot.id} {CAMERA_CN.get(shot.camera, shot.camera)} {secs:.1f}s")
        backend.animate(img, out, secs, size, fps, shot.camera, prompt, p.config["negative_prompt"], seed)
        p.cache.mark(out, fp)
        done += 1
    log("clips", f"共 {len(shots)} 个片段，本次生成 {done} 个")


# ── 7. 字幕 ────────────────────────────────────────────────────────────────────
def stage_subtitles(p: Project, force: bool = False) -> None:
    script, tl = p.script(), _timeline(p)
    scfg = p.config["subtitle"]
    (p.build / "subtitles.ass").write_text(build_ass(script, tl, scfg, p.resolution), encoding="utf-8")
    p.output.mkdir(parents=True, exist_ok=True)
    (p.output / f"{_safe(script.title)}.srt").write_text(build_srt(script, tl, scfg), encoding="utf-8")
    log("subtitles", f"字幕 {sum(len(s['items']) for s in tl['shots'])} 条（output 里另存了一份 .srt 外挂字幕）")


# ── 8. 分镜表 ──────────────────────────────────────────────────────────────────
def stage_storyboard(p: Project, force: bool = False) -> None:
    script, tl = p.script(), _timeline(p)
    times = {s["id"]: s for s in tl["shots"]}
    names = {c.id: c.name for c in script.characters}
    cards = []
    for sc in script.scenes:
        cards.append(f'<h2>{html.escape(sc.id)} · {html.escape(sc.location)} <small>{html.escape(sc.time)} {html.escape(sc.mood)}</small></h2>')
        for sh in sc.shots:
            t = times.get(sh.id, {})
            lines = "".join(
                f'<p class="{"nar" if it["kind"] == "narration" else "line"}"><b>{html.escape("旁白" if it["speaker"] == NARRATOR else names.get(it["speaker"], it["speaker"]))}</b>{html.escape(it["text"])}</p>'
                for it in t.get("items", []))
            cards.append(f"""<article><img src="images/{sh.id}.png" alt="{html.escape(sh.id)}" loading="lazy">
<div><h3>{html.escape(sh.id)} <span>{html.escape(sh.shot)} · {CAMERA_CN.get(sh.camera, sh.camera)} · {t.get('start', 0):.1f}s–{t.get('end', 0):.1f}s</span></h3>
<p class="desc">{html.escape(sh.description)}</p><p class="vis">{html.escape(sh.visual)}</p>{lines}</div></article>""")
    page = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(script.title)} · 分镜表</title><style>
body{{margin:0;padding:24px 16px;font:15px/1.6 system-ui,"PingFang SC","Microsoft YaHei",sans-serif;background:#f4f1ec;color:#222}}
main{{max-width:960px;margin:auto}}h1{{margin:0 0 4px}}h2{{margin:32px 0 12px;font-size:18px;border-bottom:2px solid #c0392b;padding-bottom:4px}}
h2 small{{color:#888;font-weight:400;font-size:13px}}article{{display:grid;grid-template-columns:160px 1fr;gap:16px;background:#fff;border-radius:10px;padding:12px;margin:10px 0;box-shadow:0 1px 4px #0001}}
article img{{width:160px;border-radius:6px;background:#ddd}}h3{{margin:0;font-size:16px}}h3 span{{color:#c0392b;font-size:13px;font-weight:400;margin-left:6px}}
.desc{{margin:4px 0}}.vis{{color:#888;font-size:12px;margin:4px 0}}.line b,.nar b{{display:inline-block;min-width:3.5em;color:#555}}.nar{{color:#8a6d1d}}
@media(max-width:560px){{article{{grid-template-columns:96px 1fr}}article img{{width:96px}}}}</style></head><body><main>
<h1>{html.escape(script.title)}</h1><p>{html.escape(script.logline)}　总时长 {tl['total']:.1f} 秒 · {len(tl['shots'])} 个镜头</p>
{''.join(cards)}</main></body></html>"""
    (p.build / "storyboard.html").write_text(page, encoding="utf-8")
    log("storyboard", "分镜表：build/storyboard.html（用浏览器打开）")


# ── 9. 合成成片 ────────────────────────────────────────────────────────────────
def stage_compose(p: Project, force: bool = False) -> Path:
    script = p.script()
    shots = script.all_shots()
    clips = []
    for sh in shots:
        c = p.build / "clips" / f"{sh.id}.mp4"
        if not c.exists():
            raise ManjuError(f"缺少片段 {c.name}，请先运行 clips 步骤。")
        clips.append(f"clips/{sh.id}.mp4")
    scfg, bcfg = p.config["subtitle"], p.config["bgm"]
    subs = None
    if scfg.get("enabled", True):
        if not (p.build / "subtitles.ass").exists():
            stage_subtitles(p)
        subs = "subtitles.ass"
    fonts_dir = None
    if scfg.get("fonts_dir"):
        fd = p.path(scfg["fonts_dir"])
        local = p.build / "fonts"
        if fd.resolve() != local.resolve():
            shutil.copytree(fd, local, dirs_exist_ok=True)
        fonts_dir = "fonts"
    bgm = p.path(bcfg["file"]) if bcfg.get("file") else None
    if bgm and not bgm.exists():
        raise ManjuError(f"背景音乐 {bcfg['file']} 不存在")
    p.output.mkdir(parents=True, exist_ok=True)
    out = p.output / f"{_safe(script.title)}.mp4"
    log("compose", "合成成片中…")
    t0 = time.time()
    ffmpeg.compose(p.build, clips, "voice_track.wav", out.resolve(), subtitles=subs, fonts_dir=fonts_dir,
                   bgm=bgm.resolve() if bgm else None, bgm_volume=float(bcfg.get("volume", 0.18)),
                   ducking=bool(bcfg.get("ducking", True)), crf=int(p.config["video"].get("crf", 20)))
    log("compose", f"完成：{out}（{ffmpeg.probe_duration(out):.1f} 秒，用时 {time.time() - t0:.0f} 秒）")
    return out


def _safe(name: str) -> str:
    return "".join(c for c in name if c not in '\\/:*?"<>|').strip() or "output"


STAGES = {
    "script": stage_script,
    "characters": stage_characters,
    "images": stage_images,
    "voice": stage_voice,
    "timeline": stage_timeline,
    "clips": stage_clips,
    "subtitles": stage_subtitles,
    "storyboard": stage_storyboard,
    "compose": stage_compose,
}
ORDER = list(STAGES)


def run(p: Project, stages: list[str] | None = None, force: bool = False) -> None:
    for name in stages or ORDER:
        if name not in STAGES:
            raise ManjuError(f"没有 {name} 这个步骤，可选：{', '.join(ORDER)}")
        t0 = time.time()
        STAGES[name](p, force=force)
        if time.time() - t0 > 2:
            log(name, f"用时 {time.time() - t0:.1f} 秒")
