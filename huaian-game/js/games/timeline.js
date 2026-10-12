// js/games/timeline.js —— 周恩来故里：「少年志向」时间线排序
// 卡片打乱后排列，玩家按时间先后依次点选；点对的卡片落到上方的时间轴上。

window.MiniGames = window.MiniGames || {};

MiniGames.timeline = {
    create(stage, cfg, api) {
        const events = (cfg.events || []).map((e, i) => ({ ...e, order: i }));
        let next = 0;
        let mistakes = 0;
        let startTime = 0;
        let timer = null;
        let done = false;

        stage.innerHTML = `
            <div class="tl-wrap">
                <ol class="tl-axis" id="tl-axis"></ol>
                <p class="tl-tip">按时间先后，依次点下面的卡片</p>
                <div class="tl-cards" id="tl-cards"></div>
            </div>`;
        const axis  = stage.querySelector('#tl-axis');
        const cards = stage.querySelector('#tl-cards');

        // 时间轴上的空位
        events.forEach(() => {
            const li = document.createElement('li');
            li.className = 'tl-slot';
            axis.appendChild(li);
        });

        // 打乱顺序；保证不会恰好是正确顺序
        const shuffled = events.slice();
        do {
            for (let i = shuffled.length - 1; i > 0; i--) {
                const j = Math.floor(Math.random() * (i + 1));
                [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
            }
        } while (shuffled.length > 1 && shuffled.every((e, i) => e.order === i));

        shuffled.forEach(ev => {
            const b = document.createElement('button');
            b.className = 'tl-card';
            b.dataset.order = ev.order;
            b.textContent = ev.text;
            b.disabled = true;
            b.addEventListener('click', () => pick(b, ev));
            cards.appendChild(b);
        });

        function hud() {
            const sec = startTime ? Math.floor((Date.now() - startTime) / 1000) : 0;
            api.setHud(`已排 ${next}/${events.length} · 失误 ${mistakes} · ${sec} 秒`);
        }

        function pick(btn, ev) {
            if (done) return;
            if (ev.order === next) {
                SFX.good();
                btn.classList.add('placed');
                btn.disabled = true;
                const slot = axis.children[next];
                slot.innerHTML = `<b>${ev.year}</b><span></span>`;
                slot.querySelector('span').textContent = ev.text;
                slot.classList.add('filled');
                next++;
                hud();
                if (next === events.length) finish();
            } else {
                SFX.bad();
                mistakes++;
                if (navigator.vibrate) navigator.vibrate(120);
                btn.classList.remove('shake');
                void btn.offsetWidth;
                btn.classList.add('shake');
                hud();
            }
        }

        function finish() {
            done = true;
            clearInterval(timer);
            const sec = Math.round((Date.now() - startTime) / 1000);
            const stars = mistakes === 0 ? 3 : mistakes <= 2 ? 2 : 1;
            setTimeout(() => api.finish({
                stars,
                score: Math.max(0, 300 - mistakes * 40 - sec * 2),
                title: stars === 3 ? '一次全对，了不起！' : '排好啦！',
                detail: `用时 ${sec} 秒，失误 ${mistakes} 次。`,
            }), 900);
        }

        return {
            start() {
                startTime = Date.now();
                cards.querySelectorAll('.tl-card').forEach(b => { b.disabled = false; });
                hud();
                timer = setInterval(hud, 1000);
            },
            destroy() { done = true; clearInterval(timer); },
        };
    },
};
