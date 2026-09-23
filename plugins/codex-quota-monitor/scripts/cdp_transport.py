"""Small, local-only Chrome DevTools Protocol transport.

This module owns the synchronous wire adapter used by the launcher. It accepts
only loopback WebSocket targets and keeps the protocol implementation bounded;
no page code or renderer selectors live here.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import ipaddress
import json
import math
import secrets
import socket
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


MAX_MESSAGE = 8 * 1024 * 1024
MAX_HEADERS = 16 * 1024


class CDPError(RuntimeError):
    pass


def _valid_timeout(value: Any) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value > 0)


def _loopback(host: str) -> bool:
    if host.lower() == 'localhost':
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _endpoint(url: str) -> tuple[urllib.parse.SplitResult, str, int]:
    if (not isinstance(url, str) or not url.isascii() or
            any(char.isspace() or ord(char) < 32 for char in url)):
        raise ValueError('unsupported websocket endpoint')
    parsed = urllib.parse.urlsplit(url)
    host = parsed.hostname
    try:
        port = parsed.port
    except ValueError:
        port = None
    if (parsed.scheme != 'ws' or not host or not _loopback(host) or port is None
            or not 1 <= port <= 65535 or parsed.username is not None
            or parsed.password is not None or parsed.fragment):
        raise ValueError('unsupported websocket endpoint')
    return parsed, host, port


def _read_exact(sock: socket.socket, size: int) -> bytes:
    if size < 0 or size > MAX_MESSAGE:
        raise CDPError('frame_too_large')
    result = bytearray()
    while len(result) < size:
        chunk = sock.recv(size - len(result))
        if not chunk:
            raise CDPError('connection_closed')
        result.extend(chunk)
    return bytes(result)


def _headers(sock: socket.socket) -> bytes:
    data = bytearray()
    while b'\r\n\r\n' not in data:
        if len(data) >= MAX_HEADERS:
            raise CDPError('handshake_too_large')
        chunk = sock.recv(min(4096, MAX_HEADERS - len(data)))
        if not chunk:
            raise CDPError('handshake_closed')
        data.extend(chunk)
    return bytes(data)


def _open(url: str, timeout: float) -> socket.socket:
    parsed, host, port = _endpoint(url)
    sock = socket.create_connection((host, port), timeout=timeout)
    try:
        key = base64.b64encode(secrets.token_bytes(16)).decode('ascii')
        path = parsed.path or '/'
        if parsed.query:
            path += '?' + parsed.query
        host_header = parsed.hostname or host
        if ':' in host_header and not host_header.startswith('['):
            host_header = '[' + host_header + ']'
        request = (
            f'GET {path} HTTP/1.1\r\n'
            f'Host: {host_header}:{port}\r\n'
            'Upgrade: websocket\r\n'
            'Connection: Upgrade\r\n'
            f'Sec-WebSocket-Key: {key}\r\n'
            'Sec-WebSocket-Version: 13\r\n\r\n').encode('ascii')
        sock.sendall(request)
        response = _headers(sock)
        head = response.split(b'\r\n\r\n', 1)[0].split(b'\r\n')
        if not head or len(head[0].split()) < 2 or head[0].split()[1] != b'101':
            raise CDPError('handshake_rejected')
        fields = {}
        for line in head[1:]:
            if b':' not in line:
                continue
            name, value = line.split(b':', 1)
            fields[name.decode('latin1').strip().lower()] = value.decode('latin1').strip()
        accept = base64.b64encode(hashlib.sha1(
            (key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode('ascii')).digest()).decode('ascii')
        if (fields.get('upgrade', '').lower() != 'websocket' or
                'upgrade' not in fields.get('connection', '').lower() or
                fields.get('sec-websocket-accept') != accept):
            raise CDPError('handshake_rejected')
        return sock
    except BaseException:
        sock.close()
        raise


def _client_frame(payload: bytes, opcode: int) -> bytes:
    if len(payload) > MAX_MESSAGE:
        raise CDPError('frame_too_large')
    header = bytearray([0x80 | (opcode & 0x0F)])
    length = len(payload)
    if length < 126:
        header.append(0x80 | length)
    elif length <= 0xFFFF:
        header.extend((0x80 | 126,))
        header.extend(struct.pack('!H', length))
    else:
        header.extend((0x80 | 127,))
        header.extend(struct.pack('!Q', length))
    mask = secrets.token_bytes(4)
    return bytes(header) + mask + bytes(value ^ mask[index % 4] for index, value in enumerate(payload))


def _server_frame(sock: socket.socket) -> tuple[bool, int, bytes]:
    first = _read_exact(sock, 2)
    fin, reserved, opcode = bool(first[0] & 0x80), first[0] & 0x70, first[0] & 0x0F
    masked, length = bool(first[1] & 0x80), first[1] & 0x7F
    if reserved or (opcode >= 8 and (not fin or length > 125)):
        raise CDPError('protocol_error')
    if length == 126:
        length = struct.unpack('!H', _read_exact(sock, 2))[0]
    elif length == 127:
        value = struct.unpack('!Q', _read_exact(sock, 8))[0]
        if value & (1 << 63):
            raise CDPError('protocol_error')
        length = value
    if length > MAX_MESSAGE or masked:
        raise CDPError('protocol_error')
    return fin, opcode, _read_exact(sock, length)


def _send(sock: socket.socket, payload: bytes, opcode: int = 1) -> None:
    sock.sendall(_client_frame(payload, opcode))


def _message(sock: socket.socket, deadline: float) -> bytes:
    fragments = None
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Timed out waiting for CDP response')
        sock.settimeout(remaining)
        try:
            fin, opcode, payload = _server_frame(sock)
        except socket.timeout as error:
            raise TimeoutError('Timed out waiting for CDP response') from error
        if opcode == 8:
            try:
                _send(sock, payload[:125], 8)
            except OSError:
                pass
            raise CDPError('connection_closed')
        if opcode == 9:
            _send(sock, payload, 10)
            continue
        if opcode == 10:
            continue
        if opcode == 1:
            if fragments is not None:
                raise CDPError('protocol_error')
            fragments = [payload]
            if fin:
                return b''.join(fragments)
            continue
        if opcode == 0 and fragments is not None:
            fragments.append(payload)
            if fin:
                return b''.join(fragments)
            continue
        raise CDPError('protocol_error')


class CDPClient:
    def __init__(self, websocket_url: str, timeout: float = 5.0) -> None:
        if not _valid_timeout(timeout):
            raise ValueError('invalid timeout')
        self.websocket_url = websocket_url
        self.timeout = float(timeout)
        self.sock = _open(websocket_url, self.timeout)
        self.next_id = 0

    def close(self) -> None:
        sock, self.sock = self.sock, None
        if sock is None:
            return
        try:
            sock.close()
        except OSError:
            pass

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.sock is None:
            raise CDPError('connection_closed')
        if not isinstance(method, str) or not method:
            raise ValueError('invalid method')
        self.next_id += 1
        request_id = self.next_id
        encoded = json.dumps({'id': request_id, 'method': method, 'params': params or {}},
                             separators=(',', ':'), allow_nan=False).encode('utf-8')
        if len(encoded) > MAX_MESSAGE:
            raise CDPError('request_too_large')
        try:
            _send(self.sock, encoded)
            deadline = time.monotonic() + self.timeout
            while True:
                response = json.loads(_message(self.sock, deadline).decode('utf-8'))
                if not isinstance(response, dict):
                    raise CDPError('protocol_error')
                if response.get('id') != request_id:
                    continue
                if 'error' in response:
                    raise CDPError('remote_error')
                result = response.get('result')
                return result if isinstance(result, dict) else {}
        except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as error:
            self.close()
            raise CDPError('protocol_error') from error

    def evaluate(self, expression: str) -> Any:
        result = self.call('Runtime.evaluate', {
            'expression': expression, 'awaitPromise': True,
            'returnByValue': True, 'userGesture': False})
        if 'exceptionDetails' in result:
            raise CDPError('javascript_error')
        remote = result.get('result')
        if not isinstance(remote, dict):
            raise CDPError('protocol_error')
        return remote.get('value')


def devtools_targets(port: int, timeout: float = 2.0) -> list[dict[str, Any]]:
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('invalid port')
    if not _valid_timeout(timeout):
        raise ValueError('invalid timeout')
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/json', timeout=timeout) as response:
            raw = response.read(MAX_MESSAGE + 1)
    except (urllib.error.URLError, OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CDPError(f'Cannot connect to the Codex renderer on 127.0.0.1:{port}. '
                       'Launch ChatGPT or Codex with --remote-debugging-port first.') from error
    if len(raw) > MAX_MESSAGE:
        raise CDPError('target_list_too_large')
    try:
        data = json.loads(raw.decode('utf-8'))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise CDPError('invalid_target_list') from error
    if not isinstance(data, list) or len(data) > 256:
        raise CDPError('Invalid DevTools target list')
    return [item for item in data if isinstance(item, dict)]


def is_codex_renderer_target(target: dict[str, Any]) -> bool:
    title = str(target.get('title') or '').lower()
    url = str(target.get('url') or '').lower()
    return url.startswith('app://') and (
        'codex' in title or 'chatgpt' in title or
        url.startswith('app://codex/') or url.startswith('app://-/index.html'))


def has_renderer_target(targets: list[dict[str, Any]], mode: str = 'owned') -> bool:
    if mode not in {'owned', 'ready'}:
        raise ValueError('invalid target state')
    for target in targets:
        if not isinstance(target, dict) or target.get('type') != 'page':
            continue
        if not is_codex_renderer_target(target):
            continue
        if mode == 'owned':
            return True
        decoded = urllib.parse.unquote(str(target.get('url') or '').lower())
        if 'initialroute=' not in decoded and 'avatar-overlay' not in decoded:
            return True
    return False


def target_score(target: dict[str, Any]) -> int:
    title = str(target.get('title') or '').lower()
    url = str(target.get('url') or '').lower()
    decoded = urllib.parse.unquote(url)
    score = 100 if url.startswith('app://') else 0
    if url in {'app://-/index.html', 'app://codex/index.html'}:
        score += 200
    if 'initialroute=' in decoded:
        score -= 100
    if 'avatar-overlay' in decoded:
        score -= 300
    if 'codex' in title or 'codex' in url:
        score += 40
    if 'chatgpt' in title:
        score += 30
    return score


def select_target(targets: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [target for target in targets
                  if isinstance(target, dict) and target.get('type') == 'page'
                  and isinstance(target.get('webSocketDebuggerUrl'), str)
                  and is_codex_renderer_target(target) and target_score(target) > 0]
    for target in sorted(candidates, key=target_score, reverse=True):
        return target
    raise CDPError('No debuggable Codex renderer target found')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    state = commands.add_parser('target-state')
    state.add_argument('port', type=int)
    state.add_argument('mode', choices=('owned', 'ready'))
    args = parser.parse_args(argv)
    try:
        return 0 if has_renderer_target(devtools_targets(args.port, timeout=0.6), args.mode) else 1
    except (CDPError, ValueError):
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
