"""时间轴：镜头时长由配音长度决定，画面跟着声音走。"""
from __future__ import annotations

from .schema import Script, voice_items


def build_timeline(script: Script, durations: dict[str, float], vcfg: dict) -> dict:
    head = float(vcfg.get("head_pad", 0.35))
    tail = float(vcfg.get("tail_pad", 0.6))
    gap = float(vcfg.get("line_gap", 0.25))
    min_shot = float(vcfg.get("min_shot_seconds", 2.5))

    by_shot: dict[str, list] = {}
    for it in voice_items(script):
        by_shot.setdefault(it.shot_id, []).append(it)

    t = 0.0
    shots = []
    for shot in script.all_shots():
        start = t
        cursor = start + head
        items = []
        for it in by_shot.get(shot.id, []):
            d = float(durations.get(it.key, 0.0))
            items.append({"key": it.key, "speaker": it.speaker, "text": it.text, "kind": it.kind,
                          "start": round(cursor, 3), "end": round(cursor + d, 3)})
            cursor += d + gap
        speech_end = (cursor - gap + tail) if items else start
        need = max(shot.duration or 0.0, min_shot)
        end = max(speech_end, start + need)
        shots.append({"id": shot.id, "start": round(start, 3), "end": round(end, 3),
                      "duration": round(end - start, 3), "items": items})
        t = end
    return {"title": script.title, "total": round(t, 3), "shots": shots}
