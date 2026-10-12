# 淮安印记 · 运河之都文旅互动小游戏

一个手机网页小游戏：游客扫二维码打开，不用下载 App，也不用登录。跟着吉祥物「小印」走过淮安的四个地方，听故事、答题、集印记，最后获得「淮安文旅达人」徽章。

## 游戏流程

1. **扫码**：`qr.html` 用来在大屏或展板上展示二维码，二维码会根据部署后的网址自动生成。
2. **首页**：点「开始旅程」，幕布拉开。
3. **开场故事**：小印用打字机效果讲故事，配古筝风背景音乐。
4. **旅程地图**：展示四个站点的路线。
5. **四个展区**：左右滑动，或点底部按钮切换。
   - 第一站 · 周恩来故里
   - 第二站 · 河下古镇（吴承恩故居 · 西游记）
   - 第三站 · 清江浦 · 大运河
   - 第四站 · 淮扬美食
   每站都有语音讲解：配置了 mp3 就播放 mp3，没有的话用手机自带的中文语音朗读。
6. **印记挑战**：4 道题。答对有彩纸和音效，答错手机会震动并显示正确答案，每题都有解析。
7. **结束页**：徽章拼合动画、得分、拍立得照片。可以分享（调起系统分享，不支持时复制链接，方便发微信），也可以再玩一次。

## 改内容

**所有文字、题目、图片和音效都在 `flow.yaml` 里**，改这个文件就行，不用动代码。

- 加一个展区：在 `zones` 里照格式加一项，再放一张图片到 `assets/images/`。
- 加讲解音频：在展区的 `slides` 里加一行 `audio: "assets/audio/xxx.mp3"`。
- 改题目：改 `quiz_game.questions`，`correct_index` 从 0 开始数。
- 固定二维码网址：填 `qr_screen.game_url`；不填就自动用当前网址。

## 本地运行

`flow.yaml` 是用 `fetch()` 读取的，所以要起一个本地服务器，不能直接双击打开 `index.html`：

```bash
cd huaian-game
python3 -m http.server 8080
# 手机和电脑连同一个 Wi-Fi，打开 http://电脑IP:8080
```

## 部署

全部是静态文件，不需要构建：

- **Vercel**（本仓库已在用）：部署后访问 `https://你的域名/huaian-game/`，扫码页是 `/huaian-game/qr.html`。
- **GitHub Pages / 任意静态托管**：把 `huaian-game` 文件夹上传即可。

所有依赖（js-yaml、二维码生成库）都放在 `js/vendor/` 里，不依赖境外 CDN，国内网络也能正常打开。

## 图片和音效

图片都是用代码画的扁平风插画，音效和背景音乐是用代码合成的五声音阶拨弦声，可以自由使用和修改。

```bash
python3 art/make_art.py                    # 生成 art/svg/*.svg
node art/render.mjs                        # 渲染成 assets/ 里的 jpg / png（需要 playwright）
python3 art/make_audio.py                  # 合成 assets/audio/*.mp3（需要 numpy、ffmpeg）
```

想换成真实照片的话，直接替换 `assets/images/` 里的同名文件就行。展区图片建议用 5:4 的比例。

## 目录结构

```text
huaian-game/
├── index.html          # 游戏主页面
├── qr.html             # 扫码展示页（大屏 / 展板用）
├── flow.yaml           # 全部内容配置
├── css/                # 样式
├── js/
│   ├── app.js          # 页面流程（状态机）、语音讲解
│   ├── game.js         # 答题、计分、徽章动画、分享
│   └── vendor/         # js-yaml、qrcode-generator（MIT 许可）
├── assets/             # 图片、图标、音效
└── art/                # 生成图片和音效的脚本
```

## 致谢与许可

本项目基于 [moonshineTP/Heritage-Realm](https://github.com/moonshineTP/Heritage-Realm)（「Dấu Di Sản」越南文化遗产互动游戏）改编，原项目使用 Apache License 2.0，见 `LICENSE`。

主要改动：

- 界面和内容全部改成中文，换成淮安四个站点的故事和题目。
- 吉祥物改为「小印」，可在配置里设置名字。
- 新画了全部插画、地图、Logo 和徽章，新合成了音效和背景音乐。
- 新增：没有音频时用系统语音朗读、加载失败重试、断网提示、「下一站」按钮。
- 分享改为系统分享加复制链接，去掉了 Facebook；二维码改为自动生成。
- 第三方库改为本地引入，去掉了原项目的访问统计脚本。
