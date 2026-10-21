"""测试用的假服务：模拟 ComfyUI、OpenAI 兼容的 LLM 和 TTS 接口。"""
from __future__ import annotations

import io
import json
import struct
import threading
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from PIL import Image


def png_bytes(color=(200, 80, 60), size=(64, 112)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


def wav_bytes(seconds=1.0, rate=24000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<h", 1000) * int(seconds * rate))
    return buf.getvalue()


class FakeServer:
    """记录收到的请求，按 routes 返回结果。routes: {(method, path): handler(req) -> (status, ctype, body)}"""

    def __init__(self):
        self.requests: list[dict] = []
        self.routes: dict = {}
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _handle(self, method):
                u = urlparse(self.path)
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                req = {"method": method, "path": u.path, "query": parse_qs(u.query), "body": body,
                       "headers": dict(self.headers)}
                try:
                    req["json"] = json.loads(body) if body and "json" in self.headers.get("Content-Type", "") else None
                except json.JSONDecodeError:
                    req["json"] = None
                outer.requests.append(req)
                fn = outer.routes.get((method, u.path))
                if fn is None:
                    for (m, prefix), f in outer.routes.items():
                        if m == method and prefix.endswith("*") and u.path.startswith(prefix[:-1]):
                            fn = f
                            break
                if fn is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                status, ctype, out = fn(req)
                if isinstance(out, (dict, list)):
                    out = json.dumps(out).encode()
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

            def do_GET(self):
                self._handle("GET")

            def do_POST(self):
                self._handle("POST")

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def fake_comfyui() -> FakeServer:
    s = FakeServer()
    s.queued = []

    s.routes[("GET", "/system_stats")] = lambda r: (200, "application/json", {"system": {}})
    s.routes[("POST", "/upload/image")] = lambda r: (200, "application/json", {"name": "ref.png", "subfolder": "", "type": "input"})

    def prompt(r):
        s.queued.append(r["json"]["prompt"])
        return 200, "application/json", {"prompt_id": f"p{len(s.queued)}", "number": 1, "node_errors": {}}
    s.routes[("POST", "/prompt")] = prompt

    def history(r):
        pid = r["path"].rsplit("/", 1)[-1]
        return 200, "application/json", {pid: {"status": {"status_str": "success", "completed": True},
                                               "outputs": {"9": {"images": [{"filename": "manju_0001.png", "subfolder": "", "type": "output"}]}}}}
    s.routes[("GET", "/history/*")] = history
    s.routes[("GET", "/view")] = lambda r: (200, "image/png", png_bytes())
    return s
