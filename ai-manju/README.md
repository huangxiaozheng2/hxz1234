# ManjuFlow 漫剧工坊

**开源的 AI 漫剧工作流：一段故事进去，一条带配音、字幕、运镜的竖屏漫剧出来。**

```
故事 / 小说
   │  LLM 改编（DeepSeek / 通义千问 / 本地 Ollama……）
   ▼
剧本 script.yaml  ── 角色卡、场次、镜头、景别、运镜、台词、旁白（可手改）
   │
   ├─▶ 角色定妆照 ──┐
   ├─▶ 分镜画面 ◀───┘ 角色参考图保证一致性（ComfyUI：SDXL / FLUX / Qwen-Image……）
   ├─▶ 配音 ─────────▶ 时间轴（画面跟着声音走）
   ├─▶ 运镜 / 图生视频（推拉摇移 或 Wan 等图生视频模型）
   ├─▶ 字幕（ASS 烧录 + SRT 外挂）
   └─▶ 合成成片（配乐自动避让人声）+ 分镜表
```

## 特点

- **每一步都可以换模型**：出图、视频、配音、LLM 全部是可插拔的后端，自己在 ComfyUI 里调好的工作流导出就能用，不用改代码。
- **不用显卡也能跑通**：默认“草稿模式”用分镜卡 + 推拉摇移生成**动态分镜**，先看节奏、对台词，满意了再接 AI 画面。
- **剧本是一个可编辑的文件**：LLM 写完你可以改任何一句，再次运行**只重做受影响的部分**（改一句台词只重配那一句、只重做那一个镜头）。
- **画面跟着配音走**：镜头时长由配音长度自动决定，字幕时间轴自动对齐。
- **角色一致性**：固定外貌描述 + 定妆照参考图（IP-Adapter / PuLID 等）+ 固定种子。
- **国内友好**：中文提示词和报错；LLM 支持任何 OpenAI 兼容接口；本地服务自动绕过系统代理。
- **依赖少**：Python 3.10+、ffmpeg、PyYAML、Pillow。

## 快速开始

```bash
# 1. 安装（需要先装好 ffmpeg：https://ffmpeg.org/download.html）
cd ai-manju
pip install -e .                 # 或者 pip install -r requirements.txt，然后用 python -m manjuflow

# 2. 跑通示例（草稿模式，不需要显卡和任何 API Key，约 1 分钟）
manju run examples/demo
#   成片   examples/demo/output/末班车.mp4
#   分镜表 examples/demo/build/storyboard.html

# 3. 检查环境
manju doctor examples/demo
```

## 不想装任何东西？在 GitHub 上一键生成

仓库里带了一个 GitHub Actions 工作流（`.github/workflows/manju.yml`）：剧本用**通义千问**写，画面用**通义万相**画，配音用免费的微软语音。不需要显卡，也不用在自己电脑上装软件。

