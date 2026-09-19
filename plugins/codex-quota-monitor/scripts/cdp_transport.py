"""Minimal Chrome DevTools Protocol transport used by the overlay."""
from __future__ import annotations

import base64
import json
import os
import secrets
import socket
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class CDPError(RuntimeError):
    pass


class CDPClient:
    def __init__(self, websocket_url: str, timeout: float = 5.0) -> None:
        self.websocket_url = websocket_url
        self.timeout = timeout
        self.sock = self._connect(websocket_url)
        self.next_id = 1

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        message_id = self.next_id
        self.next_id += 1
        self._send_json({"id": message_id, "method": method, "params": params or {}})
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            message = self._recv_json()
            if message.get("id") != message_id:
                continue
            if "error" in message:
                raise CDPError(str(message["error"]))
            return message.get("result") or {}
        raise TimeoutError(f"Timed out waiting for CDP response to {method}")

    def evaluate(self, expression: str) -> Any:
        result = self.call("Runtime.evaluate", {"expression": expression, "awaitPromise": True,
                                                 "returnByValue": True, "userGesture": False})
        remote = result.get("result") or {}
        if "exceptionDetails" in result:
            raise CDPError(str(result["exceptionDetails"]))
        return remote.get("value")

    def _connect(self, websocket_url: str) -> socket.socket:
        parsed = urllib.parse.urlparse(websocket_url)
        if parsed.scheme != "ws" or not parsed.hostname:
            raise ValueError(f"Unsupported websocket URL: {websocket_url}")
        port = parsed.port or 80
        sock = socket.create_connection((parsed.hostname, port), timeout=self.timeout)
        sock.settimeout(self.timeout)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        path = parsed.path or "/"
        if parsed.query:
            path += f"?{parsed.query}"
        request = (f"GET {path} HTTP/1.1\r\nHost: {parsed.hostname}:{port}\r\n"
                   "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                   f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        sock.sendall(request.encode("ascii"))
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            raise CDPError(f"WebSocket handshake failed: {response[:200]!r}")
        return sock

    def _send_json(self, payload: dict[str, Any]) -> None:
        self.sock.sendall(masked_websocket_frame(json.dumps(payload, separators=(",", ":")).encode("utf-8")))

    def _recv_json(self) -> dict[str, Any]:
        while True:
            opcode, payload = read_websocket_frame(self.sock)
            if opcode == 1:
                data = json.loads(payload.decode("utf-8"))
                if isinstance(data, dict):
                    return data
            if opcode == 9:
                self.sock.sendall(masked_websocket_frame(payload, opcode=10))
            if opcode == 8:
                raise CDPError("WebSocket closed by target")


def masked_websocket_frame(payload: bytes, opcode: int = 1) -> bytes:
    header = bytearray([0x80 | (opcode & 0x0F)])
    length = len(payload)
    if length < 126:
        header.append(0x80 | length)
    elif length < 65536:
        header.append(0x80 | 126)
        header.extend(struct.pack("!H", length))
    else:
        header.append(0x80 | 127)
        header.extend(struct.pack("!Q", length))
    mask = secrets.token_bytes(4)
    masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    return bytes(header) + mask + masked


def read_websocket_frame(sock: socket.socket) -> tuple[int, bytes]:
    first = read_exact(sock, 2)
    opcode = first[0] & 0x0F
    masked = bool(first[1] & 0x80)
    length = first[1] & 0x7F
    if length == 126:
        length = struct.unpack("!H", read_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", read_exact(sock, 8))[0]
    mask = read_exact(sock, 4) if masked else b""
    payload = read_exact(sock, length)
    if masked:
        payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    return opcode, payload


def read_exact(sock: socket.socket, length: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < length:
        chunk = sock.recv(length - len(chunks))
        if not chunk:
            raise CDPError("Unexpected WebSocket EOF")
        chunks.extend(chunk)
    return bytes(chunks)


def devtools_targets(port: int) -> list[dict[str, Any]]:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=2) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        raise CDPError(f"Cannot connect to the Codex renderer on 127.0.0.1:{port}. "
                       "Launch ChatGPT or Codex with --remote-debugging-port first.") from exc
    return data if isinstance(data, list) else []


def select_target(targets: list[dict[str, Any]]) -> dict[str, Any]:
    pages = [target for target in targets if target.get("type") == "page"
             and is_codex_renderer_target(target) and target_score(target) > 0]
    for target in sorted(pages, key=target_score, reverse=True):
        if target.get("webSocketDebuggerUrl"):
            return target
    raise CDPError("No debuggable Codex renderer target found")


def is_codex_renderer_target(target: dict[str, Any]) -> bool:
    title = str(target.get("title") or "").lower()
    url = str(target.get("url") or "").lower()
    return url.startswith("app://") and ("codex" in title or "chatgpt" in title
                                         or url.startswith("app://codex/")
                                         or url.startswith("app://-/index.html"))


def target_score(target: dict[str, Any]) -> int:
    title = str(target.get("title") or "").lower()
    url = str(target.get("url") or "").lower()
    decoded_url = urllib.parse.unquote(url)
    score = 100 if url.startswith("app://") else 0
    if url in {"app://-/index.html", "app://codex/index.html"}:
        score += 200
    if "initialroute=" in decoded_url:
        score -= 100
    if "avatar-overlay" in decoded_url:
        score -= 300
    if "codex" in title or "codex" in url:
        score += 40
    if "chatgpt" in title:
        score += 30
    return score
