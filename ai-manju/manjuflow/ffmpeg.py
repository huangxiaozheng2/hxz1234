"""ffmpeg 相关操作：运镜、片段统一、音轨拼接、成片合成。

所有命令都在 build 目录下运行、使用相对路径，避免 Windows 盘符里的冒号
打断 ffmpeg 滤镜参数。
"""
from __future__ import annotations

import json
import subprocess
import wave
from pathlib import Path

from .util import ManjuError, need_tool

SAMPLE_RATE = 44100


def run(args: list[str], cwd: Path | None = None) -> None:
    cmd = [need_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", *args]
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise ManjuError("ffmpeg 出错：\n" + (proc.stderr.strip()[-1500:] or "（没有输出）") +
                         "\n命令：" + " ".join(cmd))


def probe_duration(path: Path) -> float:
    cmd = [need_tool("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)]
    out = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(json.loads(out.stdout)["format"]["duration"])
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        raise ManjuError(f"读不出 {path.name} 的时长：{out.stderr.strip()}") from e


def to_wav(src: Path, dst: Path) -> float:
    """任意音频 → 44.1kHz 单声道 16bit wav，返回时长（秒）。"""
    run(["-i", str(src), "-ac", "1", "-ar", str(SAMPLE_RATE), "-sample_fmt", "s16", str(dst)])
    return wav_duration(dst)


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def silence_wav(dst: Path, seconds: float) -> None:
    with wave.open(str(dst), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(b"\x00\x00" * int(seconds * SAMPLE_RATE))


def assemble_track(segments: list[tuple[float, Path]], total: float, dst: Path) -> None:
    """把若干段 wav 按开始时间摆到一条音轨上（同一时间只会有一段在说话）。"""
    n_total = int(round(total * SAMPLE_RATE))
    buf = bytearray(n_total * 2)
    for start, path in segments:
        with wave.open(str(path), "rb") as w:
            if w.getframerate() != SAMPLE_RATE or w.getnchannels() != 1 or w.getsampwidth() != 2:
                raise ManjuError(f"{path.name} 不是 44.1k 单声道 wav，请先用 to_wav 转换。")
            frames = w.readframes(w.getnframes())
        off = int(round(start * SAMPLE_RATE)) * 2
        end = min(len(buf), off + len(frames))
        buf[off:end] = frames[: end - off]
    with wave.open(str(dst), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(bytes(buf))


# ── 运镜（Ken Burns）──────────────────────────────────────────────────────────
def camera_expr(camera: str, zoom: float, frames: int) -> tuple[str, str, str]:
    """返回 zoompan 的 z / x / y 表达式。p 为 0→1 的进度，用缓动让运动更自然。"""
    p = f"(on/{max(1, frames - 1)})"
    ease = f"(0.5-0.5*cos(PI*{p}))"
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    z_hold = f"{1 + zoom:.3f}"
    if camera == "push_in":
        return f"1+{zoom}*{ease}", cx, cy
    if camera == "pull_out":
        return f"{1 + zoom}-{zoom}*{ease}", cx, cy
    if camera == "pan_left":   # 镜头向左摇：画面内容向右移
        return z_hold, f"(iw-iw/zoom)*(1-{ease})", cy
    if camera == "pan_right":
        return z_hold, f"(iw-iw/zoom)*{ease}", cy
    if camera == "tilt_up":
        return z_hold, cx, f"(ih-ih/zoom)*(1-{ease})"
    if camera == "tilt_down":
        return z_hold, cx, f"(ih-ih/zoom)*{ease}"
    # static：极轻微的呼吸感推进，避免画面完全静止
    return f"1.03+0.02*{ease}", cx, cy


def kenburns(image: Path, dst: Path, seconds: float, size: tuple[int, int], fps: int,
             camera: str, zoom: float, crf: int = 20) -> None:
    w, h = size
    frames = max(1, int(round(seconds * fps)))
    z, x, y = camera_expr(camera, zoom, frames)
    # 先放大到 1.5 倍再 zoompan，减少缩放时的抖动
    bw, bh = int(w * 1.5) // 2 * 2, int(h * 1.5) // 2 * 2
    vf = (f"scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh},setsar=1,"
          f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={w}x{h}:fps={fps},"
          f"format=yuv420p")
    run(["-loop", "1", "-i", str(image), "-vf", vf, "-frames:v", str(frames), "-r", str(fps),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-an", str(dst)])


def conform_clip(src: Path, dst: Path, seconds: float, size: tuple[int, int], fps: int, crf: int = 20) -> None:
    """把 AI 生成的视频统一成目标尺寸、帧率和时长（不够长就定格最后一帧）。"""
    w, h = size
    have = probe_duration(src)
    pad = max(0.0, seconds - have)
    vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps={fps},"
          f"tpad=stop_mode=clone:stop_duration={pad:.3f},format=yuv420p")
    run(["-i", str(src), "-vf", vf, "-t", f"{seconds:.3f}", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", str(crf), "-an", str(dst)])


def compose(build: Path, clips: list[str], audio: str, out: Path, *, subtitles: str | None,
            fonts_dir: str | None, bgm: Path | None, bgm_volume: float, ducking: bool, crf: int) -> None:
    """拼接片段 + 配音 + 背景音乐 + 烧录字幕 → 成片。"""
    (build / "clips.txt").write_text("".join(f"file '{c}'\n" for c in clips), encoding="utf-8")
    args = ["-f", "concat", "-safe", "0", "-i", "clips.txt", "-i", audio]
    if bgm:
        args += ["-stream_loop", "-1", "-i", str(bgm)]
    vf = "[0:v]null"
    if subtitles:
        vf = f"[0:v]ass={subtitles}" + (f":fontsdir={fonts_dir}" if fonts_dir else "")
    graph = [vf + "[v]"]
    if bgm:
        graph.append(f"[2:a]volume={bgm_volume},aformat=sample_rates={SAMPLE_RATE}:channel_layouts=stereo[bg]")
        graph.append("[1:a]aformat=sample_rates=44100:channel_layouts=stereo,asplit=2[vo][sc]")
        if ducking:   # 有人说话时自动压低背景音乐
            graph.append("[bg][sc]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=500[bgd]")
        else:
            graph.append("[sc]anullsink;[bg]anull[bgd]")
        graph.append("[vo][bgd]amix=inputs=2:duration=first:normalize=0[a]")
    else:
        graph.append("[1:a]aformat=sample_rates=44100:channel_layouts=stereo[a]")
    args += ["-filter_complex", ";".join(graph), "-map", "[v]", "-map", "[a]",
             "-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-shortest", str(out)]
    run(args, cwd=build)
