// js/games/whack.js —— 河下古镇：「金箍棒打妖怪」
// 3×3 的老宅窗户里随机冒出妖怪和唐僧。点妖怪得分，点到唐僧扣分。

window.MiniGames = window.MiniGames || {};

MiniGames.whack = (() => {
    // 角色立绘（内联 SVG）
    const ART = {
        demon: `<svg viewBox="0 0 100 100" aria-hidden="true">
            <path d="M22 30 L30 6 L40 28 Z M78 30 L70 6 L60 28 Z" fill="#f2e3c0"/>
            <ellipse cx="50" cy="60" rx="38" ry="36" fill="#5f8f4e"/>
            <ellipse cx="50" cy="70" rx="24" ry="18" fill="#8db57a"/>
            <circle cx="36" cy="52" r="10" fill="#fff"/><circle cx="64" cy="52" r="10" fill="#fff"/>
            <circle cx="38" cy="54" r="5" fill="#2c1508"/><circle cx="62" cy="54" r="5" fill="#2c1508"/>
            <path d="M26 40 L44 46 M74 40 L56 46" stroke="#2c1508" stroke-width="4" stroke-linecap="round"/>
            <path d="M36 74 Q50 84 64 74" stroke="#2c1508" stroke-width="4" fill="none" stroke-linecap="round"/>
            <path d="M40 76 L43 82 L46 77 M54 77 L57 82 L60 76" fill="#fff"/>
        </svg>`,
        demon2: `<svg viewBox="0 0 100 100" aria-hidden="true">
            <path d="M50 4 L58 26 L42 26 Z" fill="#f2e3c0"/>
            <ellipse cx="50" cy="60" rx="38" ry="36" fill="#7a5a9e"/>
            <circle cx="50" cy="50" r="14" fill="#fff"/><circle cx="50" cy="52" r="7" fill="#2c1508"/>
            <path d="M30 76 Q50 66 70 76" stroke="#2c1508" stroke-width="4" fill="none" stroke-linecap="round"/>
            <path d="M14 56 Q4 50 8 40 M86 56 Q96 50 92 40" stroke="#7a5a9e" stroke-width="8" fill="none" stroke-linecap="round"/>
        </svg>`,
        gold: `<svg viewBox="0 0 100 100" aria-hidden="true">
            <path d="M20 32 L26 4 L40 28 Z M80 32 L74 4 L60 28 Z" fill="#9e2b25"/>
            <ellipse cx="50" cy="60" rx="38" ry="36" fill="#d4a73a"/>
            <circle cx="36" cy="52" r="9" fill="#fff"/><circle cx="64" cy="52" r="9" fill="#fff"/>
            <circle cx="36" cy="54" r="4.5" fill="#2c1508"/><circle cx="64" cy="54" r="4.5" fill="#2c1508"/>
            <path d="M34 74 Q50 86 66 74" stroke="#2c1508" stroke-width="4" fill="none" stroke-linecap="round"/>
            <circle cx="20" cy="22" r="4" fill="#fff8d0"/><circle cx="82" cy="18" r="3" fill="#fff8d0"/>
        </svg>`,
        monk: `<svg viewBox="0 0 100 100" aria-hidden="true">
            <path d="M18 100 Q22 70 50 68 Q78 70 82 100 Z" fill="#c8322a"/>
            <path d="M40 70 L50 100 L60 70" fill="#d4a73a"/>
            <circle cx="50" cy="50" r="22" fill="#f6d7b3"/>
            <path d="M24 40 Q50 6 76 40 L70 42 Q50 26 30 42 Z" fill="#d4a73a"/>
            <path d="M30 40 L34 22 M42 34 L44 16 M58 34 L56 16 M70 40 L66 22" stroke="#9e2b25" stroke-width="3"/>
            <path d="M40 52 Q43 49 46 52 M54 52 Q57 49 60 52" stroke="#2c1508" stroke-width="2.5" fill="none" stroke-linecap="round"/>
            <path d="M44 61 Q50 65 56 61" stroke="#2c1508" stroke-width="2.5" fill="none" stroke-linecap="round"/>
        </svg>`,
    };

    return {
        create(stage, cfg, api) {
            const duration = (cfg.duration || 30) * 1000;
            const starAt = cfg.stars || [12, 20, 28];
            let score = 0, hits = 0, monkHits = 0;
            let startTime = 0, raf = 0, spawnTimer = 0, running = false;
            const holes = [];

            stage.innerHTML = `<div class="wh-wrap"><div class="wh-grid" id="wh-grid"></div><p class="wh-tip">点妖怪 +1，金色妖怪 +3，点到唐僧 −3</p></div>`;
            const grid = stage.querySelector('#wh-grid');
            for (let i = 0; i < 9; i++) {
                const cell = document.createElement('div');
                cell.className = 'wh-hole';
                cell.innerHTML = `<div class="wh-eave"></div><div class="wh-window"><button class="wh-char" tabindex="-1" aria-label=""></button></div>`;
                const btn = cell.querySelector('.wh-char');
                const hole = { cell, btn, kind: null, until: 0 };
                btn.addEventListener('pointerdown', e => { e.preventDefault(); whack(hole); });
                grid.appendChild(cell);
                holes.push(hole);
            }

            function hud() {
                const left = Math.max(0, Math.ceil((duration - (Date.now() - startTime)) / 1000));
                api.setHud(`得分 ${score} · 剩 ${left} 秒`);
            }

            function show(hole, kind, ms) {
                hole.kind = kind;
                hole.until = Date.now() + ms;
                hole.btn.innerHTML = ART[kind];
                hole.btn.setAttribute('aria-label', kind === 'monk' ? '唐僧' : '妖怪');
                hole.btn.className = 'wh-char up ' + kind;
                hole.btn.tabIndex = 0;
            }

            function hide(hole) {
                hole.kind = null;
                hole.btn.classList.remove('up');
                hole.btn.tabIndex = -1;
            }

            function whack(hole) {
                if (!running || !hole.kind || hole.btn.classList.contains('hit')) return;
                const kind = hole.kind;
                let pts;
                if (kind === 'monk') {
                    pts = -3; monkHits++;
                    SFX.bad();
                    if (navigator.vibrate) navigator.vibrate(150);
                } else {
                    pts = kind === 'gold' ? 3 : 1; hits++;
                    kind === 'gold' ? SFX.collect() : SFX.hit();
                }
                score = Math.max(0, score + pts);
                const pop = document.createElement('span');
                pop.className = 'wh-pop ' + (pts > 0 ? 'plus' : 'minus');
                pop.textContent = (pts > 0 ? '+' : '') + pts;
                hole.cell.appendChild(pop);
                setTimeout(() => pop.remove(), 700);
                hole.btn.classList.add('hit');
                setTimeout(() => { hole.btn.classList.remove('hit'); hide(hole); }, 220);
                hud();
            }

            function spawn() {
                if (!running) return;
                const elapsed = Date.now() - startTime;
                const progress = elapsed / duration;
                const free = holes.filter(h => !h.kind);
                if (free.length) {
                    const hole = free[Math.floor(Math.random() * free.length)];
                    const r = Math.random();
                    const kind = r < 0.2 ? 'monk' : r < 0.3 ? 'gold' : r < 0.65 ? 'demon' : 'demon2';
                    const stay = (kind === 'gold' ? 650 : 1100) - progress * 350;
                    show(hole, kind, stay);
                }
                // 越到后面冒得越快
                spawnTimer = setTimeout(spawn, 650 - progress * 300 + Math.random() * 200);
            }

            function loop() {
                if (!running) return;
                const now = Date.now();
                holes.forEach(h => { if (h.kind && now > h.until && !h.btn.classList.contains('hit')) hide(h); });
                hud();
                if (now - startTime >= duration) { end(); return; }
                raf = requestAnimationFrame(loop);
            }

            function end() {
                running = false;
                clearTimeout(spawnTimer);
                cancelAnimationFrame(raf);
                holes.forEach(hide);
                const stars = score >= starAt[2] ? 3 : score >= starAt[1] ? 2 : score >= starAt[0] ? 1 : 0;
                api.finish({
                    stars,
                    score: score * 10,
                    title: stars === 3 ? '齐天大圣也要点赞！' : stars > 0 ? '妖怪被打跑啦！' : '妖怪太狡猾了……',
                    detail: `打中妖怪 ${hits} 只，误伤唐僧 ${monkHits} 次，得分 ${score}。` +
                        (stars < 3 ? `（${starAt[stars] ?? starAt[2]} 分可再得一星）` : ''),
                });
            }

            return {
                start() {
                    running = true;
                    startTime = Date.now();
                    spawn();
                    loop();
                },
                destroy() {
                    running = false;
                    clearTimeout(spawnTimer);
                    cancelAnimationFrame(raf);
                },
            };
        },
    };
})();
