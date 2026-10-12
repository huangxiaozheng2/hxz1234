"""生成「淮安印记」全部插画的 SVG 源文件。

用法：
    python3 art/make_art.py        # 生成 art/svg/*.svg
    node art/render.mjs            # 把 SVG 渲染成 assets/ 里的 png / jpg

所有图都是扁平风插画，用代码画出来，方便以后改颜色、改文字。
"""
import math
import os
import random

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "svg")

# ── 配色 ────────────────────────────────────────────────────────────────────
PAPER = "#f3e6cc"
INK = "#2c1508"
RED = "#9e2b25"
DEEP_RED = "#7a2421"
GOLD = "#d4a73a"
TEAL = "#3f7f86"
LIGHT_TEAL = "#7fb2ac"
TILE = "#4a4f57"
WALL = "#f4efe6"
WOOD = "#6b3a22"
FONT = "'WenQuanYi Zen Hei', 'Noto Sans SC', sans-serif"


def svg(w, h, body, bg=None):
    rect = f'<rect width="{w}" height="{h}" fill="{bg}"/>' if bg else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}">{rect}{body}</svg>')


def save(name, content):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(content)


# ── 通用元素 ────────────────────────────────────────────────────────────────
def roof(cx, y, w, h, color=TILE, ridge=None):
    """中式屋顶：檐口两端上翘。y 为檐口底线，h 为屋顶高度。"""
    ridge = ridge or color
    p = (f"M{cx - w / 2},{y - h * 0.38} "
         f"Q{cx - w * 0.42},{y + h * 0.04} {cx - w * 0.3},{y} "
         f"L{cx + w * 0.3},{y} "
         f"Q{cx + w * 0.42},{y + h * 0.04} {cx + w / 2},{y - h * 0.38} "
         f"Q{cx + w * 0.36},{y - h * 0.5} {cx + w * 0.3},{y - h} "
         f"L{cx - w * 0.3},{y - h} "
         f"Q{cx - w * 0.36},{y - h * 0.5} {cx - w / 2},{y - h * 0.38} Z")
    ridge_bar = (f'<rect x="{cx - w * 0.32}" y="{y - h - h * 0.12}" width="{w * 0.64}" '
                 f'height="{h * 0.16}" rx="{h * 0.06}" fill="{ridge}"/>')
    # 瓦楞线
    lines = ""
    n = max(4, int(w / 22))
    for i in range(1, n):
        x = cx - w * 0.3 + (w * 0.6) * i / n
        lines += (f'<line x1="{x}" y1="{y - h * 0.92}" x2="{x}" y2="{y - 2}" '
                  f'stroke="#000" stroke-opacity="0.12" stroke-width="{max(1.5, w / 160)}"/>')
    return f'<path d="{p}" fill="{color}"/>{lines}{ridge_bar}'


def cloud(x, y, s=1.0, color="#fff", opacity=0.9):
    """祥云：几个圆弧叠成，带一个卷尾。"""
    return (f'<g transform="translate({x},{y}) scale({s})" fill="{color}" opacity="{opacity}">'
            f'<ellipse cx="0" cy="0" rx="70" ry="26"/>'
            f'<circle cx="-30" cy="-14" r="26"/>'
            f'<circle cx="12" cy="-24" r="32"/>'
            f'<circle cx="46" cy="-8" r="22"/>'
            f'<path d="M-70,4 q-26,-2 -22,-24 q4,-16 20,-10" fill="none" stroke="{color}" '
            f'stroke-width="10" stroke-linecap="round"/>'
            f'</g>')


def lantern(x, y, s=1.0):
    return (f'<g transform="translate({x},{y}) scale({s})">'
            f'<line x1="0" y1="-60" x2="0" y2="-32" stroke="{INK}" stroke-width="3"/>'
            f'<rect x="-14" y="-36" width="28" height="8" rx="2" fill="{GOLD}"/>'
            f'<ellipse cx="0" cy="0" rx="34" ry="30" fill="#c8322a"/>'
            f'<ellipse cx="0" cy="0" rx="18" ry="30" fill="none" stroke="#e8645a" stroke-width="3"/>'
            f'<line x1="-34" y1="0" x2="34" y2="0" stroke="#e8645a" stroke-width="2" opacity="0.6"/>'
            f'<rect x="-14" y="28" width="28" height="8" rx="2" fill="{GOLD}"/>'
            f'<path d="M-8,36 L-10,62 M0,36 L0,66 M8,36 L10,62" stroke="{GOLD}" stroke-width="3"/>'
            f'</g>')


def willow(x, y, flip=False, n=9, length=520, seed=1):
    """垂柳：从角落垂下的柳条。"""
    rnd = random.Random(seed)
    sx = -1 if flip else 1
    out = f'<g transform="translate({x},{y}) scale({sx},1)">'
    out += (f'<path d="M-40,-20 Q120,10 260,60" fill="none" stroke="#5b4630" '
            f'stroke-width="16" stroke-linecap="round"/>')
    for i in range(n):
        bx = 10 + i * 28
        by = 2 + i * 6
        ln = length * (0.55 + rnd.random() * 0.45)
        sway = rnd.uniform(-40, 40)
        out += (f'<path d="M{bx},{by} Q{bx + sway},{by + ln * 0.5} {bx + sway * 0.4},{by + ln}" '
                f'fill="none" stroke="#6e9a4a" stroke-width="3"/>')
        out += (f'<path d="M{bx},{by + 20} Q{bx + sway},{by + ln * 0.5} {bx + sway * 0.4},{by + ln}" '
                f'fill="none" stroke="#8fbf5e" stroke-width="10" stroke-dasharray="14 10" '
                f'stroke-linecap="round" opacity="0.9"/>')
    return out + "</g>"


