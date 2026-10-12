// js/games/tangbao.js —— 淮扬美食：「吃汤包」
// 按口诀分四步：轻轻提（按住控制力度）→ 慢慢移（拖动不能太快）
//               → 先开窗（选对动作）→ 后喝汤（吸一口、吹一吹，别烫着）

window.MiniGames = window.MiniGames || {};

MiniGames.tangbao = {
    create(stage, cfg, api) {
        const STEPS = ['轻轻提', '慢慢移', '先开窗', '后喝汤'];
        let step = -1;
        let mistakes = 0;
        let alive = true;
        const timers = [];
        const later = (fn, ms) => { const t = setTimeout(() => alive && fn(), ms); timers.push(t); return t; };

        stage.innerHTML = `
            <div class="tb-wrap">
                <ol class="tb-steps" id="tb-steps">${STEPS.map(s => `<li>${s}</li>`).join('')}</ol>
                <div class="tb-scene" id="tb-scene">
                    <div class="tb-steamer"></div>
                    <div class="tb-spoon"></div>
                    <div class="tb-bun" id="tb-bun">
                        <svg viewBox="0 0 120 100" aria-hidden="true">
                            <defs><radialGradient id="tbg" cx="0.42" cy="0.35" r="0.7">
                                <stop offset="0" stop-color="#fffdf6"/><stop offset="0.7" stop-color="#f6ead2"/><stop offset="1" stop-color="#e2cfa8"/>
                            </radialGradient></defs>
                            <path class="tb-skin" d="M10 70 Q8 34 60 26 Q112 34 110 70 Q108 92 60 94 Q12 92 10 70 Z" fill="url(#tbg)" stroke="#e2cfa8" stroke-width="2"/>
                            <g stroke="#e6d6b4" stroke-width="2.5" fill="none" stroke-linecap="round">
                                <path d="M60 30 L36 58"/><path d="M60 30 L48 60"/><path d="M60 30 L60 62"/><path d="M60 30 L72 60"/><path d="M60 30 L84 58"/>
                            </g>
                            <circle cx="60" cy="30" r="6" fill="#f3e6cc" stroke="#e6d6b4" stroke-width="2"/>
                            <ellipse class="tb-hole" cx="60" cy="31" rx="7" ry="4" fill="#c9a06a" opacity="0"/>
                            <rect class="tb-straw" x="56" y="-10" width="8" height="44" rx="3" fill="#9e2b25" opacity="0"/>
                        </svg>
                        <div class="tb-steam"></div>
                    </div>
                    <p class="tb-msg" id="tb-msg"></p>
                </div>
                <div class="tb-panel" id="tb-panel"></div>
            </div>`;

        const bun   = stage.querySelector('#tb-bun');
        const panel = stage.querySelector('#tb-panel');
        const msg   = stage.querySelector('#tb-msg');
        const stepEls = stage.querySelectorAll('#tb-steps li');

        function say(text, kind = '') {
            msg.textContent = text;
            msg.className = 'tb-msg show ' + kind;
        }

        function oops(text) {
            mistakes++;
            SFX.bad();
            if (navigator.vibrate) navigator.vibrate(150);
            say(text, 'bad');
            bun.classList.remove('wobble');
            void bun.offsetWidth;
            bun.classList.add('wobble');
            hud();
        }

        function hud() {
            api.setHud(`第 ${Math.max(1, step + 1)}/4 步 · 失误 ${mistakes}`);
        }

        function goStep(i) {
            step = i;
            stepEls.forEach((el, k) => {
                el.classList.toggle('active', k === i);
                el.classList.toggle('done', k < i);
            });
            hud();
            [stepLift, stepMove, stepWindow, stepSip][i]();
        }

        // 一个可以“按住”的按钮，返回 { el }
        function holdButton(label, onDown, onUp) {
            const b = document.createElement('button');
            b.className = 'btn tb-hold';
            b.textContent = label;
            let held = false;
            const down = e => { e.preventDefault(); if (held) return; held = true; b.classList.add('held'); onDown(); };
            const up = () => { if (!held) return; held = false; b.classList.remove('held'); onUp(); };
            b.addEventListener('pointerdown', down);
            b.addEventListener('pointerup', up);
            b.addEventListener('pointerleave', up);
            b.addEventListener('pointercancel', up);
            b.addEventListener('keydown', e => { if (e.key === ' ' || e.key === 'Enter') down(e); });
            b.addEventListener('keyup', e => { if (e.key === ' ' || e.key === 'Enter') up(); });
            return b;
        }

        function meter(label, zone) {
            const wrap = document.createElement('div');
            wrap.className = 'tb-meter';
            wrap.innerHTML = `<span>${label}</span><div class="tb-bar">${zone ? `<i class="tb-zone" style="left:${zone[0]}%;width:${zone[1] - zone[0]}%"></i>` : ''}<b></b></div>`;
            const fill = wrap.querySelector('b');
            return { el: wrap, set: v => { fill.style.width = Math.max(0, Math.min(100, v)) + '%'; } };
        }

        // ── 第 1 步：轻轻提 ──────────────────────────────────────────────────
        function stepLift() {
            say('按住按钮把汤包提起来，力度停在绿色区域就松手。');
            panel.innerHTML = '';
            const ZONE = [45, 75];
            const m = meter('力度', ZONE);
            let v = 0, iv = 0;
            const btn = holdButton('按住 · 提起', () => {
                v = 0;
                iv = setInterval(() => {
                    v += 2.2;
                    m.set(v);
                    bun.style.setProperty('--lift', Math.min(v, 100) * 0.35 + 'px');
                    bun.style.setProperty('--stretch', 1 + Math.min(v, 100) / 400);
                    if (v >= 100) {
                        clearInterval(iv);
                        btn.disabled = true;
                        oops('用力太猛，汤包皮破了！换一个重新来。');
                        later(() => { bun.style.setProperty('--lift', '0px'); bun.style.setProperty('--stretch', 1); m.set(0); btn.disabled = false; }, 900);
                    }
                }, 30);
                timers.push(iv);
            }, () => {
                clearInterval(iv);
                if (btn.disabled) return;
                if (v >= ZONE[0] && v <= ZONE[1]) {
                    SFX.good();
                    say('稳稳提起来了！', 'good');
                    btn.disabled = true;
                    later(() => goStep(1), 900);
                } else {
                    say('还没提起来，再按久一点。');
                    bun.style.setProperty('--lift', '0px');
                    bun.style.setProperty('--stretch', 1);
                    m.set(0);
                }
            });
            panel.append(m.el, btn);
        }

        // ── 第 2 步：慢慢移 ──────────────────────────────────────────────────
        function stepMove() {
            bun.style.setProperty('--stretch', 1);
            say('把汤包慢慢拖到右边的汤勺里，太快汤会晃出来。');
            panel.innerHTML = `<div class="tb-track" id="tb-track"><div class="tb-knob" id="tb-knob" role="slider" tabindex="0" aria-label="移动汤包" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"></div><span class="tb-target">汤勺</span></div>`;
            const m = meter('晃动', [0, 70]);
            panel.prepend(m.el);
            const track = panel.querySelector('#tb-track');
            const knob  = panel.querySelector('#tb-knob');
            let dragging = false, pos = 0, lastX = 0, lastT = 0, shake = 0;

            function setPos(p) {
                pos = Math.max(0, Math.min(1, p));
                knob.style.left = (pos * 100) + '%';
                knob.setAttribute('aria-valuenow', Math.round(pos * 100));
                bun.style.setProperty('--move', (pos * 55) + '%');
            }
            function reset() { dragging = false; shake = 0; m.set(0); setPos(0); }

            knob.addEventListener('pointerdown', e => {
                e.preventDefault();
                dragging = true; lastX = e.clientX; lastT = performance.now();
                knob.setPointerCapture(e.pointerId);
            });
            knob.addEventListener('pointermove', e => {
                if (!dragging) return;
                const r = track.getBoundingClientRect();
                const now = performance.now();
                const v = Math.abs(e.clientX - lastX) / Math.max(1, now - lastT);   // 像素/毫秒
                lastX = e.clientX; lastT = now;
                shake = shake * 0.85 + Math.min(100, v * 70) * 0.6;
                m.set(shake);
                bun.classList.toggle('jiggle', shake > 45);
                if (shake > 100) {
                    bun.classList.remove('jiggle');
                    oops('移得太快，汤晃出来了！回到起点慢慢来。');
                    reset();
                    return;
                }
                setPos((e.clientX - r.left) / r.width);
                if (pos >= 0.97) {
                    dragging = false;
                    bun.classList.remove('jiggle');
                    SFX.good();
                    say('稳稳放进汤勺里了！', 'good');
                    later(() => goStep(2), 900);
                }
            });
            knob.addEventListener('pointerup', () => { if (dragging) { dragging = false; m.set(0); shake = 0; } });
            // 键盘：每按一次右方向键前进一点
            knob.addEventListener('keydown', e => {
                if (e.key !== 'ArrowRight') return;
                setPos(pos + 0.08);
                if (pos >= 0.97) { SFX.good(); say('稳稳放进汤勺里了！', 'good'); later(() => goStep(2), 900); }
            });
        }

        // ── 第 3 步：先开窗 ──────────────────────────────────────────────────
        function stepWindow() {
            say('汤包进了汤勺，下一步该怎么做？');
            panel.innerHTML = '';
            const choices = [
                { t: '在顶上轻轻咬个小口', ok: true },
                { t: '一口整个吞下去', ok: false, why: '一口吞下去，滚烫的汤汁把嘴烫坏了！' },
                { t: '马上插吸管吸汤', ok: false, why: '还没散热就吸，汤太烫了！先开个“窗”散散热。' },
            ].sort(() => Math.random() - 0.5);
            const box = document.createElement('div');
            box.className = 'tb-choices';
            choices.forEach(c => {
                const b = document.createElement('button');
                b.className = 'btn-option';
                b.textContent = c.t;
                b.addEventListener('click', () => {
                    if (c.ok) {
                        SFX.good();
                        b.classList.add('correct');
                        box.querySelectorAll('button').forEach(x => { x.disabled = true; });
                        bun.classList.add('opened');
                        say('开了一个小窗，热气冒出来啦！', 'good');
                        later(() => goStep(3), 1100);
                    } else {
                        b.classList.add('incorrect');
                        b.disabled = true;
                        oops(c.why);
                    }
                });
                box.appendChild(b);
            });
            panel.appendChild(box);
        }

        // ── 第 4 步：后喝汤 ──────────────────────────────────────────────────
        function stepSip() {
            bun.classList.add('straw');
            say('按住吸汤，松手吹一吹。别让温度爆表！');
            panel.innerHTML = '';
            const soupM = meter('汤汁');
            const heatM = meter('烫嘴', [0, 80]);
            heatM.el.classList.add('heat');
            panel.append(soupM.el, heatM.el);
            let soup = 100, heat = 20, sipping = false;
            soupM.set(soup); heatM.set(heat);
            const iv = setInterval(() => {
                if (sipping) { soup -= 1.6; heat += 3.2; } else { heat -= 2.6; }
                heat = Math.max(0, heat);
                soupM.set(soup); heatM.set(heat);
                bun.style.setProperty('--soup', Math.max(0, soup) / 100);
                if (heat >= 100) {
                    sipping = false;
                    btn.classList.remove('held');
                    heat = 55;
                    oops('好烫好烫！吸一口要停下来吹一吹。');
                }
                if (soup <= 0) {
                    clearInterval(iv);
                    btn.disabled = true;
                    SFX.good();
                    say('汤喝光了，鲜！', 'good');
                    stepEls.forEach(el => { el.classList.remove('active'); el.classList.add('done'); });
                    later(finish, 1000);
                }
            }, 40);
            timers.push(iv);
            const btn = holdButton('按住 · 吸汤', () => { sipping = true; }, () => { sipping = false; });
            panel.appendChild(btn);
        }

        function finish() {
            const stars = mistakes === 0 ? 3 : mistakes <= 2 ? 2 : 1;
            api.finish({
                stars,
                score: Math.max(60, 300 - mistakes * 60),
                title: stars === 3 ? '吃得优雅又地道，老淮安都夸你！' : '汤包吃完啦！',
                detail: `失误 ${mistakes} 次。口诀记住了吗？轻轻提，慢慢移，先开窗，后喝汤。`,
            });
        }

        hud();
        return {
            start() { goStep(0); },
            destroy() { alive = false; timers.forEach(t => { clearTimeout(t); clearInterval(t); }); },
        };
    },
};
