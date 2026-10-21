"""字幕：ASS（烧录进画面，带样式）+ SRT（上传平台用的外挂字幕）。"""
from __future__ import annotations

from .schema import NARRATOR, Script
from .util import wrap_cjk


def _ass_time(t: float) -> str:
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _escape(text: str) -> str:
    return text.replace("\\", "＼").replace("{", "｛").replace("}", "｝")


def _cues(script: Script, timeline: dict, scfg: dict):
    names = {c.id: c.name for c in script.characters}
    for shot in timeline["shots"]:
        for it in shot["items"]:
            text = it["text"]
            if scfg.get("show_speaker") and it["speaker"] != NARRATOR:
                text = f"{names.get(it['speaker'], it['speaker'])}：{text}"
            yield it, wrap_cjk(text, float(scfg.get("max_chars", 14)))


def build_ass(script: Script, timeline: dict, scfg: dict, size: tuple[int, int]) -> str:
    w, h = size
    fs = int(h * float(scfg.get("size", 0.042)))
    margin = int(h * float(scfg.get("bottom", 0.16)))
    font = scfg.get("font", "Noto Sans CJK SC")
    outline = max(2, fs // 14)
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Line,{font},{fs},&H00FFFFFF,&H00FFFFFF,&H00101010,&H80000000,-1,0,0,0,100,100,1,0,1,{outline},1,2,40,40,{margin},1
Style: Narration,{font},{int(fs * 0.92)},&H0090E8FF,&H0090E8FF,&H00101010,&H80000000,-1,0,0,0,100,100,1,0,1,{outline},1,2,40,40,{margin},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    rows = []
    for it, lines in _cues(script, timeline, scfg):
        style = "Narration" if it["kind"] == "narration" else "Line"
        text = r"\N".join(_escape(x) for x in lines)
        rows.append(f"Dialogue: 0,{_ass_time(it['start'])},{_ass_time(it['end'])},{style},{it['speaker']},0,0,0,,"
                    r"{\fad(120,120)}" + text)
    return head + "\n".join(rows) + "\n"


def build_srt(script: Script, timeline: dict, scfg: dict) -> str:
    out = []
    for i, (it, lines) in enumerate(_cues(script, timeline, scfg), 1):
        out.append(f"{i}\n{_srt_time(it['start'])} --> {_srt_time(it['end'])}\n" + "\n".join(lines) + "\n")
    return "\n".join(out)