def water_ripples(x0, y0, w, h, n=18, seed=3, color="#fff", opacity=0.35):
    rnd = random.Random(seed)
    out = ""
    for _ in range(n):
        x = x0 + rnd.random() * w
        y = y0 + rnd.random() * h
        ln = 30 + rnd.random() * 90
        out += (f'<line x1="{x}" y1="{y}" x2="{x + ln}" y2="{y}" stroke="{color}" '
                f'stroke-opacity="{opacity}" stroke-width="4" stroke-linecap="round"/>')
    return out


def boat(x, y, s=1.0, sail=True, sail_color=RED):
    """漕船：船身 + 船篷 + 帆。"""
    out = f'<g transform="translate({x},{y}) scale({s})">'
    if sail:
        out += f'<line x1="10" y1="-10" x2="10" y2="-230" stroke="{WOOD}" stroke-width="6"/>'
        out += (f'<path d="M14,-220 Q90,-160 96,-40 L14,-40 Z" fill="{sail_color}"/>')
        for i in range(1, 5):
            yy = -220 + i * 36
            out += (f'<line x1="14" y1="{yy}" x2="{40 + i * 13}" y2="{yy}" stroke="#000" '
                    f'stroke-opacity="0.18" stroke-width="3"/>')
    out += (f'<path d="M-120,-30 Q-40,-36 120,-30 Q150,-32 160,-50 L150,-6 Q100,22 -100,22 '
            f'Q-140,10 -150,-40 Z" fill="{WOOD}"/>')
    out += f'<path d="M-120,-30 Q-40,-36 120,-30" fill="none" stroke="#8a5434" stroke-width="5"/>'
    out += f'<path d="M-90,-30 Q-50,-92 0,-30 Z" fill="#3d2a1c"/>'
    out += f'<path d="M-80,-30 Q-50,-80 -12,-30" fill="none" stroke="#5d4430" stroke-width="4"/>'
    return out + "</g>"


def arch_bridge(cx, y, w, h, color="#c9b89a", shadow="#a8977a"):
    p = (f"M{cx - w / 2},{y} L{cx - w / 2},{y - h * 0.55} Q{cx},{y - h * 1.15} {cx + w / 2},{y - h * 0.55} "
         f"L{cx + w / 2},{y} L{cx + w * 0.3},{y} A{w * 0.3},{h * 0.72} 0 0 0 {cx - w * 0.3},{y} Z")
    rail = f'<path d="M{cx - w / 2},{y - h * 0.62} Q{cx},{y - h * 1.22} {cx + w / 2},{y - h * 0.62}" fill="none" stroke="{shadow}" stroke-width="{h * 0.08}"/>'
    stones = ""
    for i in range(1, 8):
        a = math.pi - i * math.pi / 8
        x1 = cx + w * 0.3 * math.cos(a)
        y1 = y - h * 0.72 * math.sin(a)
        x2 = cx + w * 0.36 * math.cos(a)
        y2 = y - h * 0.86 * math.sin(a)
        stones += f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{shadow}" stroke-width="3"/>'
    return f'<path d="{p}" fill="{color}"/>{rail}{stones}'


def pagoda(cx, base, w, tier_h, tiers=7, body="#c89a6a", roof_c="#5a4a42"):
    """文通塔式的八角砖塔。"""
    out = ""
    y = base
    for i in range(tiers):
        bw = w * (1 - i * 0.085)
        th = tier_h * (1 - i * 0.04)
        out += f'<rect x="{cx - bw / 2}" y="{y - th}" width="{bw}" height="{th}" fill="{body}"/>'
        out += f'<rect x="{cx - bw / 2}" y="{y - th}" width="{bw * 0.18}" height="{th}" fill="#000" opacity="0.08"/>'
        out += (f'<path d="M{cx - bw * 0.1},{y - th * 0.2} L{cx - bw * 0.1},{y - th * 0.55} '
                f'Q{cx},{y - th * 0.75} {cx + bw * 0.1},{y - th * 0.55} L{cx + bw * 0.1},{y - th * 0.2} Z" '
                f'fill="#3a2a22"/>')
        y -= th
        out += roof(cx, y + th * 0.08, bw * 1.5, th * 0.42, roof_c)
        y -= th * 0.22
    out += f'<line x1="{cx}" y1="{y}" x2="{cx}" y2="{y - tier_h * 1.1}" stroke="{GOLD}" stroke-width="{w * 0.05}"/>'
    for k in range(3):
        out += f'<circle cx="{cx}" cy="{y - tier_h * (0.3 + k * 0.25)}" r="{w * 0.07}" fill="{GOLD}"/>'
    return out


def hall(cx, base, w, h, eaves=2, column=RED, roof_c=TILE, wall="#e9dcc4"):
    """重檐楼阁：红柱 + 层层屋檐。"""
    out = ""
    y = base
    for i in range(eaves):
        bw = w * (1 - i * 0.22)
        bh = h * (1 - i * 0.18)
        out += f'<rect x="{cx - bw / 2}" y="{y - bh}" width="{bw}" height="{bh}" fill="{wall}"/>'
        cols = 5
        for c in range(cols + 1):
            x = cx - bw / 2 + bw * c / cols
            out += f'<rect x="{x - bw * 0.015}" y="{y - bh}" width="{bw * 0.03}" height="{bh}" fill="{column}"/>'
        out += (f'<rect x="{cx - bw / 2}" y="{y - bh * 0.32}" width="{bw}" height="{bh * 0.05}" '
                f'fill="{column}"/>')
        y -= bh
        out += roof(cx, y + 4, bw * 1.36, bh * 0.62, roof_c)
        y -= bh * 0.62
    return out


