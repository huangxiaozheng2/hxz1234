"""只用标准库的 HTTP 小工具。

本机或局域网里的服务（ComfyUI、本地 TTS）自动绕过系统代理，
否则开了代理软件时会连不上 127.0.0.1。
"""
from __future__ import annotations

import ipaddress
import json
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import ProxyHandler, Request, build_opener

from .util import ManjuError


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
        body = e.read().decode("utf-8", "replace")[:800]
        raise ManjuError(f"{method} {url} 返回 {e.code}：{body}") from e
    except URLError as e:
        raise ManjuError(f"连接不上 {url}：{e.reason}。请确认服务已经启动、地址端口正确。") from e
    except TimeoutError as e:
        raise ManjuError(f"请求 {url} 超时（{timeout} 秒）") from e


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
