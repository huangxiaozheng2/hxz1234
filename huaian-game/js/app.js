// js/app.js —— 入口与页面流程
// 加载 → 首页 → 开场故事 → 闯关地图 ⇄（站点故事 → 小游戏 → 盖章）× 4
//      → 印记大挑战（限时答题）→ 结束页（称号 + 分享海报）

// ─── 全局状态 ────────────────────────────────────────────────────────────────
const AppState = {
    config: null,
    station: null,       // 当前站点配置
    game: null,          // 当前小游戏实例
    progress: { stations: {} },   // { stations: { id: { stars, score } } }
    quizResult: null,
};

const STORE_KEY = 'huaian-yinji-v2';

const Store = {
    load() {
        try {
            const raw = localStorage.getItem(STORE_KEY);
            const p = raw ? JSON.parse(raw) : null;
            if (p && p.stations) AppState.progress = p;
        } catch (e) { /* 隐私模式等情况下读不到，忽略 */ }
    },
    save() {
        try { localStorage.setItem(STORE_KEY, JSON.stringify(AppState.progress)); } catch (e) { /* 忽略 */ }
    },
    clear() {
        AppState.progress = { stations: {} };
        try { localStorage.removeItem(STORE_KEY); } catch (e) { /* 忽略 */ }
    },
};

const starsOf = id => (AppState.progress.stations[id] || {}).stars || 0;
const stationsDone = () => AppState.config.stations.filter(s => starsOf(s.id) > 0).length;