def seal_text(cx, cy, size, chars, color="#fff", weight=700):
    """把四个字排成 2×2 的印章字。"""
    out = ""
    pos = [(0, 0), (1, 0), (0, 1), (1, 1)]  # 按现代习惯从左往右、从上往下读
    for ch, (col, row) in zip(chars, pos):
        x = cx + (col - 0.5) * size
        y = cy + (row - 0.5) * size + size * 0.36
        out += (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size * 0.92}" '
                f'font-weight="{weight}" fill="{color}" text-anchor="middle">{ch}</text>')
    return out


# ── 1. 首页背景 1080×1920 ───────────────────────────────────────────────────
def intro_bg():
    w, h = 1080, 1920
    b = f'''<defs>
<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#e48a5a"/><stop offset="0.45" stop-color="#f4c38a"/>
  <stop offset="0.62" stop-color="#f8dfb2"/></linearGradient>
<linearGradient id="water" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#6aa3a0"/><stop offset="1" stop-color="#2f6670"/></linearGradient>
<radialGradient id="sun" cx="0.5" cy="0.5" r="0.5">
  <stop offset="0" stop-color="#fff2c8"/><stop offset="0.55" stop-color="#ffd27a"/>
  <stop offset="1" stop-color="#ffd27a" stop-opacity="0"/></radialGradient>
</defs>
<rect width="{w}" height="{h}" fill="url(#sky)"/>
<circle cx="760" cy="430" r="260" fill="url(#sun)"/>
<circle cx="760" cy="430" r="120" fill="#ffe7a8"/>
{cloud(220, 260, 1.4, "#fff3dd", 0.85)}{cloud(900, 180, 1.0, "#fff3dd", 0.7)}{cloud(560, 640, 1.2, "#fff3dd", 0.6)}
<path d="M0,1140 Q180,1020 360,1090 T720,1060 T1080,1080 L1080,1260 L0,1260 Z" fill="#d79a72" opacity="0.55"/>
<path d="M0,1180 Q240,1100 460,1160 T900,1130 T1080,1150 L1080,1260 L0,1260 Z" fill="#b97a5a" opacity="0.6"/>
{pagoda(210, 1250, 150, 105, tiers=7)}
<!-- 镇淮楼：城台 + 重檐楼 -->
<rect x="640" y="1100" width="380" height="160" fill="#a4806a"/>
<path d="M790,1260 L790,1180 Q830,1130 870,1180 L870,1260 Z" fill="#3a2a22"/>
{hall(830, 1100, 300, 100, eaves=2)}
<rect x="0" y="1250" width="{w}" height="{h - 1250}" fill="url(#water)"/>
<g opacity="0.35" transform="translate(0,2500) scale(1,-1)">
  {pagoda(210, 1250, 150, 105, tiers=7, body="#ffffff", roof_c="#ffffff")}
</g>
{water_ripples(0, 1290, w, 620, n=40, seed=7)}
<rect x="0" y="1240" width="{w}" height="22" fill="#8c7a63"/>
{arch_bridge(540, 1520, 560, 220)}
{boat(300, 1720, 1.25)}
{boat(860, 1610, 0.75, sail_color="#c4703a")}
{willow(-30, -10, n=10, length=560, seed=2)}
{willow(1110, -10, flip=True, n=8, length=480, seed=5)}
{lantern(700, 1060, 0.7)}{lantern(960, 1060, 0.7)}
'''
    save("intro-bg.svg", svg(w, h, b))


