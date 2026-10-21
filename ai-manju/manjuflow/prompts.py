"""给 LLM 的编剧提示词，以及画面提示词的拼装。"""
from __future__ import annotations

from .schema import Character, Script, Shot

SCRIPT_SYSTEM = """你是一名专业的 AI 漫剧编剧兼分镜师，擅长把小说改编成竖屏短剧。
你只输出一个 JSON 对象，不要输出任何解释或 Markdown。"""

SCRIPT_USER = """请把下面的故事改编成一集 AI 漫剧的分镜剧本。

要求：
1. 竖屏 9:16 画面，总共约 {target_shots} 个镜头，单集约 {target_seconds} 秒。
2. 开头 3 秒内必须有钩子（冲突、悬念或反差），结尾留下悬念或情绪高点。
3. 每个镜头只表现一个动作或一个情绪点；台词口语化，每句不超过 20 个字，每个镜头最多 2 句台词。
4. 景别要有变化，可选：大远景、远景、全景、中景、近景、特写、大特写。
5. 运镜 camera 只能从这些里选：static, push_in, pull_out, pan_left, pan_right, tilt_up, tilt_down。
6. visual 字段用英文写画面提示词：构图、动作、表情、环境、光线。不要写角色名字，也不要写外貌（系统会自动拼接角色外貌）。
7. 角色 appearance 用英文写稳定的外貌特征：年龄、性别、发型发色、脸部特征、服装、标志性配饰。所有镜头都会复用这段描述，所以要具体、固定。
8. 角色 id 用小写英文或拼音；旁白放在 narration 字段，不要算作角色。
9. 忠于原著情节，可以删减合并，但不要编造原著没有的重大情节。

输出 JSON 结构：
{{
  "title": "剧名",
  "logline": "一句话简介",
  "characters": [
    {{"id": "linxia", "name": "林夏", "gender": "female", "appearance": "25-year-old woman, short black bob hair, ...", "voice_hint": "青年女声，温柔偏冷"}}
  ],
  "scenes": [
    {{
      "id": "s1", "location": "深夜地铁站台", "time": "night", "mood": "孤独、悬疑",
      "shots": [
        {{
          "id": "s1_01", "shot": "远景", "camera": "push_in",
          "description": "中文画面说明",
          "visual": "English image prompt ...",
          "characters": ["linxia"],
          "narration": "旁白，可以为空字符串",
          "lines": [{{"speaker": "linxia", "text": "台词", "emotion": "焦急"}}]
        }}
      ]
    }}
  ]
}}

故事如下：
<<<
{story}
>>>"""

SCRIPT_FIX = "你上次的输出有问题：\n{error}\n请修正后重新输出完整的 JSON。"


def build_image_prompt(style: str, shot: Shot, chars: list[Character]) -> str:
    """风格 + 景别 + 画面 + 角色外貌 + 场景氛围。"""
    parts = [style, shot.shot_prompt, shot.visual or shot.description]
    for c in chars:
        if c.appearance:
            parts.append(f"{c.appearance}" if len(chars) == 1 else f"({c.appearance})")
    sc = shot.scene
    if sc is not None:
        if sc.time:
            parts.append({"night": "night scene", "day": "daytime", "dusk": "dusk, golden hour",
                          "dawn": "dawn, early morning light"}.get(sc.time, sc.time))
    parts.append("vertical composition, masterpiece, best quality")
    return ", ".join(p.strip().strip(",") for p in parts if p and p.strip())


def build_portrait_prompt(style: str, c: Character) -> str:
    return ", ".join(p for p in [
        style, "character design sheet, full body, front view, standing, neutral expression",
        c.appearance, "plain light grey background, masterpiece, best quality"] if p)


def describe(script: Script) -> str:
    return f"《{script.title}》 {len(script.characters)} 个角色，{len(script.scenes)} 场，{len(script.all_shots())} 个镜头"
