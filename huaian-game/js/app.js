// js/app.js —— 入口与状态机
// 流程：加载 → 首页 → 开场故事 → 地图 → 展区故事 → 挑战 → 答题 → 结束

// ─── 全局状态 ────────────────────────────────────────────────────────────────
const AppState = {
    config: null,        // 解析后的 flow.yaml
    currentZoneIndex: 0  // 当前展区，从 0 开始
};

// ─── 页面切换 ────────────────────────────────────────────────────────────────
const Screens = {
    loading:   document.getElementById('screen-loading'),
    intro:     document.getElementById('screen-intro'),
    prologue:  document.getElementById('screen-prologue'),
    map:       document.getElementById('screen-map'),
    story:     document.getElementById('screen-story'),
    challenge: document.getElementById('screen-challenge'),
    quiz:      document.getElementById('screen-quiz'),
    end:       document.getElementById('screen-endscreen'),

    show(screen) {
        Object.values(this).forEach(s => {
            if (s instanceof HTMLElement) s.classList.remove('active');
        });
        screen.classList.add('active');
    }
};

// ─── 加载页 ──────────────────────────────────────────────────────────────────
function runLoadingScreen() {
    const progressFill = document.querySelector('#screen-loading .progress-fill');
    const errorBox     = document.getElementById('ui-load-error');
    errorBox.classList.remove('visible');
    progressFill.style.width = '0%';
    let progress = 0;

    const tick = setInterval(() => {
        progress += 20;
        progressFill.style.width = progress + '%';

        if (progress >= 100) {
            clearInterval(tick);
            loadConfig().then(() => {
                setTimeout(() => {
                    Screens.show(Screens.intro);
                    applyTheme(AppState.config);
                    renderIntro(AppState.config);
                }, 400);
            }).catch(err => {
                console.error(err);
                errorBox.classList.add('visible');
            });
        }
    }, 300);
}

function bindLoadRetry() {
    const btn = document.getElementById('btn-load-retry');
    if (btn) btn.addEventListener('click', runLoadingScreen);
}

// ─── 读取 flow.yaml ─────────────────────────────────────────────────────────
function loadConfig() {
    return fetch('flow.yaml')
        .then(r => {
            if (!r.ok) throw new Error('无法加载 flow.yaml');
            return r.text();
        })
        .then(text => {
            AppState.config = jsyaml.load(text);
            applyLoadingScreen(AppState.config);
            preloadImages(AppState.config);
        });
}

// ─── 图片预加载 ─────────────────────────────────────────────────────────────
function preloadImages(config) {
    if (!config) return;
    const urls = [];

    if (config.intro_screen && config.intro_screen.background_image)
        urls.push(config.intro_screen.background_image);
    if (config.map_screen && config.map_screen.background_image)
        urls.push(config.map_screen.background_image);

    if (config.zones) {
        config.zones.forEach(zone => {
            if (zone.thumbnail) urls.push(zone.thumbnail);
            if (zone.slides) zone.slides.forEach(slide => { if (slide.image) urls.push(slide.image); });
        });
    }

    if (config.quiz_game && config.quiz_game.challenge_screen && config.quiz_game.challenge_screen.image)
        urls.push(config.quiz_game.challenge_screen.image);
    if (config.endscreen && config.endscreen.badge_image)
        urls.push(config.endscreen.badge_image);

    urls.forEach(url => { const img = new Image(); img.src = url; });
}

// ─── 首页与幕布转场 ──────────────────────────────────────────────────────────
function applyLoadingScreen(config) {
    if (!config) return;
    const ls = config.loading_screen;
    if (!ls) return;
    const logoEl = document.getElementById('ui-loading-logo');
    if (logoEl && ls.logo) logoEl.src = ls.logo;
    const errEl = document.getElementById('ui-load-error-text');
    if (errEl && config.qr_screen && config.qr_screen.error_message)
        errEl.textContent = config.qr_screen.error_message;
}

