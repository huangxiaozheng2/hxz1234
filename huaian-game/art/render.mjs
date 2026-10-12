// 把 art/svg/*.svg 渲染成 assets/ 里用的图片。
// 用法：node art/render.mjs（需要已安装 playwright 和 Chromium）
import { createRequire } from 'module';
import { readFileSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const require = createRequire(import.meta.url);
let playwright;
try {
    playwright = require('playwright');
} catch {
    playwright = require(join(process.env.NODE_PATH || '/opt/node22/lib/node_modules', 'playwright'));
}

const here = dirname(fileURLToPath(import.meta.url));
const assets = join(here, '..', 'assets');

// [源文件, 输出文件, 宽, 高, 格式]
const jobs = [
    ['intro-bg.svg', 'images/intro-bg.jpg', 1080, 1920, 'jpeg'],
    ['zone-01.svg',  'images/zone-01.jpg',  1200, 960,  'jpeg'],
    ['zone-02.svg',  'images/zone-02.jpg',  1200, 960,  'jpeg'],
    ['zone-03.svg',  'images/zone-03.jpg',  1200, 960,  'jpeg'],
    ['zone-04.svg',  'images/zone-04.jpg',  1200, 960,  'jpeg'],
    ['map.svg',      'images/map.png',      1024, 1536, 'png'],
    ['logo.svg',     'icons/logo.png',      512,  512,  'png'],
    ['badge.svg',    'icons/badge.png',     512,  512,  'png'],
];

const browser = await playwright.chromium.launch();
const page = await browser.newPage();
for (const [src, out, w, h, type] of jobs) {
    const svg = readFileSync(join(here, 'svg', src), 'utf8');
    await page.setViewportSize({ width: w, height: h });
    await page.setContent(
        `<html><body style="margin:0;background:transparent">${svg}</body></html>`
    );
    await page.screenshot({
        path: join(assets, out),
        type,
        quality: type === 'jpeg' ? 82 : undefined,
        omitBackground: type === 'png',
        clip: { x: 0, y: 0, width: w, height: h },
    });
    console.log('✓', out);
}
await browser.close();
