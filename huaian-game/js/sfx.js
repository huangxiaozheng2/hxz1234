// js/sfx.js —— 音效
// 1. 配置里的 mp3 音效（答对 / 答错 / 过关）
// 2. 小游戏里的短音效，用 Web Audio 现场合成，不需要额外文件

let isMuted = false; // 全局静音状态

const SFX = {
    _pool: {},
    _ctx: null,

    init(config) {
        const paths = (config.project && config.project.global_audio) || {};
        for (const [key, src] of Object.entries(paths)) {
            if (!src || this._pool[key]) continue;
            const a = new Audio(src);
            a.preload = 'auto';
            this._pool[key] = a;
        }
    },

    // 必须在用户点击时调用一次，手机浏览器才允许之后播放声音
    unlock() {
        try {
            if (!this._ctx) {
                const Ctx = window.AudioContext || window.webkitAudioContext;
                if (Ctx) this._ctx = new Ctx();
            }
            if (this._ctx && this._ctx.state === 'suspended') this._ctx.resume();
        } catch (e) { /* 不支持就算了 */ }
        Object.values(this._pool).forEach(a => {
            a.play().then(() => { a.pause(); a.currentTime = 0; }).catch(() => {});
        });
    },

    play(key) {
        if (isMuted) return;
        const a = this._pool[key];
        if (!a) return;
        try {
            a.currentTime = 0;
            a.play().catch(() => {});
        } catch (e) { /* 忽略 */ }
    },

    // 合成一个短音：freq 起始频率，to 结束频率，dur 秒，type 波形
    tone(freq, dur = 0.12, { to = freq, type = 'sine', vol = 0.25, delay = 0 } = {}) {
        if (isMuted || !this._ctx) return;
        try {
            const ctx = this._ctx;
            const t0 = ctx.currentTime + delay;
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = type;
            osc.frequency.setValueAtTime(freq, t0);
            osc.frequency.exponentialRampToValueAtTime(Math.max(30, to), t0 + dur);
            gain.gain.setValueAtTime(0.0001, t0);
            gain.gain.exponentialRampToValueAtTime(vol, t0 + 0.01);
            gain.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
            osc.connect(gain).connect(ctx.destination);
            osc.start(t0);
            osc.stop(t0 + dur + 0.02);
        } catch (e) { /* 忽略 */ }
    },

    // 常用音效
    hit()     { this.tone(520, 0.09, { to: 260, type: 'square', vol: 0.12 }); },
    good()    { this.tone(880, 0.08, { vol: 0.2 }); this.tone(1320, 0.12, { vol: 0.18, delay: 0.07 }); },
    bad()     { this.tone(220, 0.25, { to: 110, type: 'sawtooth', vol: 0.1 }); },
    tick()    { this.tone(1000, 0.04, { vol: 0.08 }); },
    collect() { this.tone(660, 0.07, { vol: 0.18 }); this.tone(990, 0.09, { vol: 0.15, delay: 0.05 }); },
    crash()   { this.tone(160, 0.35, { to: 60, type: 'sawtooth', vol: 0.18 }); },
    stamp()   { this.tone(140, 0.18, { to: 70, type: 'triangle', vol: 0.4 }); },
};