function applyTheme(config) {
    if (!config || !config.project || !config.project.theme) return;
    const root = document.documentElement;
    const t = config.project.theme;
    if (t.secondary_color) root.style.setProperty('--gold-color',      t.secondary_color);
    if (t.primary_color)   root.style.setProperty('--alternate-color', t.primary_color);
}

function renderIntro(config) {
    if (!config) return;
    const s = config.intro_screen;
    document.getElementById('ui-intro-title').textContent    = s.title || '';
    document.getElementById('ui-intro-subtitle').textContent = s.subtitle || '';
    document.getElementById('ui-intro-text').textContent     = s.intro_text || '';
    document.getElementById('btn-start').textContent         = s.start_button || '开始';

    const bg = s.background_image || 'assets/images/intro-bg.jpg';
    const landing = document.getElementById('intro-landing');
    if (landing) landing.style.backgroundImage = 'url(' + bg + ')';
}

function bindCurtainTransition() {
    const btnStart = document.getElementById('btn-start');
    btnStart.addEventListener('click', () => {
        // 在用户点击时解锁语音朗读（iOS 要求必须由用户操作触发）
        Narrator.unlock();

        // 1. 合上幕布
        Screens.intro.classList.add('closing');

        // 2. 幕布合上后，在下面准备好开场故事
        setTimeout(() => {
            const sharedBg = document.getElementById('prologue-map-bg');
            if (sharedBg) sharedBg.classList.add('active');

            Screens.prologue.classList.add('active');

            // 3. 拉开幕布
            Screens.intro.classList.remove('closing');
            Screens.intro.classList.add('open');

            // 4. 清理首页，开始讲故事
            setTimeout(() => {
                Screens.intro.classList.remove('active');
                const config = AppState.config;
                if (config && config.prologue_screen) {
                    if (config.prologue_screen.ambient_audio) {
                        startAmbient(config.prologue_screen.ambient_audio);
                    }
                    runPrologueAnimation(config);
                } else {
                    renderStory(config, 0);
                    Screens.show(Screens.story);
                }
            }, 1000);
        }, 1000);
    });
}

// ─── 开场故事 ────────────────────────────────────────────────────────────────
let prologueTimers = [];
let ambientAudio   = null;
let ambientFadeInt = null;

function startAmbient(src) {
    if (!src || isMuted) return;
    try {
        ambientAudio        = new Audio(src);
        ambientAudio.loop   = true;
        ambientAudio.volume = 0;
        ambientAudio.play().catch(() => {});
        let vol = 0;
        clearInterval(ambientFadeInt);
        ambientFadeInt = setInterval(() => {
            vol = Math.min(vol + 0.02, 0.35);
            if (ambientAudio) ambientAudio.volume = vol;
            if (vol >= 0.35) clearInterval(ambientFadeInt);
        }, 150);
    } catch (e) { /* 没有音频文件就跳过 */ }
}

function stopAmbient(callback) {
    clearInterval(ambientFadeInt);
    if (!ambientAudio) { if (callback) callback(); return; }
    let vol = ambientAudio.volume;
    ambientFadeInt = setInterval(() => {
        vol = Math.max(vol - 0.03, 0);
        if (ambientAudio) ambientAudio.volume = vol;
        if (vol <= 0) {
            clearInterval(ambientFadeInt);
            if (ambientAudio) { ambientAudio.pause(); ambientAudio = null; }
            if (callback) callback();
        }
    }, 50);
}

