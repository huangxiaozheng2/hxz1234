// js/poster.js —— 生成分享海报（canvas → png）
// 海报内容：标题、昵称、称号徽章、总分、四枚印章、二维码。

const Poster = {
    W: 750,
    H: 1250,

    _img(src) {
        return new Promise(resolve => {
            const i = new Image();
            i.onload = () => resolve(i);
            i.onerror = () => resolve(null);
            i.src = src;
        });
    },

    _font(size, weight = 400, serif = false) {
        const fam = serif
            ? '"Songti SC","STSong","Noto Serif SC","SimSun",serif'
            : '"PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans SC","WenQuanYi Zen Hei",sans-serif';
        return `${weight} ${size}px ${fam}`;
    },

    _seal(ctx, cx, cy, size, chars, on) {
        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(on ? -0.06 : 0);
        ctx.fillStyle = on ? '#9e2b25' : '#d9cbb0';
        ctx.beginPath();
        ctx.roundRect(-size / 2, -size / 2, size, size, size * 0.12);
        ctx.fill();
        ctx.strokeStyle = on ? '#f6e7c8' : '#efe4cf';
        ctx.lineWidth = 3;
        ctx.strokeRect(-size / 2 + 8, -size / 2 + 8, size - 16, size - 16);
        ctx.fillStyle = on ? '#f6e7c8' : '#c4b393';
        ctx.font = this._font(size * 0.3, 700);
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        const q = size * 0.2;
        [...chars].slice(0, 4).forEach((ch, i) => {
            ctx.fillText(ch, (i % 2 ? q : -q), (i < 2 ? -q : q) + 2);
        });
        ctx.restore();
    },

    _qr(ctx, url, x, y, size) {
        if (typeof qrcode !== 'function') return;
        const qr = qrcode(0, 'M');
        qr.addData(url);
        qr.make();
        const n = qr.getModuleCount();
        const cell = size / (n + 4);
        ctx.fillStyle = '#fff';
        ctx.fillRect(x, y, size, size);
        ctx.fillStyle = '#2c1508';
        for (let r = 0; r < n; r++) {
            for (let c = 0; c < n; c++) {
                if (qr.isDark(r, c)) ctx.fillRect(x + (c + 2) * cell, y + (r + 2) * cell, Math.ceil(cell), Math.ceil(cell));
            }
        }
    },

    // data: { nickname, rankTitle, rankMessage, badge, score, stations:[{stamp, stars}], quizText, url }
    async render(data) {
        const { W, H } = this;
        const canvas = document.createElement('canvas');
        canvas.width = W;
        canvas.height = H;
        const ctx = canvas.getContext('2d');
        const [hero, badge, logo] = await Promise.all([
            this._img('assets/images/intro-bg.jpg'),
            this._img(data.badge),
            this._img('assets/icons/logo.png'),
        ]);

        // 底色与边框
        ctx.fillStyle = '#f3e6cc';
        ctx.fillRect(0, 0, W, H);

        // 顶部插画（取首页背景的上半部分）
        if (hero) {
            const sh = hero.width * (430 / W);
            ctx.drawImage(hero, 0, 380, hero.width, sh, 0, 0, W, 430);
        }
        const fade = ctx.createLinearGradient(0, 280, 0, 430);
        fade.addColorStop(0, 'rgba(243,230,204,0)');
        fade.addColorStop(1, 'rgba(243,230,204,1)');
        ctx.fillStyle = fade;
        ctx.fillRect(0, 280, W, 150);

        ctx.strokeStyle = '#6b3a22';
        ctx.lineWidth = 6;
        ctx.strokeRect(18, 18, W - 36, H - 36);
        ctx.lineWidth = 2;
        ctx.strokeRect(32, 32, W - 64, H - 64);

        // 标题
        if (logo) ctx.drawImage(logo, 60, 56, 92, 92);
        ctx.fillStyle = '#fff';
        ctx.shadowColor = 'rgba(0,0,0,0.35)';
        ctx.shadowBlur = 10;
        ctx.font = this._font(60, 900);
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';
        ctx.fillText('淮安印记', 170, 92);
        ctx.font = this._font(26, 500);
        ctx.fillText('运河之都 · 文旅闯关', 172, 140);
        ctx.shadowBlur = 0;

        // 昵称
        ctx.textAlign = 'center';
        ctx.fillStyle = '#2c1508';
        ctx.font = this._font(34, 700);
        const who = (data.nickname || '').trim();
        ctx.fillText(who ? `${who} 的淮安之旅` : '我的淮安之旅', W / 2, 380);

        // 徽章与称号
        if (badge) ctx.drawImage(badge, W / 2 - 130, 410, 260, 260);
        ctx.fillStyle = '#9e2b25';
        ctx.font = this._font(58, 900, true);
        ctx.fillText(`「${data.rankTitle}」`, W / 2, 712);
        ctx.fillStyle = '#7a5238';
        ctx.font = this._font(28, 500);
        ctx.fillText(`总分 ${data.score}　·　${data.quizText}`, W / 2, 768);

        // 四枚印章
        const n = data.stations.length;
        const gap = (W - 120) / n;
        data.stations.forEach((s, i) => {
            const cx = 60 + gap * (i + 0.5);
            this._seal(ctx, cx, 880, 118, s.stamp, s.stars > 0);
            ctx.fillStyle = '#d4a73a';
            ctx.font = this._font(30, 700);
            ctx.fillText('★'.repeat(s.stars) + '☆'.repeat(3 - s.stars), cx, 972);
        });

        // 底部：寄语 + 二维码
        ctx.fillStyle = '#ead6b6';
        ctx.fillRect(32, 1020, W - 64, H - 1052);
        ctx.textAlign = 'left';
        ctx.fillStyle = '#2c1508';
        ctx.font = this._font(30, 700);
        ctx.fillText('一起来集淮安印章！', 64, 1080);
        ctx.fillStyle = '#7a5238';
        ctx.font = this._font(24, 400);
        this._wrap(ctx, data.rankMessage, 64, 1126, 430, 36);
        ctx.font = this._font(22, 500);
        ctx.fillText('长按识别二维码，开始闯关', 64, 1196);
        this._qr(ctx, data.url, W - 64 - 170, 1040, 170);

        return canvas.toDataURL('image/png');
    },

    _wrap(ctx, text, x, y, maxW, lh) {
        let line = '';
        for (const ch of text || '') {
            if (ctx.measureText(line + ch).width > maxW) {
                ctx.fillText(line, x, y);
                line = ch;
                y += lh;
            } else {
                line += ch;
            }
        }
        if (line) ctx.fillText(line, x, y);
    },
};
