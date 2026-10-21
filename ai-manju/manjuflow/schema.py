"""剧本（script.yaml）的数据结构与校验。

剧本既可以由 LLM 从小说生成，也可以手写。字段名用英文，内容用中文即可。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .util import ManjuError

NARRATOR = "narrator"

# 景别：中文 → 英文提示词
SHOT_TYPES = {
    "大远景": "extreme wide shot",
    "远景": "wide shot",
    "全景": "full shot",
    "中景": "medium shot",
    "近景": "medium close-up shot",
    "特写": "close-up shot",
    "大特写": "extreme close-up shot",
}

# 运镜：中文别名 → 内部名称
CAMERA_ALIASES = {
    "固定": "static", "静止": "static",
    "推": "push_in", "推近": "push_in", "推镜": "push_in",
    "拉": "pull_out", "拉远": "pull_out", "拉镜": "pull_out",
    "左摇": "pan_left", "左移": "pan_left", "向左": "pan_left",
    "右摇": "pan_right", "右移": "pan_right", "向右": "pan_right",
    "上摇": "tilt_up", "上移": "tilt_up", "向上": "tilt_up",
    "下摇": "tilt_down", "下移": "tilt_down", "向下": "tilt_down",
}
CAMERAS = {"static", "push_in", "pull_out", "pan_left", "pan_right", "tilt_up", "tilt_down"}

ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


@dataclass
class Character:
    id: str
    name: str
    appearance: str = ""
    gender: str = ""            # male / female，用来挑默认音色
    voice: str = ""             # project.yaml 里 tts.voices 的键
    voice_hint: str = ""        # 音色描述，仅供参考
    reference: str = ""         # 定妆照路径（相对项目目录）
    seed: int | None = None


@dataclass
class Line:
    speaker: str
    text: str
    emotion: str = ""


@dataclass
class Shot:
    id: str
    shot: str = "中景"
    camera: str = "static"
    visual: str = ""
    description: str = ""
    characters: list[str] = field(default_factory=list)
    narration: str = ""
    lines: list[Line] = field(default_factory=list)
    duration: float | None = None   # 最短时长（秒），不填则按配音长度自动计算
    seed: int | None = None
    scene: "Scene | None" = field(default=None, repr=False)

    @property
    def shot_prompt(self) -> str:
        return SHOT_TYPES.get(self.shot, self.shot)


@dataclass
class Scene:
    id: str
    location: str = ""
    time: str = ""
    mood: str = ""
    shots: list[Shot] = field(default_factory=list)


@dataclass
class Script:
    title: str
    style: str = ""
    logline: str = ""
    characters: list[Character] = field(default_factory=list)
    scenes: list[Scene] = field(default_factory=list)

    def all_shots(self) -> list[Shot]:
        return [s for sc in self.scenes for s in sc.shots]

    def character(self, cid: str) -> Character | None:
        return next((c for c in self.characters if c.id == cid), None)


@dataclass
class VoiceItem:
    """一段需要配音的文字：旁白或台词。"""
    key: str
    shot_id: str
    speaker: str
    text: str
    emotion: str
    kind: str   # narration / line


def voice_items(script: Script) -> list[VoiceItem]:
    items = []
    for shot in script.all_shots():
        if shot.narration.strip():
            items.append(VoiceItem(f"{shot.id}_n", shot.id, NARRATOR, shot.narration.strip(), "", "narration"))
        for j, ln in enumerate(shot.lines, 1):
            if ln.text.strip():
                items.append(VoiceItem(f"{shot.id}_l{j}", shot.id, ln.speaker, ln.text.strip(), ln.emotion, "line"))
    return items


# ── 解析与校验 ────────────────────────────────────────────────────────────────
def _str(v) -> str:
    return "" if v is None else str(v).strip()


def parse_script(data: dict) -> Script:
    """把 dict 解析成 Script；有问题时一次性列出所有错误。"""
    errors: list[str] = []
    if not isinstance(data, dict):
        raise ManjuError("剧本格式不对：顶层应该是一个对象（title / characters / scenes）。")

    chars = []
    for i, c in enumerate(data.get("characters") or []):
        where = f"characters[{i}]"
        if not isinstance(c, dict):
            errors.append(f"{where} 应该是对象")
            continue
        cid = _str(c.get("id"))
        if not cid or not ID_RE.match(cid):
            errors.append(f"{where}.id 必须是英文字母、数字、下划线组成，当前为 {cid!r}")
        if cid == NARRATOR:
            errors.append(f"{where}.id 不能叫 {NARRATOR}，这个名字留给旁白")
        chars.append(Character(
            id=cid, name=_str(c.get("name")) or cid, appearance=_str(c.get("appearance")),
            gender=_str(c.get("gender")).lower(), voice=_str(c.get("voice")),
            voice_hint=_str(c.get("voice_hint")), reference=_str(c.get("reference")),
            seed=int(c["seed"]) if c.get("seed") not in (None, "") else None,
        ))
    ids = [c.id for c in chars]
    dup = {x for x in ids if ids.count(x) > 1}
    if dup:
        errors.append(f"角色 id 重复：{', '.join(sorted(dup))}")
    known = set(ids)

    scenes = []
    shot_ids: list[str] = []
    raw_scenes = data.get("scenes") or []
    if not raw_scenes:
        errors.append("scenes 不能为空，至少要有一个场景")
    for si, sc in enumerate(raw_scenes):
        where = f"scenes[{si}]"
        if not isinstance(sc, dict):
            errors.append(f"{where} 应该是对象")
            continue
        scene = Scene(id=_str(sc.get("id")) or f"s{si + 1}", location=_str(sc.get("location")),
                      time=_str(sc.get("time")), mood=_str(sc.get("mood")))
        for hi, sh in enumerate(sc.get("shots") or []):
            w = f"{where}.shots[{hi}]"
            if not isinstance(sh, dict):
                errors.append(f"{w} 应该是对象")
                continue
            sid = _str(sh.get("id")) or f"{scene.id}_{hi + 1:02d}"
            if not ID_RE.match(sid):
                errors.append(f"{w}.id 只能用英文字母、数字、下划线，当前为 {sid!r}")
            shot_ids.append(sid)
            cam = _str(sh.get("camera")) or "static"
            cam = CAMERA_ALIASES.get(cam, cam)
            if cam not in CAMERAS:
                errors.append(f"{w}.camera 不认识 {cam!r}，可选：{', '.join(sorted(CAMERAS))} 或 推/拉/左摇/右摇/上摇/下摇/固定")
            sc_chars = sh.get("characters") or []
            if isinstance(sc_chars, str):
                sc_chars = [x.strip() for x in re.split(r"[,，\s]+", sc_chars) if x.strip()]
            for cid in sc_chars:
                if cid not in known:
                    errors.append(f"{w}.characters 里的 {cid!r} 没有在 characters 中定义")
            lines = []
            for li, ln in enumerate(sh.get("lines") or []):
                lw = f"{w}.lines[{li}]"
                if isinstance(ln, str):
                    errors.append(f"{lw} 应该写成 {{speaker: 角色id, text: 台词}}")
                    continue
                spk = _str(ln.get("speaker"))
                if spk != NARRATOR and spk not in known:
                    errors.append(f"{lw}.speaker {spk!r} 没有在 characters 中定义")
                txt = _str(ln.get("text"))
                if not txt:
                    errors.append(f"{lw}.text 不能为空")
                lines.append(Line(speaker=spk, text=txt, emotion=_str(ln.get("emotion"))))
            dur = sh.get("duration")
            try:
                dur = float(dur) if dur not in (None, "") else None
            except (TypeError, ValueError):
                errors.append(f"{w}.duration 应该是数字（秒）")
                dur = None
            shot = Shot(
                id=sid, shot=_str(sh.get("shot")) or "中景", camera=cam,
                visual=_str(sh.get("visual")), description=_str(sh.get("description")),
                characters=list(sc_chars), narration=_str(sh.get("narration")), lines=lines,
                duration=dur, seed=int(sh["seed"]) if sh.get("seed") not in (None, "") else None,
                scene=scene,
            )
            if not shot.visual and not shot.description:
                errors.append(f"{w} 至少要写 visual（画面提示词）或 description（画面说明）其中一个")
            scene.shots.append(shot)
        if not scene.shots:
            errors.append(f"{where} 没有镜头（shots）")
        scenes.append(scene)

    dup = {x for x in shot_ids if shot_ids.count(x) > 1}
    if dup:
        errors.append(f"镜头 id 重复：{', '.join(sorted(dup))}")

    if errors:
        raise ManjuError("剧本有 {} 处问题：\n  - ".format(len(errors)) + "\n  - ".join(errors))

    return Script(title=_str(data.get("title")) or "未命名漫剧", style=_str(data.get("style")),
                  logline=_str(data.get("logline")), characters=chars, scenes=scenes)


def script_to_dict(s: Script) -> dict:
    """Script → 可写回 YAML 的 dict（省略空字段，方便人工编辑）。"""
    def clean(d: dict) -> dict:
        return {k: v for k, v in d.items() if v not in ("", None, [], {})}

    return clean({
        "title": s.title, "style": s.style, "logline": s.logline,
        "characters": [clean({
            "id": c.id, "name": c.name, "gender": c.gender, "appearance": c.appearance,
            "voice": c.voice, "voice_hint": c.voice_hint, "reference": c.reference, "seed": c.seed,
        }) for c in s.characters],
        "scenes": [clean({
            "id": sc.id, "location": sc.location, "time": sc.time, "mood": sc.mood,
            "shots": [clean({
                "id": sh.id, "shot": sh.shot, "camera": sh.camera, "description": sh.description,
                "visual": sh.visual, "characters": sh.characters, "narration": sh.narration,
                "lines": [clean({"speaker": ln.speaker, "text": ln.text, "emotion": ln.emotion}) for ln in sh.lines],
                "duration": sh.duration, "seed": sh.seed,
            }) for sh in sc.shots],
        }) for sc in s.scenes],
    })