# ── 2. 第一站：周恩来故里（白墙黛瓦的故居大门）1200×960 ─────────────────────
def zone01():
    w, h = 1200, 960
    b = f'''<defs><linearGradient id="sky1" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#9fcbd6"/><stop offset="1" stop-color="#e6f0e6"/></linearGradient></defs>
<rect width="{w}" height="{h}" fill="url(#sky1)"/>
{cloud(220, 140, 1.1)}{cloud(980, 110, 0.9)}
<!-- 远处的树 -->
<circle cx="120" cy="420" r="150" fill="#7aa36a"/><circle cx="260" cy="380" r="120" fill="#8db57a"/>
<circle cx="1080" cy="400" r="160" fill="#7aa36a"/><circle cx="950" cy="370" r="110" fill="#8db57a"/>
<rect x="110" y="480" width="22" height="200" fill="#5b4630"/><rect x="1070" y="470" width="22" height="200" fill="#5b4630"/>
<!-- 白墙 -->
<rect x="0" y="470" width="{w}" height="330" fill="{WALL}"/>
<rect x="0" y="450" width="{w}" height="30" fill="{TILE}"/>
<path d="M0,450 L{w},450" stroke="#2f3338" stroke-width="10"/>
<!-- 门楼 -->
<rect x="400" y="380" width="400" height="420" fill="#ebe4d6"/>
{roof(600, 392, 560, 120, TILE, "#2f3338")}
<rect x="455" y="430" width="290" height="60" fill="#1f1a17" rx="4"/>
<rect x="461" y="436" width="278" height="48" fill="none" stroke="{GOLD}" stroke-width="3" rx="3"/>
<text x="600" y="474" font-family="{FONT}" font-size="38" font-weight="700" fill="{GOLD}" text-anchor="middle" letter-spacing="6">周恩来故居</text>
<rect x="470" y="520" width="260" height="280" fill="#3b2418"/>
<rect x="478" y="528" width="118" height="272" fill="#5a3422"/><rect x="604" y="528" width="118" height="272" fill="#5a3422"/>
<circle cx="584" cy="660" r="9" fill="{GOLD}"/><circle cx="616" cy="660" r="9" fill="{GOLD}"/>
<!-- 门边的窗 -->
<rect x="140" y="560" width="160" height="120" fill="#5a3422"/>
<path d="M150,570 h140 v100 h-140 Z M220,570 v100 M150,620 h140" stroke="#c9a77a" stroke-width="5" fill="none"/>
<rect x="900" y="560" width="160" height="120" fill="#5a3422"/>
<path d="M910,570 h140 v100 h-140 Z M980,570 v100 M910,620 h140" stroke="#c9a77a" stroke-width="5" fill="none"/>
<!-- 台阶与地面 -->
<rect x="0" y="800" width="{w}" height="160" fill="#b9ad98"/>
<rect x="430" y="800" width="340" height="26" fill="#a0937e"/><rect x="400" y="826" width="400" height="26" fill="#d0c5b0"/>
<path d="M0,880 L{w},880 M0,930 L{w},930" stroke="#a0937e" stroke-width="3"/>
<!-- 盆栽 -->
<rect x="330" y="740" width="60" height="60" fill="#8a5434"/><circle cx="360" cy="720" r="42" fill="#5f8f4e"/>
<rect x="810" y="740" width="60" height="60" fill="#8a5434"/><circle cx="840" cy="720" r="42" fill="#5f8f4e"/>
{lantern(430, 470, 0.9)}{lantern(770, 470, 0.9)}
'''
    save("zone-01.svg", svg(w, h, b))


# ── 3. 第二站：河下古镇 · 西游记 1200×960 ────────────────────────────────────
def monkey_king(x, y, s=1.0):
    """筋斗云上的卡通孙悟空。"""
    return f'''<g transform="translate({x},{y}) scale({s})">
<!-- 金箍棒 -->
<g transform="rotate(-28)">
  <rect x="-190" y="-8" width="380" height="16" rx="6" fill="{GOLD}"/>
  <rect x="-190" y="-10" width="40" height="20" rx="4" fill="{RED}"/>
  <rect x="150" y="-10" width="40" height="20" rx="4" fill="{RED}"/>
</g>
<!-- 披风 -->
<path d="M-50,40 Q-120,120 -90,190 L-10,140 Z" fill="{RED}"/>
<!-- 身体 -->
<path d="M-45,40 Q0,20 45,40 L55,150 Q0,170 -55,150 Z" fill="#e8b04a"/>
<path d="M-50,95 L50,95" stroke="{RED}" stroke-width="12"/>
<rect x="-45" y="150" width="30" height="40" rx="10" fill="#7a4a2a"/><rect x="15" y="150" width="30" height="40" rx="10" fill="#7a4a2a"/>
<!-- 手臂 -->
<path d="M40,50 Q90,40 105,-5" stroke="#8a5a34" stroke-width="22" fill="none" stroke-linecap="round"/>
<path d="M-40,55 Q-80,80 -95,40" stroke="#8a5a34" stroke-width="22" fill="none" stroke-linecap="round"/>
<!-- 头 -->
<circle cx="0" cy="-20" r="62" fill="#8a5a34"/>
<circle cx="-62" cy="-18" r="18" fill="#e9b98f"/><circle cx="62" cy="-18" r="18" fill="#e9b98f"/>
<path d="M-42,-24 Q-40,-56 0,-48 Q40,-56 42,-24 Q46,26 0,34 Q-46,26 -42,-24 Z" fill="#f3cfa6"/>
<ellipse cx="-17" cy="-14" rx="8" ry="10" fill="{INK}"/><ellipse cx="17" cy="-14" rx="8" ry="10" fill="{INK}"/>
<circle cx="-14" cy="-18" r="3" fill="#fff"/><circle cx="20" cy="-18" r="3" fill="#fff"/>
<path d="M-14,12 Q0,22 14,12" stroke="{INK}" stroke-width="4" fill="none" stroke-linecap="round"/>
<ellipse cx="-30" cy="6" rx="8" ry="5" fill="#e8807a" opacity="0.7"/><ellipse cx="30" cy="6" rx="8" ry="5" fill="#e8807a" opacity="0.7"/>
<!-- 金箍 -->
<path d="M-60,-46 Q0,-80 60,-46" stroke="{GOLD}" stroke-width="12" fill="none" stroke-linecap="round"/>
<circle cx="0" cy="-64" r="8" fill="{RED}"/>
</g>'''


