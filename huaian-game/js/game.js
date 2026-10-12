// js/game.js —— 印记大挑战：限时答题
// 从题库随机抽题；每题倒计时，答得越快分越高；连续答对有连击加成。
// 每题时间线：点选 → 0.5 秒弹出解析 → 约 3.6 秒换下一题 → 4.6 秒收起解析

const GameEngine = {
    config: null,
    questions: [],
    index: 0,
    score: 0,
    correct: 0,
    combo: 0,
    bestCombo: 0,
    isProcessing: false,
    _timerRaf: 0,
    _deadline: 0,
    _popupTimer: null,
    onFinish: null,

    init(config, onFinish) {
        this.config = config;
        this.onFinish = onFinish;
        const qg = config.quiz_game;
        const pool = qg.questions.slice();
        for (let i = pool.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [pool[i], pool[j]] = [pool[j], pool[i]];
        }
        this.questions = pool.slice(0, qg.questions_per_round || 6);
        this.seconds = qg.seconds_per_question || 15;
        this.index = 0;
        this.score = 0;
        this.correct = 0;
        this.combo = 0;
        this.bestCombo = 0;
        this.isProcessing = false;
    },

    startQuiz() {
        Screens.quiz.classList.add('active');
        this.loadQuestion(0);
    },

    // 选项也打乱，避免每次答案位置一样
    _shuffleOptions(q) {
        const opts = q.options.map((t, i) => ({ t, ok: i === q.correct_index }));
        for (let i = opts.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [opts[i], opts[j]] = [opts[j], opts[i]];
        }
        return opts;
    },

    loadQuestion(index) {
        if (index >= this.questions.length) { this.endQuiz(); return; }
        const q = this.questions[index];
        this.index = index;
        this.isProcessing = false;
        this.current = { q, opts: this._shuffleOptions(q) };

        document.getElementById('ui-quiz-question').textContent = q.question;
        const box = document.getElementById('ui-quiz-options');
        box.innerHTML = '';
        this.current.opts.forEach(opt => {
            const btn = document.createElement('button');
            btn.className = 'btn-option';
            btn.textContent = opt.t;
            btn.addEventListener('click', () => this.handleAnswer(opt.ok, btn));
            box.appendChild(btn);
        });

        document.getElementById('ui-quiz-progress').style.width = ((index + 1) / this.questions.length * 100) + '%';
        this.updateMeta();
        this.startTimer();
    },

    updateMeta() {
        document.getElementById('ui-quiz-count').textContent = `第 ${this.index + 1} / ${this.questions.length} 题`;
        document.getElementById('ui-quiz-score').textContent = `${this.score} 分`;
        const c = document.getElementById('ui-quiz-combo');
        c.textContent = this.combo >= 2 ? `${this.combo} 连击！` : '';
        c.classList.toggle('show', this.combo >= 2);
    },

    startTimer() {
        cancelAnimationFrame(this._timerRaf);
        const total = this.seconds * 1000;
        this._deadline = performance.now() + total;
        const fill = document.getElementById('ui-quiz-timer');
        let lastSec = this.seconds;
        const tick = () => {
            const left = this._deadline - performance.now();
            fill.style.width = Math.max(0, left / total * 100) + '%';
            fill.classList.toggle('urgent', left < 5000);
            const sec = Math.ceil(left / 1000);
            if (sec !== lastSec && sec <= 3 && sec > 0) SFX.tick();
            lastSec = sec;
            if (left <= 0) { this.handleAnswer(false, null); return; }
            if (!this.isProcessing) this._timerRaf = requestAnimationFrame(tick);
        };
        this._timerRaf = requestAnimationFrame(tick);
    },

    handleAnswer(ok, btnEl) {
        if (this.isProcessing) return;
        this.isProcessing = true;
        cancelAnimationFrame(this._timerRaf);

        const timeLeft = Math.max(0, (this._deadline - performance.now()) / 1000);
        const btns = document.querySelectorAll('#ui-quiz-options .btn-option');
        btns.forEach(b => { b.disabled = true; });
        const correctBtn = [...btns][this.current.opts.findIndex(o => o.ok)];

        let gained = 0;
        if (ok) {
            this.correct++;
            this.combo++;
            this.bestCombo = Math.max(this.bestCombo, this.combo);
            const mult = this.combo >= 3 ? 1.5 : this.combo === 2 ? 1.2 : 1;
            gained = Math.round((100 + timeLeft * 10) * mult);
            this.score += gained;
            btnEl.classList.add('correct');
            SFX.play('correct_sfx');
            this.createConfetti();
        } else {
            this.combo = 0;
            if (btnEl) btnEl.classList.add('incorrect');
            SFX.play('incorrect_sfx');
            if (navigator.vibrate) navigator.vibrate(200);
            setTimeout(() => correctBtn && correctBtn.classList.add('correct'), 400);
        }
        this.updateMeta();

        const title = ok ? `答对啦！+${gained}` : btnEl ? '差一点！' : '时间到！';
        const message = ok
            ? (this.combo >= 2 ? `${this.combo} 连击，分数加成中！` : '又找回一枚印记碎片。')
            : `正确答案：${this.current.opts.find(o => o.ok).t}`;
        setTimeout(() => this.showPopup(ok, title, message), 500);
        setTimeout(() => this.swapQuestion(), 3600);
        if (this._popupTimer) clearTimeout(this._popupTimer);
        this._popupTimer = setTimeout(() => this.hidePopup(), 4600);
    },

    showPopup(isCorrect, title, message) {
        const popup = document.getElementById('quiz-popup');
        document.getElementById('ui-popup-title').textContent = title;
        document.getElementById('ui-popup-message').textContent = message;
        document.getElementById('ui-popup-explanation').textContent = this.current.q.explanation || '';
        popup.className = 'quiz-popup ' + (isCorrect ? 'correct' : 'incorrect');
        void popup.offsetHeight;
        popup.classList.add('show');
    },

    hidePopup() {
        document.getElementById('quiz-popup').classList.remove('show');
    },

    swapQuestion() {
        const main = document.querySelector('.quiz-main');
        const next = this.index + 1;
        main.classList.add('fade-out');
        setTimeout(() => {
            main.classList.remove('fade-out');
            if (next >= this.questions.length) {
                this.hidePopup();
                this.endQuiz();
                return;
            }
            this.loadQuestion(next);
            main.classList.add('slide-in');
            setTimeout(() => main.classList.remove('slide-in'), 400);
        }, 400);
    },

    abort() {
        cancelAnimationFrame(this._timerRaf);
        this.isProcessing = true;
        this.hidePopup();
    },

    createConfetti() {
        const colors = ['#d4a73a', '#9e2b25', '#e8807a', '#3f7f86'];
        for (let i = 0; i < 30; i++) {
            const el = document.createElement('div');
            el.className = 'confetti';
            el.style.left = Math.random() * 100 + 'vw';
            el.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
            const dur = 1 + Math.random();
            const del = Math.random() * 0.5;
            el.style.animation = `fall ${dur}s ${del}s linear forwards`;
            document.body.appendChild(el);
            setTimeout(() => el.remove(), (dur + del) * 1000);
        }
    },

    endQuiz() {
        this.hidePopup();
        Screens.quiz.classList.remove('active');
        const result = {
            score: this.score,
            correct: this.correct,
            total: this.questions.length,
            bestCombo: this.bestCombo,
        };
        setTimeout(() => { if (this.onFinish) this.onFinish(result); }, 600);
    },

    // ── 徽章拼合动画 ─────────────────────────────────────────────────────────
    runBadgeAnimation(badgeSrc) {
        const makeImg = () => { const i = new Image(); i.src = badgeSrc; i.alt = ''; return i; };
        const left   = document.getElementById('badge-left');
        const right  = document.getElementById('badge-right');
        const full   = document.getElementById('badge-full');
        const glow   = document.getElementById('badge-glow');
        const wreath = document.querySelector('.wreath-bg');
        [left, right, full].forEach(el => { el.innerHTML = ''; el.appendChild(makeImg()); el.classList.remove('animate'); el.style.opacity = ''; });
        glow.classList.remove('animate');
        if (wreath) wreath.classList.remove('animate');
        void full.offsetWidth;

        if (wreath) wreath.classList.add('animate');
        left.classList.add('animate');
        right.classList.add('animate');
        setTimeout(() => {
            glow.classList.add('animate');
            left.style.opacity = '0';
            right.style.opacity = '0';
            full.classList.add('animate');
            SFX.play('chime_sfx');
            this.createConfetti();
        }, 650);
    },

    // ── 提示条与复制 ─────────────────────────────────────────────────────────
    showToast(msg) {
        let t = document.querySelector('.toast');
        if (!t) {
            t = document.createElement('div');
            t.className = 'toast';
            document.body.appendChild(t);
        }
        t.textContent = msg;
        t.classList.add('show');
        setTimeout(() => t.classList.remove('show'), 2500);
    },

    copyText(text, toastMsg) {
        const done = () => this.showToast(toastMsg);
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(text).then(done).catch(() => this.legacyCopy(text) && done());
        } else if (this.legacyCopy(text)) {
            done();
        }
    },

    legacyCopy(text) {
        try {
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.setAttribute('readonly', '');
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.select();
            const ok = document.execCommand('copy');
            ta.remove();
            return ok;
        } catch (e) {
            return false;
        }
    },
};
