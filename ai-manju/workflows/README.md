# ComfyUI 工作流接入说明

ManjuFlow 不绑定任何一个模型。你在 ComfyUI 里搭好、调好的工作流，导出后加上占位符就能接进来，
换模型、换采样器、加 LoRA 都不用改代码。

## 1. 导出 API 格式

1. ComfyUI 设置里打开“开发者模式”（Dev mode）。
2. 菜单里选“导出（API）”/ “Save (API Format)”，得到一个 JSON 文件。
   注意：普通“保存”得到的是界面格式（里面有 `nodes` 和 `links`），ManjuFlow 读不了，会提示你重新导出。

## 2. 把要变化的输入改成占位符

用文本编辑器打开 JSON，把每个镜头都不同的值改成 `{{占位符}}`：

```json
"6": {"class_type": "CLIPTextEncode", "inputs": {"text": "{{prompt}}", "clip": ["4", 1]}}
```

整段字符串只有一个占位符时，会按原类型替换（`"{{seed}}"` 会变成数字）。

### 出图工作流（image.comfyui）可用的占位符

| 占位符 | 内容 |
|---|---|
| `{{prompt}}` | 自动拼好的正向提示词（画风 + 景别 + 画面 + 角色外貌） |
| `{{negative}}` | 负向提示词（project.yaml 的 `negative_prompt`） |
| `{{seed}}` | 每个镜头固定的种子，重跑画面不变 |
| `{{width}}` `{{height}}` | `image.size` |
| `{{ref_image}}` | 镜头里第一个角色的定妆照（自动上传），用于 IP-Adapter / PuLID / InstantID / Redux 等角色一致性节点 |
| 其他任意名字 | 从 `image.comfyui.params` 里取，例如 `{{ckpt}}`、`{{steps}}`、`{{lora}}` |

### 图生视频工作流（motion.comfyui）可用的占位符

| 占位符 | 内容 |
|---|---|
| `{{image}}` | 这个镜头的分镜图（自动上传），接到 LoadImage 节点的 `image` |
| `{{prompt}}` `{{negative}}` `{{seed}}` | 同上，可作为运动描述 |
| `{{width}}` `{{height}}` | 成片分辨率（可以在 params 里另设 `gen_width` 之类的值自己用） |
| `{{frames}}` | 按镜头时长算出的帧数（按 4n+1 取整，上限 `params.max_frames`，默认 81） |
| `{{fps}}` | 生成帧率（`params.fps`，默认 16） |
| `{{seconds}}` | 镜头时长 |

生成的视频不够镜头时长时，会自动定格最后一帧补齐，并统一成成片的分辨率和帧率。

## 3. 内置示例

- `sdxl_t2i.json`：只用 ComfyUI 自带节点的 SDXL 文生图。需要的参数：`ckpt`（模型文件名）、`steps`、`cfg`。
  把 `ckpt` 换成你 `models/checkpoints` 里的任意 SD1.5 / SDXL 模型（包括各种动漫风格的融合模型）即可。

## 4. 角色一致性建议

漫剧最难的是同一个角色每个镜头长得一样。由易到难：

1. **固定外貌描述**：剧本里 `appearance` 写得越具体越稳定（发型、发色、服装、配饰），每个镜头都会自动拼进去。
2. **定妆照 + 参考图节点**：先运行 `characters` 步骤生成定妆照（或者把你满意的图放进 `characters/角色id.png`），
   再在工作流里加 `LoadImage`（image 填 `{{ref_image}}`）接到 IP-Adapter / PuLID / InstantID 等节点。
3. **角色 LoRA**：用定妆照训练角色 LoRA，在工作流里用 `LoraLoader` 加载，文件名写成 `{{lora}}` 放进 params。