1. **准备 API Key**：在[阿里云百炼控制台](https://bailian.console.aliyun.com/)创建一个 API Key。
2. **存进仓库**：仓库页面 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**。
   Name 填 `DASHSCOPE_API_KEY`，Secret 填刚才的 Key，点 **Add secret**。Key 只保存在 GitHub 的加密存储里，运行日志里不会显示。
3. **运行**：仓库页面 → **Actions** → 左边选 **AI 漫剧生成** → 右边 **Run workflow**：
   - 「故事内容」粘贴你的故事（留空就用示例《末班车》）；故事很长时，可以先在仓库里新建一个 txt 文件，再填它的路径；
   - 选画风、镜头数量；
   - 第一次可以勾选「草稿模式」，免费看剧本和节奏。
4. **下载**：几分钟后运行变成绿色 ✓，点进去，页面上有分镜表；最下方 **Artifacts** 里下载压缩包，`output` 文件夹里的 mp4 就是成片。

费用：剧本一次调用、每个镜头一张图、每个角色一张定妆照，都按阿里云百炼的价格计费；配音免费。
注意：公开仓库的运行记录和下载文件，其他登录 GitHub 的人也能看到。介意的话可以把仓库设为私有（私有仓库每月有一定的免费运行时长）。

### 做你自己的漫剧

```bash
manju init my-drama --style 国漫厚涂      # 创建项目
#   把故事写进 my-drama/story.txt
#   在 my-drama/project.yaml 里配置 llm（见下文），然后：
export LLM_API_KEY=你的key
manju run my-drama --only script         # 让 AI 改编剧本 → my-drama/script.yaml
#   打开 script.yaml 检查、修改
manju run my-drama                       # 生成全部（已完成的步骤会自动跳过）
manju status my-drama                    # 查看进度
```

## 工作流步骤

| 步骤 | 做什么 | 产物 |
|---|---|---|
| `script` | LLM 把 story.txt 改编成分镜剧本（不合格会自动让它重写） | `script.yaml` |
| `characters` | 为每个角色生成定妆照（已放了自己的图就保留） | `characters/<角色id>.png` |
| `images` | 逐镜头出图：画风 + 景别 + 画面 + 角色外貌 + 参考图 | `build/images/` |
| `voice` | 逐句配音，旁白和每个角色可以用不同音色 | `build/audio/` |
| `timeline` | 按配音长度计算每个镜头时长，拼出整条人声音轨 | `build/timeline.json` |
| `clips` | 让画面动起来：推、拉、摇、移，或调用图生视频模型 | `build/clips/` |
| `subtitles` | 生成带样式的 ASS 字幕和 SRT 外挂字幕 | `build/subtitles.ass` `output/*.srt` |
| `storyboard` | 生成分镜表网页，方便审片和团队沟通 | `build/storyboard.html` |
| `compose` | 拼接片段、混音（配乐自动避让人声）、烧录字幕 | `output/*.mp4` |

常用参数：

```bash
manju run 项目 --only images,clips      # 只跑某几步
manju run 项目 --from voice             # 从某一步往后跑
manju run 项目 --only images --force    # 忽略缓存强制重做
```

想重画某一个镜头：改 `script.yaml` 里那个镜头的 `visual`，或者给它加一个 `seed: 123` 换种子，再运行就只会重画这一张。

## 剧本格式

LLM 生成的和手写的格式相同，完整示例见 [`examples/demo/script.yaml`](examples/demo/script.yaml)。

```yaml
title: 末班车
style: 国漫厚涂               # 画风预设，或者直接写英文提示词
characters:
  - id: linxia               # 英文 id，镜头和台词里用它
    name: 林夏
    gender: female           # 用来挑默认音色
    appearance: 25-year-old Chinese woman, short black bob hair, beige trench coat, silver earrings
    reference: characters/linxia.png   # 可选：你自己准备的定妆照
scenes:
  - id: s1
    location: 深夜地铁站台
    time: night              # night / day / dusk / dawn
    shots:
      - id: s1_01
        shot: 远景            # 大远景 远景 全景 中景 近景 特写 大特写
        camera: push_in      # static push_in pull_out pan_left pan_right tilt_up tilt_down（也可写 推/拉/左摇……）
        description: 空荡荡的站台，只有林夏一个人        # 中文画面说明（分镜表里显示）
        visual: empty subway platform at midnight, ...   # 英文画面提示词（不用写角色外貌，会自动拼接）
        characters: [linxia]
        narration: 凌晨零点十二分，最后一班地铁早就开走了。
        lines:
          - {speaker: linxia, text: 又错过了……, emotion: 疲惫}
        duration: 3          # 可选：最短时长（秒）
        seed: 123            # 可选：换个种子重画
```

## 配置说明（project.yaml）

只需要写和默认值不同的部分，完整默认值见 [`manjuflow/project.py`](manjuflow/project.py) 里的 `DEFAULT_CONFIG`。

### LLM：改编剧本

任何兼容 OpenAI 接口的服务都可以：

```yaml
llm:
  backend: openai
  base_url: https://api.deepseek.com/v1          # DeepSeek
  model: deepseek-chat
  api_key_env: LLM_API_KEY                       # 从环境变量读 Key，不要把 Key 写进文件
  target_shots: 12                               # 大约多少个镜头
```

| 服务 | base_url | model 示例 |
|---|---|---|
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 通义千问（阿里云百炼） | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| Ollama（本地，免 Key） | `http://127.0.0.1:11434/v1` | 你拉取的模型，如 `qwen2.5:14b` |
| vLLM / LM Studio（本地） | `http://127.0.0.1:8000/v1` | 你加载的模型名 |

本地模型如果不支持 JSON 模式，加上 `json_mode: false`。

### 出图：ComfyUI

```yaml
image:
  backend: comfyui
  size: [768, 1344]                      # 9:16；SDXL 推荐这个尺寸，成片时会自动放大
  comfyui:
    url: http://127.0.0.1:8188
    workflow: workflows/sdxl_t2i.json    # 你导出的 API 格式工作流
    params: {ckpt: 你的模型.safetensors, steps: 28, cfg: 6.5}
```

工作流里用 `{{prompt}}` `{{negative}}` `{{seed}}` `{{width}}` `{{height}}` `{{ref_image}}` 等占位符，
详见 [`workflows/README.md`](workflows/README.md)。也可以用 `backend: openai` 接任何兼容 `/images/generations` 的出图服务。

### 出图：通义万相（阿里云百炼，不需要显卡）

```yaml
image:
  backend: dashscope
  size: [768, 1344]                    # 宽高各在 512–1440 之间
  on_content_rejected: placeholder     # 某个镜头没通过内容审核时先用分镜卡代替，不中断整条片子
  dashscope:
    model: wanx2.1-t2i-turbo           # 可换成百炼里你开通的其他通义万相文生图模型
    api_key_env: DASHSCOPE_API_KEY
```

`manju init 项目 --preset dashscope` 会直接生成这套配置（剧本用通义千问 `qwen-plus`，配音用 Edge）。
目前通义万相这条路只靠固定的外貌描述来保持角色一致，同一个角色在不同镜头里可能有差别；对一致性要求高的话，建议用 ComfyUI + 参考图节点。

### 运镜 / 图生视频

```yaml
motion:
  backend: kenburns        # 默认：推拉摇移，CPU 即可，稳定
  zoom: 0.15               # 推拉幅度
```

```yaml
motion:
  backend: comfyui         # 图生视频，例如 Wan2.x
  comfyui:
    url: http://127.0.0.1:8188
    workflow: workflows/my_wan_i2v.json   # 导出你的图生视频工作流，LoadImage 填 {{image}}，帧数填 {{frames}}
    params: {fps: 16, max_frames: 81}
```

生成的视频比镜头短时会定格最后一帧补齐。图生视频很吃显存和时间，建议只给关键镜头用（可以开两个项目配置分别跑）。

### 配音

```yaml
tts:
  backend: edge            # silent / edge / openai / http
  voices:
    narrator: {edge: zh-CN-YunyangNeural}
    linxia: {edge: zh-CN-XiaoxiaoNeural, rate: "-5%"}       # 键名 = 角色 id（或角色的 voice 字段）
    default_female: {edge: zh-CN-XiaoxiaoNeural}
    default_male: {edge: zh-CN-YunxiNeural}
```

- `silent`：不发声，按语速估算时长，用来做动态分镜。
- `edge`：微软 Edge 在线语音，免费，需要 `pip install edge-tts` 并联网。
- 同性别有多个角色时，在 `voices` 里写 `female_pool` / `male_pool` 列表，会按出场顺序给每个角色分配不同的音色（见 `manju init` 生成的配置）。
- `openai`：兼容 `/audio/speech` 的服务（不少本地 TTS 服务都提供这个接口），音色写在 `voices.<角色>.openai`。
- `http`：通用模板，对接自己部署的 GPT-SoVITS、CosyVoice、IndexTTS 等。例如 GPT-SoVITS 的 API（参数请以你部署的版本为准）：

```yaml
tts:
  backend: http
  http:
    url: http://127.0.0.1:9880/tts
    method: POST
    json:
      text: "{{text}}"
      text_lang: zh
      ref_audio_path: "{{ref_audio}}"
      prompt_text: "{{prompt_text}}"
      prompt_lang: zh
  voices:
    linxia: {ref_audio: D:/voices/linxia.wav, prompt_text: 参考音频里说的那句话}
    narrator: {ref_audio: D:/voices/narrator.wav, prompt_text: ……}
```

模板里可以使用 `{{text}}`、`{{emotion}}`，以及 `voices` 里该角色配置的任意字段。

### 字幕与配乐

```yaml
subtitle:
  font: Noto Sans CJK SC     # 系统里装了的中文字体名；Windows 可用 Microsoft YaHei
  fonts_dir: assets/fonts    # 可选：放自己的字体文件
  max_chars: 14              # 每行最多几个字
  show_speaker: false        # 字幕前面加角色名
bgm:
  file: assets/bgm.mp3
  volume: 0.18
  ducking: true              # 有人说话时自动压低音乐
```

## 推荐的开源模型组合

| 环节 | 可选方案（开源/可本地部署） | 备注 |
|---|---|---|
| 剧本 | Qwen、DeepSeek、GLM 等开源模型（Ollama / vLLM 部署），或它们的官方 API | 中文改编能力好 |
| 出图 | SDXL 及动漫融合模型、FLUX.1、Qwen-Image、Kolors、HiDream | 通过 ComfyUI 接入 |
| 角色一致性 | IP-Adapter、PuLID、InstantID、FLUX Redux、角色 LoRA | 工作流里接 `{{ref_image}}` |
| 图生视频 | Wan2.x、HunyuanVideo、LTX-Video | 通过 ComfyUI 接入，显存要求高 |
| 配音 | GPT-SoVITS、CosyVoice、IndexTTS、F5-TTS | 通过 `http` 或 `openai` 后端接入 |

> **商用前请逐一核对模型许可证**：不少模型的权重有非商用或附加条款（例如 FLUX.1-dev、F5-TTS 的预训练权重），以各项目官方说明为准。
> 在国内平台发布 AI 生成的视频，请按平台要求和《人工智能生成合成内容标识办法》标注 AI 生成。

## 开发

```bash
python -m unittest          # 运行测试（用假的 ComfyUI / LLM / TTS 服务，不需要显卡和网络）
```

代码结构：

```
manjuflow/
  cli.py          命令行
  pipeline.py     九个步骤
  schema.py       剧本数据结构与校验
  project.py      项目配置、默认值、画风预设、缓存
  prompts.py      编剧提示词、画面提示词拼装
  timing.py       时间轴
  subtitles.py    ASS / SRT 字幕
  ffmpeg.py       运镜、片段统一、音轨、合成
  backends/       llm / image / motion / tts / comfyui
workflows/        ComfyUI 工作流示例与接入说明
examples/demo/    示例项目《末班车》
tests/            测试
```

加一个新后端：在 `manjuflow/backends/` 里写一个类（出图实现 `generate`，配音实现 `synthesize`，运镜实现 `animate`），
再在 `backends/__init__.py` 的 `REGISTRY` 里登记名字即可。

## 路线图

- [ ] Web 界面：可视化编辑剧本、逐镜头重画和挑图
- [ ] 一个镜头生成多张候选图，挑选后再继续
- [ ] 口型同步（LatentSync / MuseTalk 等）
- [ ] 角色 LoRA 一键训练
- [ ] 多集连续剧：角色库和设定跨集复用

欢迎提 Issue 和 PR。

## 许可证

[MIT](LICENSE)。本项目只包含工作流代码，调用的各个模型和服务遵循它们各自的许可证和使用条款。
