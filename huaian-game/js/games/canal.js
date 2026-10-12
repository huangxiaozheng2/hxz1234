// js/games/canal.js —— 清江浦：「漕船运粮」
// 竖向跑酷：运河向下流动，漕船在三条航道间切换，躲礁石和浮木，收集粮袋。

window.MiniGames = window.MiniGames || {};

// 旧版浏览器没有 roundRect 时，退化成普通矩形
if (window.CanvasRenderingContext2D && !CanvasRenderingContext2D.prototype.roundRect) {
    CanvasRenderingContext2D.prototype.roundRect = function (x, y, w, h) { this.rect(x, y, w, h); };
}

MiniGames.canal = {
    create(stage, cfg, api) {
        const goal = cfg.distance || 900;
        const maxLives = cfg.lives || 3;
        const starAt = cfg.stars || [10, 16];   // 2 星、3 星需要的粮袋数；安全到站即得 1 星

        stage.innerHTML = `<div class="cn-wrap">
            <canvas class="cn-canvas" id="cn-canvas"></canvas>
            <div class="cn-controls">
                <button class="cn-btn" id="cn-left" aria-label="向左">&larr;</button>
                <button class="cn-btn" id="cn-right" aria-label="向右">&rarr;</button>
            </div></div>`;
        const canvas = stage.querySelector('#cn-canvas');
        const ctx = canvas.getContext('2d');
        let W = 0, H = 0, dpr = 1;

        let running = false, raf = 0, last = 0;
        let lane = 1, boatX = 0;          // boatX 为平滑后的横坐标
        let dist = 0, speed = 0;          // 米、米/秒
        let lives = maxLives, grain = 0, hurtUntil = 0;
        let objs = [], spawnIn = 0, scroll = 0;
        let bankItems = [];
        let finished = false;

        function resize() {
            const r = canvas.getBoundingClientRect();
            dpr = Math.min(window.devicePixelRatio || 1, 2);
            W = r.width; H = r.height;
            canvas.width = Math.round(W * dpr);
            canvas.height = Math.round(H * dpr);
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            if (!boatX) boatX = laneX(lane);
        }

        const riverL = () => W * 0.17;
        const riverR = () => W * 0.83;
        const laneX = i => riverL() + (riverR() - riverL()) * (i + 0.5) / 3;
        const boatY = () => H * 0.8;
        const PX_PER_M = () => H / 60;    // 一屏约 60 米

        function move(d) {
            if (!running) return;
            const n = Math.max(0, Math.min(2, lane + d));
            if (n !== lane) { lane = n; SFX.tick(); }
        }

        // 操作：点按钮 / 点屏幕左右半边 / 左右滑动 / 键盘
        stage.querySelector('#cn-left').addEventListener('pointerdown', e => { e.preventDefault(); e.stopPropagation(); move(-1); });
        stage.querySelector('#cn-right').addEventListener('pointerdown', e => { e.preventDefault(); e.stopPropagation(); move(1); });
        let downX = null;
        canvas.addEventListener('pointerdown', e => { downX = e.clientX; });
        canvas.addEventListener('pointerup', e => {
            if (downX === null) return;
            const dx = e.clientX - downX;
            const r = canvas.getBoundingClientRect();
            if (Math.abs(dx) > 30) move(dx > 0 ? 1 : -1);
            else move(e.clientX - r.left < r.width / 2 ? -1 : 1);
            downX = null;
        });
        const onKey = e => {
            if (e.key === 'ArrowLeft') move(-1);
            if (e.key === 'ArrowRight') move(1);
        };
        document.addEventListener('keydown', onKey);
        window.addEventListener('resize', resize);

        function spawn() {
            // 一排最多放两个障碍，保证总有一条路
            const lanes = [0, 1, 2].sort(() => Math.random() - 0.5);
            const nObs = Math.random() < 0.25 + Math.min(0.3, dist / goal * 0.35) ? 2 : 1;
            for (let i = 0; i < nObs; i++) {
                objs.push({ lane: lanes[i], y: -40, kind: Math.random() < 0.5 ? 'rock' : 'log' });
            }
            if (Math.random() < 0.75) {
                objs.push({ lane: lanes[2], y: -40 - Math.random() * 60, kind: 'grain' });
            }
        }

        function hud() {
            api.setHud(`粮袋 ${grain} · ${'♥'.repeat(lives)}${'♡'.repeat(maxLives - lives)} · ${Math.min(goal, Math.floor(dist))}/${goal} 米`);
        }

        function update(dt) {
            speed = 18 + Math.min(1, dist / goal) * 10;      // 越开越快
            const dy = speed * dt * PX_PER_M();
            dist += speed * dt;
            scroll += dy;

            spawnIn -= dt;
            if (spawnIn <= 0 && dist < goal - 40) {
                spawn();
                spawnIn = Math.max(0.75, 1.2 - dist / goal * 0.45);
            }

            boatX += (laneX(lane) - boatX) * Math.min(1, dt * 14);

            const by = boatY();
            const now = performance.now();
            objs.forEach(o => {
                o.y += dy;
                if (o.done) return;
                const close = Math.abs(o.y - by) < 34 && Math.abs(laneX(o.lane) - boatX) < (riverR() - riverL()) / 6;
                if (!close) return;
                if (o.kind === 'grain') {
                    o.done = true; grain++; SFX.collect();
                } else if (now > hurtUntil) {
                    o.done = true; lives--; hurtUntil = now + 1200;
                    SFX.crash();
                    if (navigator.vibrate) navigator.vibrate(200);
                }
            });
            objs = objs.filter(o => o.y < H + 60 && !(o.done && o.kind === 'grain'));

            // 岸边装饰（柳树、房子）
            bankItems.forEach(b => { b.y += dy; });
            bankItems = bankItems.filter(b => b.y < H + 80);
            while (bankItems.length < 10) {
                const minY = bankItems.length ? Math.min(...bankItems.map(b => b.y)) : H;
                bankItems.push({ y: minY - 50 - Math.random() * 60, side: Math.random() < 0.5 ? 0 : 1, kind: Math.random() < 0.6 ? 'tree' : 'house' });
            }

            hud();
            if (lives <= 0) return end(false);
            if (dist >= goal) return end(true);
        }

        function drawBoat(x, y, blink) {
            if (blink) ctx.globalAlpha = 0.4;
            ctx.save();
            ctx.translate(x, y);
            ctx.fillStyle = 'rgba(0,0,0,0.18)';
            ctx.beginPath(); ctx.ellipse(3, 6, 20, 38, 0, 0, Math.PI * 2); ctx.fill();
            ctx.fillStyle = '#6b3a22';
            ctx.beginPath();
            ctx.moveTo(0, -42); ctx.quadraticCurveTo(22, -16, 18, 30); ctx.lineTo(-18, 30); ctx.quadraticCurveTo(-22, -16, 0, -42);
            ctx.fill();
            ctx.fillStyle = '#3d2a1c';
            ctx.fillRect(-11, 4, 22, 20);
            ctx.fillStyle = '#9e2b25';
            ctx.fillRect(-16, -14, 32, 8);
            ctx.fillStyle = '#d4a73a';
            ctx.beginPath(); ctx.arc(0, -10, 3.5, 0, Math.PI * 2); ctx.fill();
            ctx.restore();
            ctx.globalAlpha = 1;
        }

        function drawObj(o) {
            const x = laneX(o.lane), y = o.y;
            if (o.kind === 'rock') {
                ctx.fillStyle = '#6f6a64';
                ctx.beginPath();
                ctx.moveTo(x - 24, y + 14); ctx.lineTo(x - 18, y - 10); ctx.lineTo(x - 2, y - 20);
                ctx.lineTo(x + 18, y - 12); ctx.lineTo(x + 24, y + 12); ctx.closePath(); ctx.fill();
                ctx.fillStyle = '#8f8a82';
                ctx.beginPath(); ctx.moveTo(x - 14, y - 6); ctx.lineTo(x - 2, y - 15); ctx.lineTo(x + 10, y - 8); ctx.closePath(); ctx.fill();
                ctx.strokeStyle = 'rgba(255,255,255,0.5)'; ctx.lineWidth = 2;
                ctx.beginPath(); ctx.arc(x, y + 14, 26, 0.2, Math.PI - 0.2); ctx.stroke();
            } else if (o.kind === 'log') {
                ctx.fillStyle = '#7a4a2a';
                ctx.beginPath(); ctx.roundRect(x - 30, y - 9, 60, 18, 9); ctx.fill();
                ctx.fillStyle = '#c99a6a';
                ctx.beginPath(); ctx.ellipse(x + 26, y, 5, 8, 0, 0, Math.PI * 2); ctx.fill();
                ctx.strokeStyle = '#5a3420'; ctx.lineWidth = 2;
                ctx.beginPath(); ctx.moveTo(x - 20, y - 3); ctx.lineTo(x + 10, y - 3); ctx.stroke();
            } else {
                const bob = Math.sin((performance.now() / 200) + o.lane) * 2;
                ctx.fillStyle = '#e8c27a';
                ctx.beginPath(); ctx.roundRect(x - 15, y - 14 + bob, 30, 30, 8); ctx.fill();
                ctx.fillStyle = '#b8863a';
                ctx.fillRect(x - 6, y - 19 + bob, 12, 7);
                ctx.fillStyle = '#7a2421';
                ctx.font = 'bold 16px "PingFang SC","Microsoft YaHei",sans-serif';
                ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
                ctx.fillText('粮', x, y + 2 + bob);
            }
        }

        function drawBank(b) {
            const x = b.side === 0 ? riverL() * 0.45 : W - riverL() * 0.45;
            if (b.kind === 'tree') {
                ctx.fillStyle = '#5b4630'; ctx.fillRect(x - 2, b.y, 4, 14);
                ctx.fillStyle = '#6e9a4a';
                ctx.beginPath(); ctx.arc(x, b.y - 4, 14, 0, Math.PI * 2); ctx.fill();
                ctx.fillStyle = '#8fbf5e';
                ctx.beginPath(); ctx.arc(x - 4, b.y - 8, 7, 0, Math.PI * 2); ctx.fill();
            } else {
                ctx.fillStyle = '#f4efe6'; ctx.fillRect(x - 13, b.y - 10, 26, 22);
                ctx.fillStyle = '#4a4f57'; ctx.fillRect(x - 16, b.y - 16, 32, 8);
                ctx.fillStyle = '#5a3422'; ctx.fillRect(x - 4, b.y + 2, 8, 10);
            }
        }

        function draw() {
            // 两岸
            ctx.fillStyle = '#9db58a'; ctx.fillRect(0, 0, W, H);
            bankItems.forEach(drawBank);
            // 石砌堤岸
            ctx.fillStyle = '#b9ad98';
            ctx.fillRect(riverL() - 10, 0, 10, H); ctx.fillRect(riverR(), 0, 10, H);
            // 河面
            const g = ctx.createLinearGradient(0, 0, 0, H);
            g.addColorStop(0, '#5f9c9a'); g.addColorStop(1, '#3f7f86');
            ctx.fillStyle = g; ctx.fillRect(riverL(), 0, riverR() - riverL(), H);
            // 水波纹（随水流向下）
            ctx.strokeStyle = 'rgba(255,255,255,0.28)'; ctx.lineWidth = 2;
            for (let i = 0; i < 14; i++) {
                const yy = ((i * 73 + scroll * 0.9) % (H + 40)) - 20;
                const xx = riverL() + ((i * 97) % (riverR() - riverL() - 40)) + 10;
                ctx.beginPath(); ctx.moveTo(xx, yy); ctx.lineTo(xx + 26, yy); ctx.stroke();
            }
            // 航道分隔虚线
            ctx.setLineDash([10, 18]); ctx.strokeStyle = 'rgba(255,255,255,0.18)';
            for (let i = 1; i < 3; i++) {
                const x = riverL() + (riverR() - riverL()) * i / 3;
                ctx.lineDashOffset = -scroll;
                ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
            }
            ctx.setLineDash([]);
            // 终点：清江浦闸口
            const finishY = boatY() - (goal - dist) * PX_PER_M();
            if (finishY > -60) {
                ctx.fillStyle = '#a4806a';
                ctx.fillRect(riverL() - 10, finishY - 14, 22, 28); ctx.fillRect(riverR() - 12, finishY - 14, 22, 28);
                ctx.fillStyle = '#9e2b25';
                ctx.fillRect(riverL(), finishY - 4, riverR() - riverL(), 6);
                ctx.fillStyle = '#fff';
                ctx.font = 'bold 15px "PingFang SC","Microsoft YaHei",sans-serif';
                ctx.textAlign = 'center'; ctx.textBaseline = 'bottom';
                ctx.fillText('清江浦 · 到站', W / 2, finishY - 10);
            }
            objs.forEach(o => { if (!o.done || o.kind !== 'grain') drawObj(o); });
            const blink = performance.now() < hurtUntil && Math.floor(performance.now() / 120) % 2 === 0;
            drawBoat(boatX, boatY(), blink);
        }

        function frame(t) {
            if (!running) return;
            const dt = Math.min(0.05, (t - last) / 1000 || 0);
            last = t;
            update(dt);
            if (running) draw();
            raf = requestAnimationFrame(frame);
        }

        function end(arrived) {
            if (finished) return;
            finished = true;
            running = false;
            cancelAnimationFrame(raf);
            draw();
            const stars = !arrived ? 0 : grain >= starAt[1] ? 3 : grain >= starAt[0] ? 2 : 1;
            api.finish({
                stars,
                score: arrived ? grain * 20 + lives * 30 : grain * 10,
                title: arrived ? (stars === 3 ? '满载而归，漕运总督都要嘉奖你！' : '粮船平安到达清江浦！') : '船撞坏了，没能到站……',
                detail: arrived
                    ? `运到粮袋 ${grain} 袋，剩余 ${lives} 条命。` + (stars < 3 ? `（收集 ${starAt[stars - 1]} 袋可得 ${stars + 1} 星）` : '')
                    : `开了 ${Math.floor(dist)} 米，收集粮袋 ${grain} 袋。再试一次吧！`,
            });
        }

        // 只读状态，供自动化测试驾驶用
        canvas._state = () => ({ lane, objs, boatY: boatY(), running });

        resize();
        bankItems = [];
        draw();
        hud();

        return {
            start() {
                resize();
                running = true;
                last = performance.now();
                raf = requestAnimationFrame(frame);
            },
            destroy() {
                running = false;
                cancelAnimationFrame(raf);
                document.removeEventListener('keydown', onKey);
                window.removeEventListener('resize', resize);
            },
        };
    },
};