function escapeHTML(s) {
    return s.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// 把文字切成片段 [{text, highlight}]，吉祥物的名字会被高亮
function parseSegments(text) {
    const name = (AppState.config && AppState.config.project && AppState.config.project.mascot_name) || '';
    if (!name) return [{ text, highlight: false }];
    const parts = [];
    let last = 0, idx;
    while ((idx = text.indexOf(name, last)) !== -1) {
        if (idx > last) parts.push({ text: text.slice(last, idx), highlight: false });
        parts.push({ text: name, highlight: true });
        last = idx + name.length;
    }
    if (last < text.length) parts.push({ text: text.slice(last), highlight: false });
    return parts;
}

function buildHighlightedHTML(text) {
    return parseSegments(text).map(s =>
        s.highlight ? '<span class="dau-name">' + escapeHTML(s.text) + '</span>' : escapeHTML(s.text)
    ).join('');
}

// 打字机效果：一个字一个字地出现，名字打完整后才高亮
function typewriterEffect(el, text, speed, onComplete) {
    const segments = parseSegments(text);
    const cursor   = '<span class="tw-cursor"></span>';
    let i = 0;

    function renderPartial(len) {
        let html = '';
        let pos  = 0;
        for (const seg of segments) {
            const segEnd = pos + seg.text.length;
            if (len >= segEnd) {
                html += seg.highlight
                    ? '<span class="dau-name">' + escapeHTML(seg.text) + '</span>'
                    : escapeHTML(seg.text);
            } else if (len > pos) {
                html += escapeHTML(seg.text.slice(0, len - pos));
                break;
            } else {
                break;
            }
            pos = segEnd;
        }
        return html;
    }

    const timer = setInterval(() => {
        if (i < text.length) {
            i++;
            el.innerHTML = renderPartial(i) + cursor;
        } else {
            clearInterval(timer);
            el.innerHTML = renderPartial(text.length);
            if (onComplete) setTimeout(onComplete, 300);
        }
    }, speed);
    prologueTimers.push(timer);
}

function runPrologueAnimation(config) {
    if (!config || !config.prologue_screen) return;
    const ps        = config.prologue_screen;
    const lines     = ps.lines || [];
    const container = document.getElementById('prologue-lines');
    if (!container) return;
    container.innerHTML = '';

    const btnGo   = document.getElementById('btn-prologue-go');
    const btnSkip = document.getElementById('btn-prologue-skip');
    if (btnGo && ps.cta_button)    btnGo.textContent   = ps.cta_button;
    if (btnSkip && ps.skip_button) btnSkip.textContent = ps.skip_button;

    lines.forEach(() => {
        const el = document.createElement('p');
        el.className = 'prologue-line';
        container.appendChild(el);
    });
    const lineEls     = container.querySelectorAll('.prologue-line');
    let   currentLine = 0;

    function showNextLine() {
        if (currentLine >= lines.length) {
            showPrologueCTA();
            return;
        }
        const lineData = lines[currentLine];
        const el       = lineEls[currentLine];
        el.classList.add('visible');

        // 最后一句时，吉祥物晃一晃
        if (currentLine === lines.length - 1) {
            const mascot = document.getElementById('prologue-mascot');
            if (mascot) {
                mascot.classList.remove('wiggle');
                void mascot.offsetWidth;
                mascot.classList.add('wiggle');
            }
        }

        if (lineData.effect === 'typewriter') {
            typewriterEffect(el, lineData.text, 80, () => {
                currentLine++;
                const t = setTimeout(showNextLine, 700);
                prologueTimers.push(t);
            });
        } else {
            el.innerHTML = buildHighlightedHTML(lineData.text);
            currentLine++;
            // 中文阅读按字数留时间，长句停久一点
            const delay = (currentLine === lines.length) ? 500 : Math.min(1100 + lineData.text.length * 25, 2600);
            const t = setTimeout(showNextLine, delay);
            prologueTimers.push(t);
        }
    }

    const t0 = setTimeout(showNextLine, 500);
    prologueTimers.push(t0);
}

function showPrologueCTA() {
    const cta = document.getElementById('btn-prologue-go');
    if (cta) cta.classList.add('visible');
}

function leavePrologue() {
    prologueTimers.forEach(t => { clearTimeout(t); clearInterval(t); });
    prologueTimers = [];

    // 1. 在吉祥物当前位置放一个“替身”
    const mascotEl = document.getElementById('prologue-mascot');
    const flyEl    = document.getElementById('mascot-fly');
    if (mascotEl && flyEl) {
        const rect = mascotEl.getBoundingClientRect();
        flyEl.style.top       = rect.top  + 'px';
        flyEl.style.left      = rect.left + 'px';
        flyEl.style.transform = 'translate(0, 0)';
        flyEl.classList.add('fly-start');
        mascotEl.style.opacity = '0';

        // 2. 替身飞向左上角
        requestAnimationFrame(() => requestAnimationFrame(() => {
            flyEl.classList.add('fly-go');
            flyEl.style.top       = '-70px';
            flyEl.style.left      = '-70px';
            flyEl.style.transform = 'translate(0, 0) scale(0.5)';
        }));
    }

    // 3. 只淡出故事文字，背景保留给地图页
    const screen = document.getElementById('screen-prologue');
    if (screen) screen.classList.add('fade-out');
    stopAmbient(() => {});

    setTimeout(() => {
        if (screen) screen.classList.remove('active', 'fade-out');
        if (mascotEl) mascotEl.style.opacity = '';
        renderMapScreen(AppState.config);
        Screens.map.classList.add('active');

        setTimeout(() => {
            if (flyEl) {
                flyEl.style.transition = 'opacity 0.4s ease';
                flyEl.style.opacity    = '0';
                setTimeout(() => {
                    flyEl.classList.remove('fly-start', 'fly-go');
                    flyEl.style.transition = '';
                    flyEl.style.opacity    = '';
                }, 400);
            }
        }, 800);
    }, 500);
}

function bindPrologueButtons() {
    const btnGo   = document.getElementById('btn-prologue-go');
    const btnSkip = document.getElementById('btn-prologue-skip');
    if (btnGo)   btnGo.addEventListener('click',   leavePrologue);
    if (btnSkip) btnSkip.addEventListener('click', leavePrologue);
}

// ─── 旅程地图 ────────────────────────────────────────────────────────────────
function renderMapScreen(config) {
    if (!config || !config.map_screen) return;
    const ms = config.map_screen;
    const titleEl  = document.getElementById('ui-map-title');
    const imgEl    = document.getElementById('ui-map-image');
    const btnEl    = document.getElementById('btn-map-go');
    const actions  = document.querySelector('.map-actions');

    if (titleEl && ms.title) titleEl.textContent = ms.title;
    if (btnEl && ms.cta_button) btnEl.textContent = ms.cta_button;
    if (imgEl && ms.background_image) imgEl.src = ms.background_image;

    requestAnimationFrame(() => {
        const frameEl = document.getElementById('map-wood-frame');
        if (frameEl)  frameEl.classList.add('visible');
        if (titleEl)  titleEl.classList.add('visible');
        if (actions)  actions.classList.add('visible');
    });
}

function leaveMapScreen() {
    const screen   = document.getElementById('screen-map');
    const sharedBg = document.getElementById('prologue-map-bg');

    if (screen)   screen.classList.add('fade-out');
    if (sharedBg) sharedBg.classList.add('fade-out');

    setTimeout(() => {
        if (screen)   screen.classList.remove('active', 'fade-out');
        if (sharedBg) sharedBg.classList.remove('active', 'fade-out');
        renderStory(AppState.config, 0);
        Screens.show(Screens.story);
    }, 500);
}

function bindMapButton() {
    const btn = document.getElementById('btn-map-go');
    if (btn) btn.addEventListener('click', leaveMapScreen);
}

// ─── 语音讲解 ────────────────────────────────────────────────────────────────
// 展区配置了 audio（mp3）就播放音频；没有的话，用手机自带的中文语音朗读文字。
const Narrator = {
    _voice: null,

    supported() {
        return 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;
    },

    _pickVoice() {
        if (!this.supported()) return null;
        const voices = window.speechSynthesis.getVoices();
        return voices.find(v => /zh[-_]CN/i.test(v.lang))
            || voices.find(v => /^zh/i.test(v.lang))
            || null;
    },

    // 必须在用户点击时调用一次，iOS 才允许之后自动朗读
    unlock() {
        if (!this.supported()) return;
        try {
            const u = new SpeechSynthesisUtterance('');
            u.volume = 0;
            window.speechSynthesis.speak(u);
        } catch (e) { /* 忽略 */ }
    },

    speak(text) {
        this.stop();
        if (!this.supported() || !text) return;
        try {
            if (!this._voice) this._voice = this._pickVoice();
            const u = new SpeechSynthesisUtterance(text);
            u.lang = 'zh-CN';
            u.rate = 1;
            if (this._voice) u.voice = this._voice;
            window.speechSynthesis.speak(u);
        } catch (e) { /* 忽略 */ }
    },

    stop() {
        if (!this.supported()) return;
        try { window.speechSynthesis.cancel(); } catch (e) { /* 忽略 */ }
    }
};

if (Narrator.supported()) {
    window.speechSynthesis.onvoiceschanged = () => { Narrator._voice = Narrator._pickVoice(); };
}

// ─── 展区故事 ────────────────────────────────────────────────────────────────
let currentAudio = null;
let isMuted      = false; // 全局静音状态，切换展区时保持不变

function stopNarration() {
    if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
    }
    Narrator.stop();
}

