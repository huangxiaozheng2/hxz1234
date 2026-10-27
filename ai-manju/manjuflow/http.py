"""只用标准库的 HTTP 小工具。

本机或局域网里的服务（ComfyUI、本地 TTS）自动绕过系统代理，
否则开了代理软件时会连不上 127.0.0.1。
"""
from __future__ import annotations

import ipaddress
import json
import time
import uuid
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import ProxyHandler, Request, build_opener

from .util import ManjuError, log


class HTTPStatusError(ManjuError):
    """服务器返回了错误状态码。body 是返回内容，方便按错误码给出提示。"""

    def __init__(self, msg: str, status: int, body: str):
        super().__init__(msg)
        self.status = status
        self.body = body

    def json(self) -> dict:
        try:
            data = json.loads(self.body)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}


class NetworkError(ManjuError):
    """连接失败或超时，通常重试一下就好。"""


def retry(fn, attempts: int = 4, base_delay: float = 2.0, what: str = "请求"):
    """遇到限流（429）、服务器错误（5xx）或网络抖动时，等一会儿再试。"""
    for i in range(attempts):
        try:
            return fn()
        except (HTTPStatusError, NetworkError) as e:
            transient = isinstance(e, NetworkError) or e.status == 429 or e.status >= 500
            if not transient or i == attempts - 1:
                raise
            delay = base_delay * (2 ** i)
            log("http", f"{what}暂时失败，{delay:.0f} 秒后重试（{i + 1}/{attempts - 1}）：{str(e)[:120]}")
            time.sleep(delay)


def is_local(host: str | None) -> bool:
    if not host:
        return False
    if host in ("localhost", "host.docker.internal") or host.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private or ip.is_link_local


def _opener(url: str):
    if is_local(urlparse(url).hostname):
        return build_opener(ProxyHandler({}))
    return build_opener()


def request(method: str, url: str, *, json_body=None, data: bytes | None = None,
            headers: dict | None = None, params: dict | None = None, timeout: float = 60) -> tuple[int, dict, bytes]:
    if params:
        url += ("&" if "?" in url else "?") + urlencode(params)
    hdrs = {"User-Agent": "manjuflow/0.1"}
    hdrs.update(headers or {})
    if json_body is not None:
        data = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = Request(url, data=data, method=method.upper(), headers=hdrs)
    try:
        with _opener(url).open(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:2000]
        shown = url.split("?")[0]   # 签名链接的参数里可能带临时凭证，不打印
        raise HTTPStatusError(f"{method} {shown} 返回 {e.code}：{body[:800]}", e.code, body) from e
    except URLError as e:
        raise NetworkError(f"连接不上 {url.split('?')[0]}：{e.reason}。请确认服务已经启动、地址端口正确。") from e
    except TimeoutError as e:
        raise NetworkError(f"请求 {url.split('?')[0]} 超时（{timeout} 秒）") from e
    except (OSError, HTTPException) as e:   # 读取过程中连接被重置、数据不完整等
        raise NetworkError(f"请求 {url.split('?')[0]} 时连接中断：{e}") from e


def get_json(url: str, **kw):
    _, _, body = request("GET", url, **kw)
    return _loads(body, url)


def post_json(url: str, payload, **kw):
    _, _, body = request("POST", url, json_body=payload, **kw)
    return _loads(body, url)


def _loads(body: bytes, url: str):
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ManjuError(f"{url} 返回的不是 JSON：{body[:200]!r}") from e


def multipart(fields: dict[str, str], files: dict[str, tuple[str, bytes, str]]) -> tuple[bytes, str]:
    """组装 multipart/form-data。files: {字段名: (文件名, 内容, MIME)}"""
    boundary = "----manju" + uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    for k, (name, content, mime) in files.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"; filename="{name}"\r\n'
                     f"Content-Type: {mime}\r\n\r\n".encode() + content + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"
