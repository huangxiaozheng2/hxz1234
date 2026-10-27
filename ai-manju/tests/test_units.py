import unittest

from manjuflow.backends.comfyui import fill_template
from manjuflow.backends.llm import extract_json
from manjuflow.schema import parse_script, voice_items
from manjuflow.subtitles import _ass_time, build_ass, build_srt
from manjuflow.timing import build_timeline
from manjuflow.util import ManjuError, wrap_cjk

SCRIPT = {
    "title": "测试",
    "characters": [{"id": "a", "name": "阿甲", "gender": "male"}, {"id": "b", "name": "阿乙"}],
    "scenes": [{"id": "s1", "time": "night", "shots": [
        {"id": "s1_01", "camera": "推", "visual": "x", "narration": "旁白一句", "lines": [{"speaker": "a", "text": "你好"}]},
        {"id": "s1_02", "visual": "y", "duration": 4},
        {"id": "s1_03", "visual": "z", "lines": [{"speaker": "b", "text": "再见"}, {"speaker": "narrator", "text": "完"}]},
    ]}],
}


class SchemaTest(unittest.TestCase):
    def test_parse_and_aliases(self):
        s = parse_script(SCRIPT)
        self.assertEqual(len(s.all_shots()), 3)
        self.assertEqual(s.all_shots()[0].camera, "push_in")
        self.assertEqual(s.all_shots()[0].scene.time, "night")
        keys = [v.key for v in voice_items(s)]
        self.assertEqual(keys, ["s1_01_n", "s1_01_l1", "s1_03_l1", "s1_03_l2"])

    def test_errors_listed_together(self):
        bad = {"characters": [{"id": "a b"}], "scenes": [{"shots": [
            {"id": "x", "camera": "spin", "characters": ["ghost"], "lines": [{"speaker": "who", "text": ""}]}]}]}
        with self.assertRaises(ManjuError) as cm:
            parse_script(bad)
        msg = str(cm.exception)
        for part in ["a b", "spin", "ghost", "who", "text 不能为空", "visual"]:
            self.assertIn(part, msg)


class TimelineTest(unittest.TestCase):
    def test_durations_follow_voice(self):
        s = parse_script(SCRIPT)
        cfg = {"head_pad": 0.5, "tail_pad": 0.5, "line_gap": 0.2, "min_shot_seconds": 2}
        tl = build_timeline(s, {"s1_01_n": 2.0, "s1_01_l1": 1.0, "s1_03_l1": 0.3, "s1_03_l2": 0.3}, cfg)
        a, b, c = tl["shots"]
        self.assertAlmostEqual(a["duration"], 0.5 + 2.0 + 0.2 + 1.0 + 0.5)
        self.assertEqual(a["items"][1]["start"], 0.5 + 2.0 + 0.2)
        self.assertAlmostEqual(b["duration"], 4)          # 没有台词，用指定时长
        self.assertAlmostEqual(c["duration"], 2)          # 台词很短，用最短时长
        self.assertAlmostEqual(tl["total"], a["duration"] + 4 + 2)


class SubtitleTest(unittest.TestCase):
    def test_wrap_and_times(self):
        self.assertEqual(wrap_cjk("一二三四五，六七", 5), ["一二三四五，", "六七"])   # 标点不放行首
        self.assertEqual(_ass_time(3725.456), "1:02:05.46")
        s = parse_script(SCRIPT)
        tl = build_timeline(s, {"s1_01_n": 1, "s1_01_l1": 1, "s1_03_l1": 1, "s1_03_l2": 1}, {})
        ass = build_ass(s, tl, {"max_chars": 14}, (1080, 1920))
        self.assertIn("PlayResY: 1920", ass)
        self.assertEqual(ass.count("Dialogue:"), 4)
        self.assertIn(",Narration,", ass)
        srt = build_srt(s, tl, {"show_speaker": True})
        self.assertIn("阿甲：你好", srt)


class TemplateTest(unittest.TestCase):
    def test_typed_and_inline(self):
        wf = {"1": {"inputs": {"seed": "{{seed}}", "text": "a {{prompt}} b", "list": ["{{w}}", 2]}}}
        out = fill_template(wf, {"seed": 42, "prompt": "cat", "w": 768})
        self.assertEqual(out["1"]["inputs"]["seed"], 42)
        self.assertEqual(out["1"]["inputs"]["text"], "a cat b")
        self.assertEqual(out["1"]["inputs"]["list"], [768, 2])

    def test_missing(self):
        with self.assertRaises(ManjuError) as cm:
            fill_template({"x": "{{ckpt}} {{lora}}"}, {})
        self.assertIn("ckpt, lora", str(cm.exception))

    def test_extract_json(self):
        self.assertEqual(extract_json('<think>嗯</think>好的：\n```json\n{"a": 1}\n```'), {"a": 1})
        with self.assertRaises(ManjuError):
            extract_json("没有 JSON")


class VoiceTest(unittest.TestCase):
    def test_pools_and_overrides(self):
        from manjuflow.backends.tts import assign_voices
        from manjuflow.schema import Character
        chars = [Character("a", "甲", gender="female"), Character("b", "乙", gender="女"),
                 Character("c", "丙", gender="female"), Character("d", "丁", gender="male"),
                 Character("e", "戊", gender="female", voice="special")]
        voices = {"narrator": {"edge": "N"}, "special": {"edge": "S"},
                  "female_pool": [{"edge": "F1"}, {"edge": "F2"}], "male_pool": [{"edge": "M1"}]}
        got = {k: v["edge"] for k, v in assign_voices(chars, voices).items()}
        self.assertEqual(got, {"narrator": "N", "a": "F1", "b": "F2", "c": "F1", "d": "M1", "e": "S"})


if __name__ == "__main__":
    unittest.main()