function playNarration(slide) {
    stopNarration();
    if (isMuted || !slide) return;
    if (slide.audio) {
        currentAudio = new Audio(slide.audio);
        currentAudio.play().catch(() => { /* 浏览器拦截自动播放，用户可以点喇叭按钮 */ });
    } else {
        Narrator.speak(slide.text);
    }
}

function renderStory(config, zoneIndex) {
    if (!config) return;
    AppState.currentZoneIndex = zoneIndex;
    const zone  = config.zones[zoneIndex];
    const slide = zone.slides[0];

    document.getElementById('ui-zone-name').textContent  = zone.name;
    document.getElementById('ui-slide-text').textContent = slide.text;

    const img = document.getElementById('ui-slide-image');
    img.src = slide.image;
    img.alt = zone.name;

    playNarration(slide);

    // 底部圆点导航
    const dotsContainer = document.getElementById('ui-nav-dots');
    dotsContainer.innerHTML = '';
    config.zones.forEach((_, i) => {
        const dot = document.createElement('button');
        dot.className = 'dot' + (i === zoneIndex ? ' active' : '');
        dot.setAttribute('aria-label', '第 ' + (i + 1) + ' 站');
        dot.addEventListener('click', () => navigateTo(config, i));
        dotsContainer.appendChild(dot);
    });

    // 最后一站时，提示文字改成去挑战
    const nextBtn = document.getElementById('btn-story-next');
    if (nextBtn) {
        const last = zoneIndex === config.zones.length - 1;
        nextBtn.innerHTML = (last ? '走完啦！去完成印记挑战' : '向左滑动或点这里，去下一站')
            + ' <span class="arrow">&rarr;</span>';
    }

    syncAudioButton();
}