def zone02():
    w, h = 1200, 960
    b = f'''<defs><linearGradient id="sky2" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#f6c98f"/><stop offset="1" stop-color="#fbe8c8"/></linearGradient></defs>
<rect width="{w}" height="{h}" fill="url(#sky2)"/>
<!-- 花果山 -->
<path d="M0,560 L120,330 L230,450 L380,220 L520,430 L640,300 L780,470 L900,260 L1060,420 L1200,300 L1200,640 L0,640 Z" fill="#9db58a" opacity="0.7"/>
<path d="M0,620 L160,440 L300,540 L470,380 L640,560 L820,420 L990,560 L1200,430 L1200,700 L0,700 Z" fill="#6f9a6a"/>
{cloud(300, 200, 0.9, "#fff", 0.85)}{cloud(1040, 150, 0.8, "#fff", 0.8)}
<!-- 筋斗云 + 孙悟空 -->
<g transform="translate(840,330)">
  <path d="M-200,40 Q-210,-20 -140,-10 Q-120,-60 -50,-40 Q0,-80 60,-40 Q130,-60 150,0 Q220,10 190,60 Q100,90 -100,80 Q-200,80 -200,40 Z" fill="#fff"/>
  <path d="M-200,40 q-60,10 -90,-30 q-20,-40 20,-50" fill="none" stroke="#fff" stroke-width="22" stroke-linecap="round"/>
  {monkey_king(0, -140, 0.9)}
</g>
<!-- 河下古镇的明清老街 -->
<rect x="0" y="660" width="{w}" height="300" fill="#e7dcc6"/>
<rect x="30" y="600" width="330" height="200" fill="{WALL}"/>{roof(195, 610, 420, 90)}
<rect x="80" y="680" width="80" height="120" fill="#5a3422"/><rect x="220" y="670" width="90" height="60" fill="#5a3422"/>
<rect x="420" y="640" width="360" height="180" fill="{WALL}"/>{roof(600, 650, 450, 95)}
<rect x="540" y="700" width="120" height="120" fill="#3b2418"/>
<rect x="520" y="660" width="160" height="34" fill="#1f1a17"/>
<text x="600" y="686" font-family="{FONT}" font-size="22" font-weight="700" fill="{GOLD}" text-anchor="middle" letter-spacing="3">吴承恩故居</text>
<rect x="840" y="600" width="330" height="200" fill="{WALL}"/>{roof(1005, 610, 420, 90)}
<rect x="900" y="660" width="90" height="60" fill="#5a3422"/><rect x="1040" y="680" width="80" height="120" fill="#5a3422"/>
<!-- 石板路 -->
<path d="M0,820 L{w},820 L{w},960 L0,960 Z" fill="#a9a08f"/>
''' + "".join(
        f'<rect x="{x}" y="{y}" width="110" height="40" rx="6" fill="#bdb4a2" stroke="#8f8676" stroke-width="3"/>'
        for y in (830, 875, 920) for x in range(-40 + (y % 2) * 55, 1200, 120)
    ) + f'''
{lantern(380, 640, 0.8)}{lantern(820, 640, 0.8)}
'''
    save("zone-02.svg", svg(w, h, b))


# ── 4. 第三站：清江浦 · 大运河 1200×960 ──────────────────────────────────────
def zone03():
    w, h = 1200, 960
    b = f'''<defs>
<linearGradient id="sky3" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e98b5c"/><stop offset="0.6" stop-color="#f7cf95"/><stop offset="1" stop-color="#fbe6c2"/></linearGradient>
<linearGradient id="water3" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e9b986"/><stop offset="0.15" stop-color="#6aa3a0"/><stop offset="1" stop-color="#2f6670"/></linearGradient>
</defs>
<rect width="{w}" height="{h}" fill="url(#sky3)"/>
<circle cx="360" cy="330" r="90" fill="#ffe7a8"/>
{cloud(820, 150, 1.0, "#fff3dd", 0.8)}{cloud(160, 120, 0.7, "#fff3dd", 0.7)}
<!-- 远岸 -->
<path d="M0,480 Q300,440 600,470 T1200,460 L1200,520 L0,520 Z" fill="#b97a5a" opacity="0.7"/>
<!-- 清江浦楼 -->
<rect x="700" y="420" width="460" height="110" fill="#a4806a"/>
<rect x="700" y="520" width="460" height="20" fill="#8c6a55"/>
{hall(930, 420, 330, 110, eaves=2)}
<rect x="860" y="250" width="140" height="34" fill="#1f1a17"/>
<text x="930" y="276" font-family="{FONT}" font-size="22" font-weight="700" fill="{GOLD}" text-anchor="middle" letter-spacing="3">清江浦楼</text>
<!-- 河水 -->
<rect x="0" y="520" width="{w}" height="{h - 520}" fill="url(#water3)"/>
{water_ripples(0, 560, w, 380, n=34, seed=11)}
<!-- 堤岸 -->
<path d="M0,520 L0,470 L620,500 L700,530 Z" fill="#8c7a63"/>
{arch_bridge(260, 560, 380, 150)}
{boat(460, 820, 1.0)}
{boat(980, 760, 0.7, sail_color="#c4703a")}
{boat(130, 900, 0.55, sail=False)}
{willow(-40, -20, n=7, length=420, seed=9)}
'''
    save("zone-03.svg", svg(w, h, b))


