"""合成游戏里用到的音效和背景音乐（五声音阶的拨弦声，类似古筝）。

用法：python3 art/make_audio.py   （需要 numpy 和 ffmpeg）
输出：assets/audio/*.mp3
"""
import os
import subprocess
import tempfile
import wave

import numpy as np

SR = 44100
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "assets", "audio")
rng = np.random.default_rng(7)


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def pluck(freq, dur, decay=0.996, bright=0.5):
    """Karplus-Strong 拨弦合成。"""
    n = int(SR * dur)
    period = max(2, int(SR / freq))
    buf = rng.uniform(-1, 1, period)
    # 低通一下初始噪声，让音色柔和
    for _ in range(int(3 * (1 - bright)) + 1):
        buf = 0.5 * (buf + np.roll(buf, 1))
    out = np.zeros(n)
    for i in range(n):
        v = buf[i % period]
        out[i] = v
        buf[i % period] = decay * 0.5 * (v + buf[(i + 1) % period])
    env = np.minimum(1, np.arange(n) / (SR * 0.004))
    return out * env


def bell(freq, dur, decay=4.0):
    t = np.arange(int(SR * dur)) / SR
    tone = (np.sin(2 * np.pi * freq * t) + 0.4 * np.sin(2 * np.pi * freq * 2.01 * t)
            + 0.15 * np.sin(2 * np.pi * freq * 3.0 * t))
    return tone * np.exp(-decay * t) * np.minimum(1, t / 0.005)


def mix(length, events):
    out = np.zeros(int(SR * length))
    for start, sig, gain in events:
        s = int(SR * start)
        e = min(len(out), s + len(sig))
        out[s:e] += sig[:e - s] * gain
    return out


def write_mp3(name, sig, peak=0.85):
    sig = sig / (np.max(np.abs(sig)) + 1e-9) * peak
    pcm = (sig * 32767).astype(np.int16)
    os.makedirs(OUT, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp = f.name
    with wave.open(tmp, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-codec:a", "libmp3lame",
                    "-b:a", "96k", os.path.join(OUT, name)], check=True)
    os.remove(tmp)
    print("✓", name)


# 宫商角徵羽：D 调五声音阶
PENTA = [62, 64, 66, 69, 71]  # D E F# A B


def scale(i):
    octave, deg = divmod(i, 5)
    return PENTA[deg] + 12 * octave


def correct():
    ev = [(0.0, bell(hz(scale(7)), 0.8), 0.6), (0.11, bell(hz(scale(9)), 1.0), 0.7)]
    return mix(1.1, ev)


def incorrect():
    ev = [(0.0, pluck(hz(scale(2)), 0.6, 0.990, 0.2), 0.8),
          (0.16, pluck(hz(scale(0) - 1), 0.8, 0.988, 0.2), 0.8)]
    return mix(1.0, ev)


def fanfare():
    ev = []
    for k, i in enumerate([5, 6, 7, 8, 9, 10]):
        ev.append((k * 0.09, pluck(hz(scale(i)), 1.2, 0.997, 0.7), 0.6))
    for i in (5, 7, 9, 10):
        ev.append((0.62, pluck(hz(scale(i)), 1.8, 0.998, 0.6), 0.45))
    ev.append((0.62, bell(hz(scale(10)), 1.6, 2.5), 0.4))
    return mix(2.4, ev)


def ambient():
    """约 24 秒、可循环的古筝风背景音乐。"""
    length = 24.0
    ev = []
    beat = 0.75
    melody = [5, 7, 8, 7, 5, 4, 5, None, 7, 8, 9, 8, 7, 5, 7, None,
              4, 5, 7, 5, 4, 2, 4, None, 5, 4, 2, 0, 2, 4, 5, None]
    t = 0.0
    for note in melody:
        if note is not None:
            ev.append((t, pluck(hz(scale(note)), 2.4, 0.9975, 0.55), 0.55))
            # 偶尔加一个高八度的泛音
            if rng.random() < 0.25:
                ev.append((t + 0.02, pluck(hz(scale(note) + 12), 1.6, 0.996, 0.8), 0.18))
        t += beat
    # 低音：每 4 拍一个根音或五度
    for k in range(int(length / (beat * 4))):
        root = scale(0) - 12 if k % 2 == 0 else scale(3) - 12
        ev.append((k * beat * 4, pluck(hz(root), 3.5, 0.9985, 0.2), 0.5))
    sig = mix(length + 2.5, ev)
    # 把尾音叠回开头，循环时不突兀
    tail = sig[int(SR * length):]
    sig = sig[:int(SR * length)]
    sig[:len(tail)] += tail
    return sig


if __name__ == "__main__":
    write_mp3("correct.mp3", correct())
    write_mp3("incorrect.mp3", incorrect(), 0.7)
    write_mp3("fanfare.mp3", fanfare())
    write_mp3("ambient.mp3", ambient(), 0.7)