function navigateTo(config, index) {
    const total = config.zones.length;
    if (index < 0) return;
    if (index >= total) {
        stopNarration();
        renderChallenge(config);
        Screens.show(Screens.challenge);
        return;
    }
    renderStory(config, index);
}

function syncAudioButton() {
    const btn = document.getElementById('btn-audio');
    if (!btn) return;
    const iconSound = btn.querySelector('.icon-sound');
    const iconMute  = btn.querySelector('.icon-mute');

    if (isMuted) {
        iconSound.style.display = 'none';
        iconMute.style.display  = 'block';
        btn.classList.remove('is-playing');
        btn.classList.add('is-muted');
    } else {
        iconSound.style.display = 'block';
        iconMute.style.display  = 'none';
        btn.classList.add('is-playing');
        btn.classList.remove('is-muted');
    }
}

function bindAudioToggle() {
    document.getElementById('btn-audio').addEventListener('click', () => {
        isMuted = !isMuted;
        if (isMuted) {
            stopNarration();
        } else {
            const config = AppState.config;
            playNarration(config.zones[AppState.currentZoneIndex].slides[0]);
        }
        syncAudioButton();
    });
}

function bindSwipeNavigation() {
    const storyEl = document.getElementById('screen-story');
    let touchStartX = 0;
    let touchStartY = 0;

    storyEl.addEventListener('touchstart', e => {
        touchStartX = e.touches[0].clientX;
        touchStartY = e.touches[0].clientY;
    }, { passive: true });

    storyEl.addEventListener('touchend', e => {
        const dx = e.changedTouches[0].clientX - touchStartX;
        const dy = e.changedTouches[0].clientY - touchStartY;
        if (Math.abs(dx) < 50 || Math.abs(dx) < Math.abs(dy)) return;
        const config = AppState.config;
        const cur    = AppState.currentZoneIndex;
        if (dx < 0) navigateTo(config, cur + 1);
        else        navigateTo(config, cur - 1);
    }, { passive: true });

    const nextBtn = document.getElementById('btn-story-next');
    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            navigateTo(AppState.config, AppState.currentZoneIndex + 1);
        });
    }

    // 键盘左右键
    document.addEventListener('keydown', e => {
        if (!Screens.story.classList.contains('active')) return;
        const config = AppState.config;
        const cur    = AppState.currentZoneIndex;
        if (e.key === 'ArrowRight') navigateTo(config, cur + 1);
        if (e.key === 'ArrowLeft')  navigateTo(config, cur - 1);
    });
}