# ── 5. 第四站：淮扬美食（俯视的饭桌）1200×960 ──────────────────────────────
def zone04():
    w, h = 1200, 960
    rnd = random.Random(4)
    grain = "".join(
        f'<path d="M0,{y} Q300,{y + rnd.uniform(-14, 14)} 600,{y} T1200,{y}" stroke="#7a4a2c" stroke-width="3" fill="none" opacity="0.35"/>'
        for y in range(40, h, 70))
    # 软兜长鱼：一盘油亮的鳝鱼脊背
    eel = ""
    for i in range(14):
        a = rnd.uniform(0, math.pi * 2)
        r = rnd.uniform(0, 95)
        x, y = 330 + r * math.cos(a), 330 + r * math.sin(a) * 0.9
        ang = rnd.uniform(-70, 70)
        eel += (f'<g transform="translate({x},{y}) rotate({ang})">'
                f'<path d="M-70,0 Q0,-22 70,0" stroke="#4a2410" stroke-width="22" fill="none" stroke-linecap="round"/>'
                f'<path d="M-60,-4 Q0,-22 60,-4" stroke="#8a4a22" stroke-width="6" fill="none" stroke-linecap="round" opacity="0.8"/></g>')
    scallion = "".join(
        f'<circle cx="{330 + rnd.uniform(-110, 110)}" cy="{330 + rnd.uniform(-100, 100)}" r="{rnd.uniform(5, 9)}" fill="#7cbf4a"/>'
        for _ in range(18))
    garlic = "".join(
        f'<circle cx="{330 + rnd.uniform(-100, 100)}" cy="{330 + rnd.uniform(-90, 90)}" r="4" fill="#fff6dc"/>'
        for _ in range(20))
    # 平桥豆腐：一碗嫩豆腐羹
    tofu = "".join(
        f'<rect x="{850 + rnd.uniform(-110, 80)}" y="{330 + rnd.uniform(-100, 80)}" width="34" height="34" rx="5" fill="#fbf5e6" stroke="#e6dcc4" stroke-width="2" transform="rotate({rnd.uniform(-30, 30)} 870 350)"/>'
        for _ in range(16))
    shrimp = "".join(
        f'<path d="M{x},{y} q14,-16 28,0" stroke="#e8805a" stroke-width="8" fill="none" stroke-linecap="round"/>'
        for x, y in ((790, 300), (900, 400), (880, 270), (800, 400)))
    b = f'''<rect width="{w}" height="{h}" fill="#9a6440"/>{grain}
<!-- 桌旗 -->
<rect x="0" y="560" width="{w}" height="160" fill="{RED}" opacity="0.9"/>
<path d="M0,575 L{w},575 M0,705 L{w},705" stroke="{GOLD}" stroke-width="4" stroke-dasharray="18 10"/>
<!-- 软兜长鱼 -->
<ellipse cx="338" cy="345" rx="240" ry="225" fill="#000" opacity="0.18"/>
<circle cx="330" cy="330" r="230" fill="#fdfaf2"/>
<circle cx="330" cy="330" r="200" fill="none" stroke="#3f7f86" stroke-width="6"/>
<circle cx="330" cy="330" r="186" fill="none" stroke="#3f7f86" stroke-width="2" stroke-dasharray="10 8"/>
<ellipse cx="330" cy="330" rx="150" ry="140" fill="#7a3a16" opacity="0.5"/>
{eel}{garlic}{scallion}
<!-- 平桥豆腐 -->
<ellipse cx="868" cy="345" rx="200" ry="195" fill="#000" opacity="0.18"/>
<circle cx="860" cy="335" r="195" fill="#fdfaf2"/>
<circle cx="860" cy="335" r="160" fill="#e9c48a"/>
<circle cx="860" cy="335" r="160" fill="none" stroke="#c9a06a" stroke-width="4"/>
{tofu}{shrimp}
<circle cx="830" cy="360" r="9" fill="#7cbf4a"/><circle cx="910" cy="300" r="7" fill="#7cbf4a"/><circle cx="870" cy="420" r="8" fill="#7cbf4a"/>
<!-- 文楼汤包：蒸笼 + 一个大汤包 + 吸管 -->
<ellipse cx="612" cy="770" rx="220" ry="160" fill="#000" opacity="0.2"/>
<circle cx="600" cy="755" r="190" fill="#d9b77a"/>
<clipPath id="steamer"><circle cx="600" cy="755" r="170"/></clipPath>
<circle cx="600" cy="755" r="170" fill="#e8cf98"/>
<g clip-path="url(#steamer)">''' + "".join(
        f'<line x1="{600 - 170}" y1="{755 + k}" x2="{600 + 170}" y2="{755 + k}" stroke="#c9a46a" stroke-width="3" opacity="0.6"/>'
        for k in range(-150, 160, 26)) + f'''
</g>
<circle cx="600" cy="755" r="170" fill="none" stroke="#b08850" stroke-width="10"/>
<defs><radialGradient id="bun" cx="0.42" cy="0.38" r="0.65"><stop offset="0" stop-color="#fffdf6"/><stop offset="0.7" stop-color="#f6ead2"/><stop offset="1" stop-color="#e2cfa8"/></radialGradient></defs>
<ellipse cx="606" cy="768" rx="138" ry="132" fill="#000" opacity="0.12"/>
<circle cx="600" cy="755" r="135" fill="url(#bun)"/>
<ellipse cx="560" cy="700" rx="40" ry="22" fill="#fff" opacity="0.6" transform="rotate(-30 560 700)"/>
''' + "".join(
        f'<path d="M600,755 L{600 + 128 * math.cos(math.radians(a))},{755 + 128 * math.sin(math.radians(a))}" stroke="#eadfc8" stroke-width="5" stroke-linecap="round"/>'
        for a in range(0, 360, 20)) + f'''
<circle cx="600" cy="755" r="26" fill="#f3e6cc" stroke="#eadfc8" stroke-width="4"/>
<!-- 吸管 -->
<g transform="rotate(-35 600 755)"><rect x="590" y="520" width="20" height="240" rx="8" fill="{RED}"/><rect x="590" y="560" width="20" height="16" fill="#fff" opacity="0.8"/><rect x="590" y="610" width="20" height="16" fill="#fff" opacity="0.8"/></g>
<!-- 醋碟和姜丝 -->
<circle cx="1020" cy="800" r="80" fill="#fdfaf2"/><circle cx="1020" cy="800" r="58" fill="#5a2a14"/>
''' + "".join(
        f'<line x1="{1000 + rnd.uniform(-20, 20)}" y1="{790 + rnd.uniform(-20, 20)}" x2="{1030 + rnd.uniform(-20, 20)}" y2="{800 + rnd.uniform(-20, 20)}" stroke="#f0c45a" stroke-width="4" stroke-linecap="round"/>'
        for _ in range(8)) + f'''
<!-- 筷子 -->
<g transform="rotate(-12 150 780)"><rect x="40" y="740" width="300" height="12" rx="5" fill="#3b2418"/><rect x="40" y="770" width="300" height="12" rx="5" fill="#3b2418"/>
<rect x="40" y="740" width="70" height="12" fill="{GOLD}"/><rect x="40" y="770" width="70" height="12" fill="{GOLD}"/></g>
'''
    save("zone-04.svg", svg(w, h, b))


