// ─── 答题引擎：出题、计分、转场 ──────────────────────────────────────────────
// 每道题的时间线：
//   0 秒   — 点选答案，播放反馈（弹跳/抖动、彩纸、音效）
//   0.5 秒 — 解析弹窗从顶部滑下
//   4 秒   — 题目淡出，下一题在弹窗下方滑入
//   5 秒   — 弹窗自动收起

const GameEngine = {
    currentQuestion: null,
    score: 0,
    isProcessing: false,
    _popupTimer: null,
    _audioPaths: null,
    _audioPool: {},   // pre-created Audio elements keyed by name

    init(config) {
        this.config = config;
        this.score = 0;
        this.currentQuestionIndex = 0;
        this.isProcessing = false;
        // Cache audio paths (nested under project.global_audio in YAML)
        this._audioPaths = config.project?.global_audio || {};
        // Pre-create & unlock Audio objects so they work outside user-gesture
        this._audioPool = {};
        for (const [key, src] of Object.entries(this._audioPaths)) {
            if (src) {
                const a = new Audio(src);
                a.preload = 'auto';
                a.volume = 1;
                // "Unlock" on iOS/Android: play a silent blip from user gesture context
                a.play().then(() => a.pause()).catch(() => {});
                a.currentTime = 0;
                this._audioPool[key] = a;
            }
        }
    },

    startQuiz() {
        if (!this.config || !this.config.quiz_game) return;
        Screens.quiz.classList.add('active');
        this.loadQuestion(0);
    },

    // ── Render a question into the DOM ────────────────────────────────────────
    loadQuestion(index) {
        const questions = this.config.quiz_game.questions;
        if (index >= questions.length) { this.endQuiz(); return; }

        const q = questions[index];
        this.currentQuestion = q;
        this.currentQuestionIndex = index;
        this.isProcessing = false;

        document.getElementById('ui-quiz-question').textContent = q.question;

        const box = document.getElementById('ui-quiz-options');
        box.innerHTML = '';
        q.options.forEach((opt, idx) => {
            const btn = document.createElement('button');
            btn.className = 'btn-option';
            btn.textContent = opt;
            btn.addEventListener('click', () => this.handleAnswer(idx, btn));
            box.appendChild(btn);
        });

        // Progress bar
        const pct = ((index + 1) / questions.length) * 100;
        document.getElementById('ui-quiz-progress').style.width = pct + '%';
    },

    // ── User taps an answer ───────────────────────────────────────────────────
    handleAnswer(selectedIndex, btnEl) {
        if (this.isProcessing) return;
        this.isProcessing = true;

        const q    = this.currentQuestion;
        const ok   = selectedIndex === q.correct_index;
        const opts = document.getElementById('ui-quiz-options');
        const btns = opts.querySelectorAll('.btn-option');

        // Lock all buttons
        btns.forEach(b => (b.disabled = true));

        // ── Immediate feedback ────────────────────────────────────────────────
        if (ok) {
            this.score++;
            btnEl.classList.add('correct');
            this.playAudio('correct_sfx');
            this.createConfetti();
        } else {
            btnEl.classList.add('incorrect');
            this.playAudio('incorrect_sfx');
            if (navigator.vibrate) navigator.vibrate(200);
            // Reveal correct answer after a beat
            setTimeout(() => btns[q.correct_index].classList.add('correct'), 400);
        }

        // ── t ≈ 0.5 s → popup slides down ───────────────────────────────────────
        setTimeout(() => this.showPopup(ok), 500);

        // ── 约 4 秒 → 在弹窗下方换下一题（中文解析留足阅读时间）────────────
        setTimeout(() => this.swapQuestion(), 4000);

        // ── 约 5 秒 → 弹窗收起 ────────────────────────────────────────────────
        if (this._popupTimer) clearTimeout(this._popupTimer);
        this._popupTimer = setTimeout(() => this.hidePopup(), 5000);
    },

    // ── Popup (slides from top of viewport) ──────────────────────────────────
    showPopup(isCorrect) {
        const popup = document.getElementById('quiz-popup');
        const title = document.getElementById('ui-popup-title');
        const msg   = document.getElementById('ui-popup-message');
        const expl  = document.getElementById('ui-popup-explanation');

        title.textContent = isCorrect ? '答对啦！' : '差一点！';
        msg.textContent   = isCorrect
            ? this.currentQuestion.success_message
            : this.currentQuestion.error_message;
        expl.textContent  = this.currentQuestion.explanation || '';

        if (isCorrect) this.playAudio('chime_sfx');

        // Reset to hidden state, force reflow, then animate in
        popup.className = 'quiz-popup ' + (isCorrect ? 'correct' : 'incorrect');
        void popup.offsetHeight;   // ← commit hidden position
        popup.classList.add('show');
    },

    hidePopup() {
        document.getElementById('quiz-popup').classList.remove('show');
    },

    // ── Swap question with fade-out → slide-in ───────────────────────────────
    swapQuestion() {
        const main  = document.querySelector('.quiz-main');
        const next  = this.currentQuestionIndex + 1;

        main.classList.add('fade-out');

        setTimeout(() => {
            main.classList.remove('fade-out');

            if (next >= this.config.quiz_game.questions.length) {
                this.hidePopup();
                this.endQuiz();
                return;
            }

            this.loadQuestion(next);
            main.classList.add('slide-in');
            setTimeout(() => main.classList.remove('slide-in'), 400);
        }, 400);
    },

    // ── Audio helper ─────────────────────────────────────────────────────────
    playAudio(key) {
        try {
            if (isMuted) return;
            const a = this._audioPool[key];
            if (!a) return;
            a.currentTime = 0;
            a.play().catch(() => {});
        } catch (e) { /* never crash */ }
    },

    // ── Confetti ─────────────────────────────────────────────────────────────
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

    // ── End quiz ─────────────────────────────────────────────────────────────
    endQuiz() {
        this.hidePopup();

        // Step 1: Quiz slides back DOWN to bottom (~0.5s)
        Screens.quiz.classList.remove('active');            // triggers CSS translateY(100%)

        setTimeout(() => {
            // Step 2: Prep end screen content while quiz is sliding down
            this.renderEndScreen();

            // Step 3: End screen slides UP from bottom (~1s per flow.md)
            Screens.end.classList.add('active');

            // Step 4: Badge animation after end screen has mostly arrived
            setTimeout(() => this.runBadgeAnimation(), 800);
        }, 600);
    },

    // ── 结束页 ─────────────────────────────────────────────────────────────────
    renderEndScreen() {
        const es = this.config.endscreen;
        const total = this.config.quiz_game.questions.length;
        const scoreTpl = es.score_template || '答对 {score} / {total} 题';

        document.getElementById('ui-end-title').textContent   = es.title;
        document.getElementById('ui-end-message').textContent = es.message;
        document.getElementById('ui-end-score').textContent   =
            scoreTpl.replace('{score}', this.score).replace('{total}', total);

        const btnShare     = document.getElementById('btn-share');
        const btnReplay    = document.getElementById('btn-replay');
        const shareLabelEl = document.getElementById('btn-share-text');
        if (shareLabelEl) shareLabelEl.textContent = es.share_button;
        btnReplay.textContent = es.replay_button;

        // 分享：优先调起系统分享面板；不支持时复制「文案 + 链接」，方便粘贴到微信
        const shareUrl = location.href.split('#')[0];
        const shareMsg = es.share_text || es.title;
        const copied   = es.share_copied_toast || '链接已复制！';

        btnShare.onclick = () => {
            if (navigator.share) {
                navigator.share({ title: es.title, text: shareMsg, url: shareUrl })
                    .catch(err => { if (err && err.name !== 'AbortError') this.copyText(shareMsg + ' ' + shareUrl, copied); });
            } else {
                this.copyText(shareMsg + ' ' + shareUrl, copied);
            }
        };

        btnReplay.onclick = () => location.reload();

        this.renderPolaroids();

        // 徽章图片：左右两半拼合后变成完整徽章
        const badgeSrc = es.badge_image || 'assets/icons/badge.png';
        const makeImg = () => { const i = new Image(); i.src = badgeSrc; i.alt = ''; return i; };

        document.getElementById('badge-left').innerHTML  = '';
        document.getElementById('badge-right').innerHTML = '';
        document.getElementById('badge-full').innerHTML  = '';
        document.getElementById('badge-left').appendChild(makeImg());
        document.getElementById('badge-right').appendChild(makeImg());
        document.getElementById('badge-full').appendChild(makeImg());
    },

    // 复制到剪贴板；不支持 Clipboard API 的浏览器（如部分内置浏览器）用 execCommand 兜底
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

    renderPolaroids() {
        const cluster = document.getElementById('ui-polaroid-cluster');
        if (!cluster || !this.config.endscreen?.polaroids) return;

        cluster.innerHTML = '';
        this.config.endscreen.polaroids.forEach(p => {
            const div = document.createElement('div');
            div.className = `polaroid p-${p.position}`;
            div.style.setProperty('--rot', p.rotation);
            div.style.setProperty('--delay', p.delay);

            const img = document.createElement('img');
            img.src = p.image;
            img.alt = p.label;
            const label = document.createElement('span');
            label.className = 'polaroid-label';
            label.textContent = p.label;
            div.append(img, label);
            cluster.appendChild(div);
        });
    },

    // ── Badge assembly sequence ───────────────────────────────────────────────
    runBadgeAnimation() {
        const left   = document.getElementById('badge-left');
        const right  = document.getElementById('badge-right');
        const full   = document.getElementById('badge-full');
        const glow   = document.getElementById('badge-glow');
        const wreath = document.querySelector('.wreath-bg');

        // 第 0 步：背景光环转入
        if (wreath) wreath.classList.add('animate');

        // 第 1 步：两半徽章从两侧飞入
        left.classList.add('animate');
        right.classList.add('animate');

        // 第 2 步：合体 → 发光 + 完整徽章弹出
        setTimeout(() => {
            glow.classList.add('animate');
            left.style.opacity = '0';
            right.style.opacity = '0';
            full.classList.add('animate');
            this.playAudio('chime_sfx');
            this.createConfetti();
        }, 650);

        // 第 3 步：拍立得照片依次落下
        document.querySelectorAll('.polaroid').forEach(p => p.classList.add('animate'));
    },

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
    }
};