// ─── 挑战入口与答题 ──────────────────────────────────────────────────────────
function renderChallenge(config) {
    if (!config || !config.quiz_game || !config.quiz_game.challenge_screen) return;
    const s = config.quiz_game.challenge_screen;
    document.getElementById('ui-challenge-title').textContent = s.title;
    document.getElementById('ui-challenge-desc').textContent  = s.description;
    document.getElementById('btn-start-quiz').textContent     = s.start_button;

    const landing = document.getElementById('challenge-landing');
    if (landing && s.image) {
        landing.style.backgroundImage = 'url(' + s.image + ')';
    }
}

function closeQuiz() {
    Screens.quiz.classList.add('slide-down-exit');
    setTimeout(() => {
        Screens.quiz.classList.remove('active');
        Screens.quiz.classList.remove('slide-down-exit');
    }, 500);
}

function bindChallengeTransition() {
    const btnStartQuiz = document.getElementById('btn-start-quiz');
    if (!btnStartQuiz) return;

    btnStartQuiz.addEventListener('click', () => {
        if (AppState.config) {
            GameEngine.init(AppState.config);
            GameEngine.startQuiz();
        }
    });

    const btnCloseQuiz = document.getElementById('btn-close-quiz');
    if (btnCloseQuiz) btnCloseQuiz.addEventListener('click', closeQuiz);

    // 向下滑动关闭答题
    const quizScreen = document.getElementById('screen-quiz');
    let touchStartY = 0;

    quizScreen.addEventListener('touchstart', e => {
        touchStartY = e.touches[0].clientY;
    }, { passive: true });

    quizScreen.addEventListener('touchend', e => {
        const dy = e.changedTouches[0].clientY - touchStartY;
        if (dy > 100) closeQuiz();
    }, { passive: true });
}

// ─── 横屏提示、断网提示、启动 ───────────────────────────────────────────────
function bindOrientationWarning() {
    const warning = document.getElementById('orientation-warning');
    function checkOrientation() {
        // 只在手机横屏（高度很矮）时提示
        const isLandscape = window.matchMedia('(orientation: landscape)').matches;
        const isShort     = window.innerHeight < 500;
        warning.style.display = (isLandscape && isShort) ? 'flex' : 'none';
    }
    window.addEventListener('resize', checkOrientation);
    window.addEventListener('orientationchange', checkOrientation);
    checkOrientation();
}

function bindOfflineToast() {
    window.addEventListener('offline', () => {
        const msg = (AppState.config && AppState.config.exceptions && AppState.config.exceptions.offline_toast)
            || '网络好像断开了，正在重新连接……';
        GameEngine.showToast(msg);
    });
}

document.addEventListener('DOMContentLoaded', () => {
    runLoadingScreen();
    bindLoadRetry();
    bindCurtainTransition();
    bindPrologueButtons();
    bindMapButton();
    bindSwipeNavigation();
    bindAudioToggle();
    bindOrientationWarning();
    bindOfflineToast();
    bindChallengeTransition();
});