# ── 6. 旅程地图 1024×1536 ───────────────────────────────────────────────────
def journey_map():
    w, h = 1024, 1536
    stops = [  # (x, y, 序号, 名字, 小图标)
        (360, 1190, "1", "周恩来故里", "house"),
        (700, 950, "2", "河下古镇", "monkey"),
        (360, 700, "3", "清江浦 · 运河", "tower"),
        (700, 470, "4", "淮扬美食", "bowl"),
    ]
    start = (520, 1400)
    end = (510, 230)
    pts = [start] + [(x, y) for x, y, *_ in stops] + [end]
    route = f"M{pts[0][0]},{pts[0][1]}"
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        my = (y0 + y1) / 2
        route += f" C{x0},{my} {x1},{my} {x1},{y1}"

    def icon(kind, x, y):
        if kind == "house":
            return (f'<g transform="translate({x},{y})"><rect x="-38" y="-10" width="76" height="46" fill="{WALL}" stroke="{INK}" stroke-width="3"/>'
                    f'{roof(0, -6, 104, 34, TILE)}<rect x="-12" y="8" width="24" height="28" fill="#5a3422"/></g>')
        if kind == "monkey":
            return (f'<g transform="translate({x},{y})">{cloud(0, 30, 0.55, "#fff", 1)}'
                    f'<circle cx="0" cy="-6" r="26" fill="#8a5a34"/>'
                    f'<path d="M-18,-8 Q-17,-24 0,-20 Q17,-24 18,-8 Q20,12 0,15 Q-20,12 -18,-8 Z" fill="#f3cfa6"/>'
                    f'<circle cx="-7" cy="-6" r="3.5" fill="{INK}"/><circle cx="7" cy="-6" r="3.5" fill="{INK}"/>'
                    f'<path d="M-26,-20 Q0,-36 26,-20" stroke="{GOLD}" stroke-width="5" fill="none"/></g>')
        if kind == "tower":
            return f'<g transform="translate({x},{y + 30})">{hall(0, 0, 70, 26, eaves=2)}</g>'
        return (f'<g transform="translate({x},{y})"><ellipse cx="0" cy="10" rx="46" ry="16" fill="#fdfaf2" stroke="{INK}" stroke-width="3"/>'
                f'<path d="M-44,8 Q0,60 44,8 Z" fill="#fdfaf2" stroke="{INK}" stroke-width="3"/>'
                f'<ellipse cx="0" cy="10" rx="36" ry="10" fill="#e9c48a"/>'
                f'<path d="M-10,-6 q6,-14 0,-26 M8,-6 q6,-14 0,-26" stroke="#b0a090" stroke-width="3" fill="none"/></g>')

    stop_svg = ""
    for x, y, num, name, kind in stops:
        left = x < w / 2
        ix = x + (170 if left else -170)
        lx = x + (-30 if left else 30)
        anchor = "end" if left else "start"
        label_w = 44 * len(name.replace(" ", "")) + 24
        rx = lx - label_w if left else lx
        rx = min(max(rx, 60), w - 60 - label_w)  # 不超出画框
        stop_svg += (f'{icon(kind, ix, y - 10)}'
                     f'<rect x="{rx - 10}" y="{y + 50}" width="{label_w + 20}" height="70" rx="35" fill="{PAPER}" stroke="{WOOD}" stroke-width="3"/>'
                     f'<text x="{rx + (label_w + 0) / 2}" y="{y + 100}" font-family="{FONT}" font-size="42" font-weight="700" fill="{INK}" text-anchor="middle">{name}</text>'
                     f'<rect x="{x - 42}" y="{y - 42}" width="84" height="84" rx="12" fill="{RED}" stroke="{GOLD}" stroke-width="5" transform="rotate(-6 {x} {y})"/>'
                     f'<text x="{x}" y="{y + 18}" font-family="{FONT}" font-size="52" font-weight="700" fill="#fff" text-anchor="middle">{num}</text>')
        _ = anchor

    b = f'''<defs><pattern id="dots" width="28" height="28" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="2" fill="#c9a77a" opacity="0.35"/></pattern></defs>
<rect width="{w}" height="{h}" fill="#f1dfbd"/><rect width="{w}" height="{h}" fill="url(#dots)"/>
<clipPath id="inner"><rect x="34" y="34" width="{w - 68}" height="{h - 68}"/></clipPath>
<rect x="18" y="18" width="{w - 36}" height="{h - 36}" fill="none" stroke="{WOOD}" stroke-width="6"/>
<g clip-path="url(#inner)">
<rect x="34" y="34" width="{w - 68}" height="{h - 68}" fill="none" stroke="{WOOD}" stroke-width="2"/>
<!-- 洪泽湖（示意） -->
<path d="M40,300 Q140,260 190,340 Q230,430 150,480 Q60,520 40,460 Z" fill="{LIGHT_TEAL}" opacity="0.7"/>
<text x="110" y="400" font-family="{FONT}" font-size="34" fill="{TEAL}" text-anchor="middle">洪泽湖</text>
<!-- 运河（示意） -->
<path d="M{w},1500 C820,1300 980,1120 860,960 S560,760 620,560 S900,300 {w - 60},40" fill="none" stroke="{LIGHT_TEAL}" stroke-width="54" opacity="0.65"/>
<text x="905" y="1200" font-family="{FONT}" font-size="34" fill="{TEAL}" transform="rotate(-62 905 1200)">大运河</text>
</g>
{cloud(160, 140, 0.6, "#fff", 0.8)}{cloud(860, 1440, 0.5, "#fff", 0.7)}
<!-- 路线 -->
<path d="{route}" fill="none" stroke="{WOOD}" stroke-width="10" stroke-dasharray="4 22" stroke-linecap="round"/>
{stop_svg}
<!-- 起点 -->
<circle cx="{start[0]}" cy="{start[1]}" r="44" fill="{TEAL}" stroke="#fff" stroke-width="6"/>
<text x="{start[0]}" y="{start[1] + 13}" font-family="{FONT}" font-size="38" font-weight="700" fill="#fff" text-anchor="middle">出发</text>
<!-- 终点：印记挑战 -->
<circle cx="{end[0]}" cy="{end[1]}" r="74" fill="{GOLD}" stroke="{RED}" stroke-width="8"/>
<rect x="{end[0] - 46}" y="{end[1] - 46}" width="92" height="92" rx="10" fill="{RED}"/>
{seal_text(end[0], end[1], 38, "淮安印记")}
<rect x="{end[0] - 120}" y="{end[1] + 88}" width="240" height="66" rx="33" fill="{PAPER}" stroke="{WOOD}" stroke-width="3"/>
<text x="{end[0]}" y="{end[1] + 131}" font-family="{FONT}" font-size="42" font-weight="700" fill="{RED}" text-anchor="middle">印记挑战</text>
<!-- 指北针 -->
<g transform="translate(900,150)"><circle r="54" fill="{PAPER}" stroke="{WOOD}" stroke-width="4"/>
<path d="M0,-44 L12,0 L0,44 L-12,0 Z" fill="{WOOD}"/><path d="M0,-44 L12,0 L-12,0 Z" fill="{RED}"/>
<text x="0" y="-60" font-family="{FONT}" font-size="26" font-weight="700" fill="{WOOD}" text-anchor="middle">北</text></g>
'''
    save("map.svg", svg(w, h, b))


