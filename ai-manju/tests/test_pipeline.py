"""端到端测试：用假服务跑通 LLM 写剧本、ComfyUI 出图、TTS 配音，以及草稿模式出成片。"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from manjuflow import ffmpeg
from manjuflow.pipeline import run
from manjuflow.project import Project
from tests.fakes import FakeServer, fake_comfyui, wav_bytes

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "examples" / "demo"


def make_project(tmp: Path, overrides: dict, with_script=True) -> Project:
    shutil.copy(DEMO / "project.yaml", tmp / "project.yaml")
    shutil.copy(DEMO / "story.txt", tmp / "story.txt")
    if with_script:
        shutil.copy(DEMO / "script.yaml", tmp / "script.yaml")
    cfg = yaml.safe_load((tmp / "project.yaml").read_text(encoding="utf-8"))
    for k, v in overrides.items():
        cfg.setdefault(k, {}).update(v) if isinstance(v, dict) else cfg.__setitem__(k, v)
    cfg["video"] = {"resolution": [270, 480], "fps": 12, "min_shot_seconds": 1.0}
    (tmp / "project.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    return Project(tmp)


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="manju-test-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_draft_mode_end_to_end_and_cache(self):
        p = make_project(self.tmp, {})
        run(p)
        out = p.output / "末班车.mp4"
        self.assertTrue(out.exists())
        tl = json.loads((p.build / "timeline.json").read_text(encoding="utf-8"))
        self.assertAlmostEqual(ffmpeg.probe_duration(out), tl["total"], delta=0.3)
        self.assertTrue((p.output / "末班车.srt").exists())
        self.assertIn("s2_05", (p.build / "storyboard.html").read_text(encoding="utf-8"))

        # 改一句台词：只重配这一句，只重做这一个镜头
        script = (self.tmp / "script.yaml").read_text(encoding="utf-8")
        (self.tmp / "script.yaml").write_text(script.replace("又错过了……", "又又又错过了，今天第三次了……"), encoding="utf-8")
        before = {f.name: f.stat().st_mtime_ns for f in (p.build / "clips").glob("*.mp4")}
        p2 = Project(self.tmp)
        run(p2, ["voice", "timeline", "clips"])
        after = {f.name: f.stat().st_mtime_ns for f in (p2.build / "clips").glob("*.mp4")}
        changed = sorted(k for k in after if after[k] != before[k])
        self.assertEqual(changed, ["s1_02.mp4"])

    def test_llm_writes_script_with_retry(self):
        llm = FakeServer()
        good = yaml.safe_load((DEMO / "script.yaml").read_text(encoding="utf-8"))
        replies = iter(['{"title": "缺镜头", "scenes": []}', "```json\n" + json.dumps(good, ensure_ascii=False) + "\n```"])
        llm.routes[("POST", "/v1/chat/completions")] = lambda r: (
            200, "application/json", {"choices": [{"message": {"content": next(replies)}}]})
        try:
            p = make_project(self.tmp, {"llm": {"backend": "openai", "base_url": llm.url + "/v1", "model": "fake"}},
                             with_script=False)
            run(p, ["script"])
        finally:
            llm.close()
        self.assertEqual(Project(self.tmp).script().title, "末班车")
        calls = [r for r in llm.requests if r["path"].endswith("/chat/completions")]
        self.assertEqual(len(calls), 2)                               # 第一次不合格，自动重试
        self.assertIn("scenes 不能为空", calls[1]["json"]["messages"][-1]["content"])
        self.assertEqual(calls[0]["json"]["response_format"], {"type": "json_object"})

    def test_comfyui_images_with_reference(self):
        comfy = fake_comfyui()
        wf = {"1": {"class_type": "LoadImage", "inputs": {"image": "{{ref_image}}"}},
              "2": {"class_type": "KSampler", "inputs": {"seed": "{{seed}}", "steps": "{{steps}}"}},
              "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "{{prompt}}"}},
              "9": {"class_type": "SaveImage", "inputs": {}}}
        (self.tmp / "wf.json").write_text(json.dumps(wf), encoding="utf-8")
        try:
            p = make_project(self.tmp, {"image": {"backend": "comfyui", "comfyui": {
                "url": comfy.url, "workflow": "wf.json", "params": {"steps": 9}}}})
            # 先给角色放定妆照（用户自己准备的），工作流需要 {{ref_image}}
            (self.tmp / "characters").mkdir()
            from tests.fakes import png_bytes
            for cid in ("linxia", "conductor"):
                (self.tmp / "characters" / f"{cid}.png").write_bytes(png_bytes())
            script = (self.tmp / "script.yaml").read_text(encoding="utf-8")
            # s1_03 / s2_02 没有角色，工作流又要求参考图，应当给出清楚的报错；这里先给它们加上角色
            script = script.replace("        visual: an old-fashioned", "        characters: [linxia]\n        visual: an old-fashioned")
            script = script.replace("        visual: a little girl", "        characters: [linxia]\n        visual: a little girl")
            (self.tmp / "script.yaml").write_text(script, encoding="utf-8")
            run(Project(self.tmp), ["characters", "images"])
        finally:
            comfy.close()
        self.assertEqual(len(comfy.queued), 9)
        first = comfy.queued[0]
        self.assertEqual(first["1"]["inputs"]["image"], "ref.png")
        self.assertEqual(first["2"]["inputs"]["steps"], 9)
        self.assertIsInstance(first["2"]["inputs"]["seed"], int)
        self.assertIn("Chinese donghua style", first["3"]["inputs"]["text"])
        self.assertIn("short black bob hair", first["3"]["inputs"]["text"])   # 角色外貌自动拼进提示词
        self.assertEqual(len(list((self.tmp / "build" / "images").glob("*.png"))), 9)

    def test_http_tts_template(self):
        tts = FakeServer()
        tts.routes[("POST", "/tts")] = lambda r: (200, "audio/wav", wav_bytes(0.8))
        try:
            p = make_project(self.tmp, {"tts": {"backend": "http", "http": {
                "url": tts.url + "/tts", "json": {"text": "{{text}}", "ref_audio_path": "{{ref}}", "lang": "zh"}},
                "voices": {"narrator": {"ref": "n.wav"}, "default_female": {"ref": "f.wav"}, "default_male": {"ref": "m.wav"}}}})
            run(p, ["voice"])
        finally:
            tts.close()
        bodies = [r["json"] for r in tts.requests]
        self.assertEqual(len(bodies), 10)
        self.assertEqual(bodies[0], {"text": "凌晨零点十二分，最后一班地铁早就开走了。", "ref_audio_path": "n.wav", "lang": "zh"})
        self.assertIn({"text": "姑娘，上车吧。", "ref_audio_path": "m.wav", "lang": "zh"}, bodies)   # 老列车员按性别用男声
        self.assertAlmostEqual(ffmpeg.wav_duration(p.build / "audio" / "s1_02_l1.wav"), 0.8, delta=0.02)

    def test_comfyui_image_to_video(self):
        comfy = fake_comfyui()
        clip = self.tmp / "gen.mp4"
        ffmpeg.run(["-f", "lavfi", "-i", "testsrc=size=320x576:rate=16", "-t", "2", "-pix_fmt", "yuv420p", str(clip)])
        comfy.routes[("GET", "/view")] = lambda r: (200, "video/mp4", clip.read_bytes())
        comfy.routes[("GET", "/history/*")] = lambda r: (200, "application/json", {r["path"].rsplit("/", 1)[-1]: {
            "status": {"status_str": "success", "completed": True},
            "outputs": {"20": {"gifs": [{"filename": "wan_00001.mp4", "subfolder": "", "type": "output"}]}}}})
        wf = {"1": {"class_type": "LoadImage", "inputs": {"image": "{{image}}"}},
              "2": {"class_type": "WanImageToVideo", "inputs": {"length": "{{frames}}", "width": "{{gen_w}}"}}}
        (self.tmp / "i2v.json").write_text(json.dumps(wf), encoding="utf-8")
        try:
            p = make_project(self.tmp, {"motion": {"backend": "comfyui", "comfyui": {
                "url": comfy.url, "workflow": "i2v.json", "params": {"gen_w": 480, "fps": 16}}}})
            run(p, ["characters", "images", "voice", "timeline", "clips"])
        finally:
            comfy.close()
        tl = {s["id"]: s["duration"] for s in json.loads((p.build / "timeline.json").read_text(encoding="utf-8"))["shots"]}
        self.assertEqual(len(comfy.queued), 9)
        for wfq in comfy.queued:
            self.assertEqual((wfq["2"]["inputs"]["length"] - 1) % 4, 0)       # 帧数是 4n+1
            self.assertLessEqual(wfq["2"]["inputs"]["length"], 81)
        # 生成的视频只有 2 秒，要定格补齐到镜头时长，并统一成成片尺寸
        out = p.build / "clips" / "s1_04.mp4"
        self.assertAlmostEqual(ffmpeg.probe_duration(out), tl["s1_04"], delta=0.15)

    def test_dashscope_images(self):
        ds = FakeServer()
        tasks, submits = {}, []
        state = {"throttled": False}
        from tests.fakes import png_bytes

        def submit(r):
            submits.append(r)
            if not state["throttled"]:            # 第一次请求模拟限流，应当自动重试
                state["throttled"] = True
                return 429, "application/json", {"code": "Throttling", "message": "Requests rate limit exceeded"}
            if "FORBIDDEN" in r["json"]["input"]["prompt"]:
                return 400, "application/json", {"code": "DataInspectionFailed",
                                                 "message": "Input data may contain inappropriate content."}
            tid = f"t{len(tasks) + 1}"
            tasks[tid] = 0
            return 200, "application/json", {"output": {"task_id": tid, "task_status": "PENDING"}}

        def task(r):
            tid = r["path"].rsplit("/", 1)[-1]
            tasks[tid] += 1
            if tasks[tid] < 2:
                return 200, "application/json", {"output": {"task_id": tid, "task_status": "RUNNING"}}
            return 200, "application/json", {"output": {"task_id": tid, "task_status": "SUCCEEDED",
                                                        "results": [{"url": f"{ds.url}/result/{tid}.png?Expires=1&Signature=x"}]}}

        ds.routes[("POST", "/api/v1/services/aigc/text2image/image-synthesis")] = submit
        ds.routes[("GET", "/api/v1/tasks/*")] = task
        ds.routes[("GET", "/result/*")] = lambda r: (200, "image/png", png_bytes())
        try:
            p = make_project(self.tmp, {"image": {"backend": "dashscope", "on_content_rejected": "placeholder",
                                                  "dashscope": {"base_url": ds.url, "api_key": "sk-test", "poll_interval": 0}}})
            script = (self.tmp / "script.yaml").read_text(encoding="utf-8")
            (self.tmp / "script.yaml").write_text(script.replace("light streaks, mysterious mist", "FORBIDDEN"), encoding="utf-8")
            with mock.patch("time.sleep"):
                run(Project(self.tmp), ["characters", "images"])
        finally:
            ds.close()
        ok = [r for r in submits if "FORBIDDEN" not in r["json"]["input"]["prompt"]]
        self.assertEqual(len(ok), 1 + 2 + 8)          # 1 次被限流的重试 + 2 张定妆照 + 8 张正常镜头
        body = ok[-1]["json"]
        self.assertEqual(body["model"], "wanx2.1-t2i-turbo")
        self.assertEqual(body["parameters"]["size"], "768*1344")
        self.assertFalse(body["parameters"]["prompt_extend"])
        self.assertLess(body["parameters"]["seed"], 2147483647)
        headers = {k.lower(): v for k, v in ok[-1]["headers"].items()}   # HTTP 头不区分大小写
        self.assertEqual(headers.get("x-dashscope-async"), "enable")
        self.assertEqual(headers.get("authorization"), "Bearer sk-test")
        self.assertEqual(len(list((self.tmp / "build" / "images").glob("*.png"))), 9)   # 被拒的镜头也有分镜卡
        warnings = json.loads((self.tmp / "build" / "warnings.json").read_text(encoding="utf-8"))
        self.assertEqual([w["item"] for w in warnings], ["镜头 s1_03"])
        cache = json.loads((self.tmp / "build" / ".cache.json").read_text(encoding="utf-8"))
        self.assertFalse(any(k.endswith("s1_03.png") for k in cache))   # 没记缓存，下次会重试

    def test_dashscope_rejection_stops_by_default(self):
        ds = FakeServer()
        ds.routes[("POST", "/api/v1/services/aigc/text2image/image-synthesis")] = lambda r: (
            401, "application/json", {"code": "InvalidApiKey", "message": "Invalid API-key provided."})
        try:
            p = make_project(self.tmp, {"image": {"backend": "dashscope",
                                                  "dashscope": {"base_url": ds.url, "api_key": "bad"}}})
            from manjuflow.util import ManjuError
            with self.assertRaises(ManjuError) as cm:
                run(p, ["characters"])
        finally:
            ds.close()
        self.assertIn("API Key 无效", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