// ─── 页面切换 ────────────────────────────────────────────────────────────────
const Screens = {
    loading:   document.getElementById('screen-loading'),
    intro:     document.getElementById('screen-intro'),
    prologue:  document.getElementById('screen-prologue'),
    hub:       document.getElementById('screen-hub'),
    station:   document.getElementById('screen-station'),
    game:      document.getElementById('screen-game'),
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

const $ = id => document.getElementById(id);

// ─── 加载 ────────────────────────────────────────────────────────────────────
function runLoadingScreen() {
    const progressFill = document.querySelector('#screen-loading .progress-fill');
    const errorBox     = $('ui-load-error');
    errorBox.classList.remove('visible');
    progressFill.style.width = '0%';
    let progress = 0;

    const tick = setInterval(() => {
        progress += 25;
        progressFill.style.width = progress + '%';
        if (progress >= 100) {
            clearInterval(tick);
            loadConfig().then(() => {
                setTimeout(() => {
                    Screens.show(Screens.intro);
                    renderIntro(AppState.config);
                }, 300);
            }).catch(err => {
                console.error(err);
                errorBox.classList.add('visible');
            });
        }
    }, 220);
}

function loadConfig() {
    return fetch('flow.yaml')
        .then(r => {
            if (!r.ok) throw new Error('无法加载 flow.yaml');
            return r.text();
        })
        .then(text => {
            const config = jsyaml.load(text);
            AppState.config = config;
            SFX.init(config);
            applyTheme(config);
            const errEl = $('ui-load-error-text');
            if (config.qr_screen && config.qr_screen.error_message) errEl.textContent = config.qr_screen.error_message;
            preloadImages(config);
        });
}

function preloadImages(config) {
    const urls = [config.intro_screen.background_image, config.map_screen.background_image];
    config.stations.forEach(s => urls.push(s.image));
    (config.endscreen.ranks || []).forEach(r => urls.push(r.badge));
    urls.filter(Boolean).forEach(url => { const img = new Image(); img.src = url; });
}

function applyTheme(config) {
    const t = config.project && config.project.theme;
    if (!t) return;
    const root = document.documentElement;
    if (t.secondary_color) root.style.setProperty('--gold-color',      t.secondary_color);
    if (t.primary_color)   root.style.setProperty('--alternate-color', t.primary_color);
}

// ─── 首页 ────────────────────────────────────────────────────────────────────
function renderIntro(config) {
    const s = config.intro_screen;
    const hasProgress = stationsDone() > 0;
    $('ui-intro-title').textContent    = s.title || '';
    $('ui-intro-subtitle').textContent = s.subtitle || '';
    $('ui-intro-text').textContent     = s.intro_text || '';
    $('btn-start').textContent         = hasProgress ? (s.continue_button || '继续') : (s.start_button || '开始');
    const restart = $('btn-restart');
    restart.textContent = s.restart_link || '从头开始';
    restart.hidden = !hasProgress;
    $('intro-landing').style.backgroundImage = 'url(' + (s.background_image || 'assets/images/intro-bg.jpg') + ')';
}

function openCurtain(next) {
    Screens.intro.classList.add('closing');
    setTimeout(() => {
        next();
        Screens.intro.classList.remove('closing');
        Screens.intro.classList.add('open');
        setTimeout(() => {
            Screens.intro.classList.remove('active', 'open');
        }, 1000);
    }, 1000);
}

function bindIntro() {
    $('btn-start').addEventListener('click', () => {
        // 在用户点击时解锁声音和语音（手机浏览器要求）
        SFX.unlock();
        Narrator.unlock();
        const config = AppState.config;
        if (stationsDone() > 0) {
            openCurtain(() => {
                renderHub();
                Screens.hub.classList.add('active');
                requestAnimationFrame(fitHubMap);
            });
            return;
        }
        openCurtain(() => {
            $('prologue-map-bg').classList.add('active');
            Screens.prologue.classList.add('active');
            setTimeout(() => {
                if (config.prologue_screen.ambient_audio) startAmbient(config.prologue_screen.ambient_audio);
                runPrologueAnimation(config);
            }, 1000);
        });
    });
    $('btn-restart').addEventListener('click', () => {
        Store.clear();
        renderIntro(AppState.config);
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

function stopAmbient() {
    clearInterval(ambientFadeInt);
    if (!ambientAudio) return;
    let vol = ambientAudio.volume;
    ambientFadeInt = setInterval(() => {
        vol = Math.max(vol - 0.03, 0);
        if (ambientAudio) ambientAudio.volume = vol;
        if (vol <= 0) {
            clearInterval(ambientFadeInt);
            if (ambientAudio) { ambientAudio.pause(); ambientAudio = null; }
        }
    }, 50);
}

function escapeHTML(s) {
    return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// 把文字切成片段，吉祥物的名字会被高亮
function parseSegments(text) {
    const name = (AppState.config.project && AppState.config.project.mascot_name) || '';
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

function typewriterEffect(el, text, speed, onComplete) {
    const segments = parseSegments(text);
    const cursor   = '<span class="tw-cursor"></span>';
    let i = 0;
    function renderPartial(len) {
        let html = '', pos = 0;
        for (const seg of segments) {
            const segEnd = pos + seg.text.length;
            if (len >= segEnd) {
                html += seg.highlight ? '<span class="dau-name">' + escapeHTML(seg.text) + '</span>' : escapeHTML(seg.text);
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
    const ps        = config.prologue_screen;
    const lines     = ps.lines || [];
    const container = $('prologue-lines');
    container.innerHTML = '';
    $('btn-prologue-go').textContent   = ps.cta_button || '出发！';
    $('btn-prologue-skip').textContent = ps.skip_button || '跳过';

    lines.forEach(() => {
        const el = document.createElement('p');
        el.className = 'prologue-line';
        container.appendChild(el);
    });
    const lineEls = container.querySelectorAll('.prologue-line');
    let current = 0;

    function showNextLine() {
        if (current >= lines.length) {
            $('btn-prologue-go').classList.add('visible');
            return;
        }
        const line = lines[current];
        const el   = lineEls[current];
        el.classList.add('visible');
        if (current === lines.length - 1) {
            const mascot = $('prologue-mascot');
            mascot.classList.remove('wiggle');
            void mascot.offsetWidth;
            mascot.classList.add('wiggle');
        }
        if (line.effect === 'typewriter') {
            typewriterEffect(el, line.text, 80, () => {
                current++;
                prologueTimers.push(setTimeout(showNextLine, 700));
            });
        } else {
            el.innerHTML = buildHighlightedHTML(line.text);
            current++;
            const delay = (current === lines.length) ? 500 : Math.min(1100 + line.text.length * 25, 2600);
            prologueTimers.push(setTimeout(showNextLine, delay));
        }
    }
    prologueTimers.push(setTimeout(showNextLine, 500));
}

function leavePrologue() {
    prologueTimers.forEach(t => { clearTimeout(t); clearInterval(t); });
    prologueTimers = [];

    const mascotEl = $('prologue-mascot');
    const flyEl    = $('mascot-fly');
    const rect = mascotEl.getBoundingClientRect();
    flyEl.style.top       = rect.top  + 'px';
    flyEl.style.left      = rect.left + 'px';
    flyEl.style.transform = 'translate(0, 0)';
    flyEl.classList.add('fly-start');
    mascotEl.style.opacity = '0';
    requestAnimationFrame(() => requestAnimationFrame(() => {
        flyEl.classList.add('fly-go');
        flyEl.style.top       = '-70px';
        flyEl.style.left      = '-70px';
        flyEl.style.transform = 'translate(0, 0) scale(0.5)';
    }));

    Screens.prologue.classList.add('fade-out');
    $('prologue-map-bg').classList.add('fade-out');
    stopAmbient();

    setTimeout(() => {
        Screens.prologue.classList.remove('active', 'fade-out');
        $('prologue-map-bg').classList.remove('active', 'fade-out');
        mascotEl.style.opacity = '';
        showHub();
        setTimeout(() => {
            flyEl.style.transition = 'opacity 0.4s ease';
            flyEl.style.opacity    = '0';
            setTimeout(() => {
                flyEl.classList.remove('fly-start', 'fly-go');
                flyEl.style.transition = '';
                flyEl.style.opacity    = '';
            }, 400);
        }, 800);
    }, 500);
}

function bindPrologueButtons() {
    $('btn-prologue-go').addEventListener('click', leavePrologue);
    $('btn-prologue-skip').addEventListener('click', leavePrologue);
}

// ─── 印章（DOM 版）─────────────────────────────────────────────────────────
function sealHTML(chars) {
    return [...String(chars || '').slice(0, 4)].map(c => `<i>${escapeHTML(c)}</i>`).join('');
}

function starsHTML(n, total = 3) {
    let h = '';
    for (let i = 0; i < total; i++) {
        h += `<svg class="star ${i < n ? 'on' : ''}" viewBox="0 0 24 24" aria-hidden="true"><use href="#icon-star"></use></svg>`;
    }
    return h;
}

// ─── 闯关地图 ────────────────────────────────────────────────────────────────
function showHub() {
    renderHub();
    Screens.show(Screens.hub);
    requestAnimationFrame(fitHubMap);
}

function fitHubMap() {
    const wrap = document.querySelector('.hub-map-wrap');
    const map  = $('ui-hub-map');
    if (!wrap || !map) return;
    const ratio = 1024 / 1536;
    const w = wrap.clientWidth, h = wrap.clientHeight;
    let mw = w, mh = w / ratio;
    if (mh > h) { mh = h; mw = h * ratio; }
    map.style.width  = mw + 'px';
    map.style.height = mh + 'px';
}

function renderHub() {
    const config = AppState.config;
    const ms = config.map_screen;
    $('ui-hub-title').textContent = ms.title || '';
    $('ui-hub-map-img').src = ms.background_image;

    const map = $('ui-hub-map');
    map.querySelectorAll('.hub-spot').forEach(el => el.remove());

    const nextIndex = config.stations.findIndex(s => starsOf(s.id) === 0);
    const allDone = nextIndex === -1;

    config.stations.forEach((s, i) => {
        const stars = starsOf(s.id);
        const state = stars > 0 ? 'done' : i === nextIndex ? 'open' : 'locked';
        const b = document.createElement('button');
        b.className = 'hub-spot ' + state;
        b.style.left = s.position.x + '%';
        b.style.top  = s.position.y + '%';
        b.setAttribute('aria-label', `${s.name}（${state === 'done' ? stars + ' 星' : state === 'open' ? '可进入' : '未解锁'}）`);
        if (state === 'done') {
            b.innerHTML = `<span class="seal mini">${sealHTML(s.stamp)}</span><span class="spot-stars">${starsHTML(stars)}</span>`;
        } else if (state === 'locked') {
            b.innerHTML = `<svg class="lock" viewBox="0 0 24 24" aria-hidden="true"><use href="#icon-lock"></use></svg>`;
        } else {
            b.innerHTML = `<span class="spot-ring"></span><span class="spot-go">进入</span>`;
        }
        b.addEventListener('click', () => {
            if (state === 'locked') {
                GameEngine.showToast(`先完成「${config.stations[nextIndex].name}」才能解锁这里`);
                return;
            }
            openStation(s);
        });
        map.appendChild(b);
    });

    // 终点：印记大挑战
    const fin = document.createElement('button');
    fin.className = 'hub-spot final ' + (allDone ? 'open' : 'locked');
    fin.style.left = ms.final_position.x + '%';
    fin.style.top  = ms.final_position.y + '%';
    fin.setAttribute('aria-label', ms.final_label + (allDone ? '' : '（集齐四枚印章后解锁）'));
    fin.innerHTML = allDone
        ? `<span class="spot-ring big"></span><span class="spot-go">挑战</span>`
        : `<svg class="lock" viewBox="0 0 24 24" aria-hidden="true"><use href="#icon-lock"></use></svg>`;
    fin.addEventListener('click', () => {
        if (!allDone) {
            GameEngine.showToast('集齐四枚印章，才能开启印记大挑战');
            return;
        }
        renderChallenge();
        Screens.show(Screens.challenge);
    });
    map.appendChild(fin);

    // 顶部印章栏
    const bar = $('ui-hub-stamps');
    bar.innerHTML = config.stations.map(s =>
        `<span class="seal tiny ${starsOf(s.id) ? 'on' : ''}" title="${escapeHTML(s.name)}">${sealHTML(s.stamp)}</span>`
    ).join('');

    $('ui-hub-hint').textContent = allDone
        ? '四枚印章集齐了！点地图最上方，开启印记大挑战。'
        : `已集 ${stationsDone()}/${config.stations.length} 枚印章 · ${ms.hint || ''}`;
}

// ─── 语音讲解 ────────────────────────────────────────────────────────────────
const Narrator = {
    _voice: null,
    supported() { return 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window; },
    _pickVoice() {
        if (!this.supported()) return null;
        const voices = window.speechSynthesis.getVoices();
        return voices.find(v => /zh[-_]CN/i.test(v.lang)) || voices.find(v => /^zh/i.test(v.lang)) || null;
    },
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
            if (this._voice) u.voice = this._voice;
            window.speechSynthesis.speak(u);
        } catch (e) { /* 忽略 */ }
    },
    stop() {
        if (!this.supported()) return;
        try { window.speechSynthesis.cancel(); } catch (e) { /* 忽略 */ }
    },
};
if (Narrator.supported()) {
    window.speechSynthesis.onvoiceschanged = () => { Narrator._voice = Narrator._pickVoice(); };
}

let currentAudio = null;

function stopNarration() {
    if (currentAudio) { currentAudio.pause(); currentAudio = null; }
    Narrator.stop();
}

function playNarration(station) {
    stopNarration();
    if (isMuted || !station) return;
    if (station.audio) {
        currentAudio = new Audio(station.audio);
        currentAudio.play().catch(() => {});
    } else {
        Narrator.speak(station.story);
    }
}

function syncAudioButton() {
    const btn = $('btn-audio');
    btn.querySelector('.icon-sound').style.display = isMuted ? 'none' : 'block';
    btn.querySelector('.icon-mute').style.display  = isMuted ? 'block' : 'none';
    btn.classList.toggle('is-playing', !isMuted);
    btn.classList.toggle('is-muted', isMuted);
}

// ─── 站点故事 ────────────────────────────────────────────────────────────────
function openStation(station) {
    AppState.station = station;
    $('ui-station-name').textContent  = station.name;
    $('ui-station-story').textContent = station.story;
    const img = $('ui-station-image');
    img.src = station.image;
    img.alt = station.name;
    $('btn-station-play').textContent = `开始小游戏：${station.game.title}`;
    syncAudioButton();
    Screens.show(Screens.station);
    playNarration(station);
}

function bindStation() {
    $('btn-station-back').addEventListener('click', () => { stopNarration(); showHub(); });
    $('btn-station-play').addEventListener('click', () => { stopNarration(); startGame(AppState.station); });
    $('btn-audio').addEventListener('click', () => {
        isMuted = !isMuted;
        if (isMuted) stopNarration(); else playNarration(AppState.station);
        syncAudioButton();
    });
}

// ─── 小游戏 ──────────────────────────────────────────────────────────────────
function startGame(station) {
    if (AppState.game) AppState.game.destroy();
    const cfg = station.game;
    const factory = window.MiniGames && MiniGames[cfg.type];
    if (!factory) { GameEngine.showToast('这个小游戏还没准备好'); return; }

    const stage = $('ui-game-stage');
    stage.innerHTML = '';
    stage.className = 'game-stage game-' + cfg.type;
    $('ui-game-title').textContent = cfg.title;
    $('ui-game-hud').textContent = '';
    $('ui-howto-title').textContent = cfg.title;
    $('ui-howto-text').textContent = cfg.howto || '';
    $('ui-game-howto').hidden = false;
    $('ui-game-result').hidden = true;
    $('ui-game-countdown').hidden = true;
    Screens.show(Screens.game);

    AppState.game = factory.create(stage, cfg, {
        setHud: text => { $('ui-game-hud').textContent = text; },
        finish: res => showGameResult(station, res),
    });
}

function runCountdown(done) {
    const el = $('ui-game-countdown');
    let n = 3;
    el.hidden = false;
    const step = () => {
        if (n === 0) {
            el.textContent = '开始！';
            el.classList.remove('pop'); void el.offsetWidth; el.classList.add('pop');
            SFX.tone(1180, 0.15, { vol: 0.2 });
            setTimeout(() => { el.hidden = true; done(); }, 450);
            return;
        }
        el.textContent = n;
        el.classList.remove('pop'); void el.offsetWidth; el.classList.add('pop');
        SFX.tone(700, 0.08, { vol: 0.15 });
        n--;
        setTimeout(step, 650);
    };
    step();
}

function showGameResult(station, res) {
    const prev = AppState.progress.stations[station.id] || { stars: 0, score: 0 };
    const isBest = res.stars > prev.stars || (res.stars === prev.stars && res.score > prev.score);
    if (isBest) {
        AppState.progress.stations[station.id] = { stars: res.stars, score: res.score };
        Store.save();
    }

    const passed = res.stars > 0;
    const seal = $('ui-result-seal');
    seal.innerHTML = sealHTML(station.stamp);
    seal.className = 'seal' + (passed ? '' : ' faded');
    $('ui-result-stars').innerHTML = starsHTML(res.stars);
    $('ui-result-title').textContent = res.title;
    $('ui-result-detail').textContent = res.detail + (passed && !isBest ? '（保留了你之前更好的成绩）' : '');
    const next = $('btn-result-next');
    const retry = $('btn-result-retry');
    if (passed) {
        next.textContent = '盖章成功，返回地图';
        retry.textContent = res.stars < 3 ? '再玩一次，争取更多星' : '再玩一次';
    } else {
        next.textContent = '再试一次';
        retry.textContent = '先回地图';
    }
    next.dataset.action = passed ? 'hub' : 'retry';
    retry.dataset.action = passed ? 'retry' : 'hub';

    $('ui-game-result').hidden = false;
    if (passed) {
        seal.classList.add('slam');
        setTimeout(() => { SFX.stamp(); if (navigator.vibrate) navigator.vibrate(60); }, 380);
        setTimeout(() => SFX.play('chime_sfx'), 700);
    } else {
        SFX.play('incorrect_sfx');
    }
}

function leaveGame(action) {
    if (AppState.game) { AppState.game.destroy(); AppState.game = null; }
    if (action === 'retry') startGame(AppState.station);
    else showHub();
}

function bindGame() {
    $('btn-howto-go').addEventListener('click', () => {
        SFX.unlock();
        $('ui-game-howto').hidden = true;
        runCountdown(() => { if (AppState.game) AppState.game.start(); });
    });
    $('btn-game-quit').addEventListener('click', () => leaveGame('hub'));
    $('btn-result-next').addEventListener('click', e => leaveGame(e.currentTarget.dataset.action));
    $('btn-result-retry').addEventListener('click', e => leaveGame(e.currentTarget.dataset.action));
}

// ─── 印记大挑战 ──────────────────────────────────────────────────────────────
function renderChallenge() {
    const s = AppState.config.quiz_game.challenge_screen;
    $('ui-challenge-title').textContent = s.title;
    $('ui-challenge-desc').textContent  = s.description;
    $('btn-start-quiz').textContent     = s.start_button;
}

function bindChallenge() {
    $('btn-start-quiz').addEventListener('click', () => {
        GameEngine.init(AppState.config, showEnd);
        GameEngine.startQuiz();
    });
    $('btn-challenge-back').addEventListener('click', showHub);
}

// ─── 结束页 ──────────────────────────────────────────────────────────────────
function computeResult(quiz) {
    const config = AppState.config;
    const stations = config.stations.map(s => ({ ...s, ...(AppState.progress.stations[s.id] || { stars: 0, score: 0 }) }));
    const starSum = stations.reduce((a, s) => a + s.stars, 0);
    const starMax = stations.length * 3;
    const ratio = 0.6 * (starSum / starMax) + 0.4 * (quiz.correct / quiz.total);
    const ranks = (config.endscreen.ranks || []).slice().sort((a, b) => b.min - a.min);
    const rank = ranks.find(r => ratio >= r.min) || ranks[ranks.length - 1];
    const total = stations.reduce((a, s) => a + (s.score || 0), 0) + quiz.score;
    return { stations, starSum, starMax, rank, total, quiz };
}

function showEnd(quiz) {
    const es = AppState.config.endscreen;
    const r = computeResult(quiz);
    AppState.quizResult = r;

    $('ui-end-rank').textContent = `「${r.rank.title}」`;
    $('ui-end-score').textContent = `${es.score_label || '总分'} ${r.total}`;
    $('ui-end-breakdown').innerHTML =
        `<span>印章星数 <b>${r.starSum}/${r.starMax}</b></span>` +
        `<span>答题 <b>${quiz.correct}/${quiz.total}</b></span>` +
        `<span>最高连击 <b>${quiz.bestCombo}</b></span>`;
    $('ui-end-message').textContent = r.rank.message;
    $('input-nickname').placeholder = es.nickname_placeholder || '';
    $('btn-share-text').textContent = es.share_button;
    $('btn-replay').textContent = es.replay_button;

    Screens.show(Screens.end);
    setTimeout(() => GameEngine.runBadgeAnimation(r.rank.badge), 700);
}

function bindEnd() {
    const es = () => AppState.config.endscreen;

    $('btn-share').addEventListener('click', async () => {
        const r = AppState.quizResult;
        const btn = $('btn-share');
        btn.disabled = true;
        try {
            const url = location.href.split('#')[0];
            const dataUrl = await Poster.render({
                nickname: $('input-nickname').value,
                rankTitle: r.rank.title,
                rankMessage: r.rank.message,
                badge: r.rank.badge,
                score: r.total,
                quizText: `答对 ${r.quiz.correct}/${r.quiz.total} 题`,
                stations: r.stations.map(s => ({ stamp: s.stamp, stars: s.stars })),
                url,
            });
            $('ui-poster-img').src = dataUrl;
            $('ui-poster-hint').textContent = es().poster_hint;
            const save = $('btn-poster-save');
            save.textContent = es().poster_save;
            save.href = dataUrl;
            $('btn-poster-close').textContent = es().poster_close;
            $('ui-poster').hidden = false;
        } catch (e) {
            console.error(e);
            GameEngine.copyText((es().share_text || '') + ' ' + location.href.split('#')[0], es().share_copied_toast);
        } finally {
            btn.disabled = false;
        }
    });

    $('btn-poster-close').addEventListener('click', () => { $('ui-poster').hidden = true; });

    $('btn-replay').addEventListener('click', () => {
        Store.clear();
        location.reload();
    });
}

// ─── 横屏提示、断网提示、启动 ───────────────────────────────────────────────
function bindOrientationWarning() {
    const warning = $('orientation-warning');
    function check() {
        const isLandscape = window.matchMedia('(orientation: landscape)').matches;
        warning.style.display = (isLandscape && window.innerHeight < 500) ? 'flex' : 'none';
        if (Screens.hub.classList.contains('active')) fitHubMap();
    }
    window.addEventListener('resize', check);
    window.addEventListener('orientationchange', check);
    check();
}

function bindOfflineToast() {
    window.addEventListener('offline', () => {
        const msg = (AppState.config && AppState.config.exceptions && AppState.config.exceptions.offline_toast)
            || '网络好像断开了，正在重新连接……';
        GameEngine.showToast(msg);
    });
}

document.addEventListener('DOMContentLoaded', () => {
    Store.load();
    runLoadingScreen();
    $('btn-load-retry').addEventListener('click', runLoadingScreen);
    bindIntro();
    bindPrologueButtons();
    bindStation();
    bindGame();
    bindChallenge();
    bindEnd();
    bindOrientationWarning();
    bindOfflineToast();
});