# ── 7. Logo（印章）512×512，透明背景 ────────────────────────────────────────
def logo():
    b = f'''<rect x="16" y="16" width="480" height="480" rx="64" fill="{RED}"/>
<rect x="44" y="44" width="424" height="424" rx="40" fill="none" stroke="#f6e7c8" stroke-width="10"/>
{seal_text(256, 256, 176, "淮安印记", "#f6e7c8")}'''
    save("logo.svg", svg(512, 512, b))


# ── 8. 称号徽章 512×512，透明背景（三个等级，配色不同）──────────────────────
BADGES = [
    ("badge-1.svg", "初识淮安", "#b08a5a", "#d9c09a", "#7a5a3a"),   # 铜
    ("badge-2.svg", "淮安行家", "#a9b2b8", "#dfe5e8", "#5f6b73"),   # 银
    ("badge-3.svg", "文旅达人", GOLD, "#f1cf6e", DEEP_RED),        # 金
]


def badge(name, chars, ring, ring_light, ribbon):
    teeth = ""
    for i in range(36):
        a = math.radians(i * 10)
        teeth += f'<circle cx="{256 + 228 * math.cos(a)}" cy="{256 + 228 * math.sin(a)}" r="22" fill="{ring}"/>'
    b = f'''{teeth}
<circle cx="256" cy="256" r="226" fill="{ring}"/>
<circle cx="256" cy="256" r="200" fill="{ring_light}"/>
<circle cx="256" cy="256" r="186" fill="{RED}"/>
<circle cx="256" cy="256" r="170" fill="none" stroke="#f6e7c8" stroke-width="5" stroke-dasharray="14 9"/>
<rect x="146" y="120" width="220" height="220" rx="22" fill="#f6e7c8"/>
{seal_text(256, 230, 96, chars, RED)}
<path d="M120,360 Q256,410 392,360 L380,420 Q256,460 132,420 Z" fill="{ribbon}"/>
<text x="256" y="416" font-family="{FONT}" font-size="40" font-weight="700" fill="{ring_light}" text-anchor="middle" letter-spacing="10">淮安</text>
'''
    save(name, svg(512, 512, b))


if __name__ == "__main__":
    intro_bg()
    zone01()
    zone02()
    zone03()
    zone04()
    journey_map()
    logo()
    for args in BADGES:
        badge(*args)
    print("SVG 已生成到", OUT)
