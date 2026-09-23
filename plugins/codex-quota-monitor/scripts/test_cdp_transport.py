import base64
import hashlib
import json
import socket
import struct
import threading
import unittest

from cdp_transport import CDPClient, CDPError, has_renderer_target, select_target


def server_text(payload, *, final=True, opcode=1):
    data = payload if isinstance(payload, bytes) else payload.encode('utf-8')
    first = (0x80 if final else 0) | opcode
    length = len(data)
    if length < 126:
        return bytes([first, length]) + data
    if length <= 65535:
        return bytes([first, 126]) + struct.pack('!H', length) + data
    return bytes([first, 127]) + struct.pack('!Q', length) + data


def read_client_frame(sock):
    first = sock.recv(2)
    if len(first) != 2:
        raise AssertionError('missing client frame')
    length = first[1] & 0x7f
    if length == 126:
        length = struct.unpack('!H', sock.recv(2))[0]
    elif length == 127:
        length = struct.unpack('!Q', sock.recv(8))[0]
    mask = sock.recv(4)
    payload = bytearray()
    while len(payload) < length:
        payload.extend(sock.recv(length - len(payload)))
    return first[0] & 0x0f, bytes(value ^ mask[index % 4] for index, value in enumerate(payload))


class CDPTransportTests(unittest.TestCase):
    def server(self, handler):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        listener.settimeout(3)
        errors = []

        def run():
            try:
                connection, _ = listener.accept()
                with connection:
                    request = bytearray()
                    while b'\r\n\r\n' not in request:
                        request.extend(connection.recv(4096))
                    headers = request.decode('latin1').split('\r\n')
                    key = next(line.split(':', 1)[1].strip() for line in headers
                                if line.lower().startswith('sec-websocket-key:'))
                    accept = base64.b64encode(hashlib.sha1(
                        (key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode('ascii')).digest()).decode('ascii')
                    connection.sendall((
                        'HTTP/1.1 101 Switching Protocols\r\n'
                        'Upgrade: websocket\r\nConnection: Upgrade\r\n'
                        f'Sec-WebSocket-Accept: {accept}\r\n\r\n').encode('ascii'))
                    handler(connection)
            except BaseException as error:
                errors.append(error)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return listener, thread, errors

    def test_evaluate_handles_events_ping_and_fragmented_response(self):
        def handler(sock):
            _opcode, request = read_client_frame(sock)
            message = json.loads(request.decode('utf-8'))
            sock.sendall(server_text(json.dumps({'method': 'Runtime.consoleAPICalled'})))
            sock.sendall(server_text(b'ping', opcode=9))
            response = json.dumps({'id': message['id'], 'result': {
                'result': {'type': 'string', 'value': 'ok'}}})
            midpoint = len(response) // 2
            sock.sendall(server_text(response[:midpoint], final=False))
            sock.sendall(server_text(response[midpoint:], final=True, opcode=0))

        listener, thread, errors = self.server(handler)
        try:
            client = CDPClient(f'ws://127.0.0.1:{listener.getsockname()[1]}/devtools/page/test', timeout=1)
            try:
                self.assertEqual(client.evaluate('1 + 1'), 'ok')
            finally:
                client.close()
        finally:
            listener.close()
            thread.join(3)
        self.assertEqual(errors, [])

    def test_only_loopback_websocket_targets_are_accepted(self):
        with self.assertRaises(ValueError):
            CDPClient('ws://example.test/devtools/page/nope')
        with self.assertRaises(ValueError):
            CDPClient('ws://127.0.0.1:9222/devtools/page/nope', timeout=0)

    def test_target_selection_keeps_explicit_codex_priority(self):
        target = select_target([
            {'type': 'page', 'url': 'app://-/index.html?initialRoute=home',
             'webSocketDebuggerUrl': 'ws://127.0.0.1:1/no'},
            {'type': 'page', 'title': 'Codex', 'url': 'app://-/index.html',
             'webSocketDebuggerUrl': 'ws://127.0.0.1:2/yes'},
        ])
        self.assertEqual(target['webSocketDebuggerUrl'], 'ws://127.0.0.1:2/yes')

    def test_target_state_matches_launcher_owned_and_ready_rules(self):
        targets = [
            {'type': 'page', 'title': 'Codex', 'url': 'app://-/index.html?initialRoute=home'},
            {'type': 'page', 'title': 'Codex', 'url': 'app://-/index.html?avatar-overlay=true'},
            {'type': 'page', 'title': 'Codex', 'url': 'app://-/index.html'},
        ]
        self.assertTrue(has_renderer_target(targets, 'owned'))
        self.assertTrue(has_renderer_target(targets, 'ready'))
        self.assertFalse(has_renderer_target(targets[:2], 'ready'))
        self.assertFalse(has_renderer_target([{'type': 'page', 'url': 'https://example.com'}], 'owned'))
        with self.assertRaisesRegex(ValueError, '^invalid target state$'):
            has_renderer_target(targets, 'unknown')

    def test_remote_javascript_errors_are_distinguished(self):
        def handler(sock):
            _opcode, request = read_client_frame(sock)
            message = json.loads(request.decode('utf-8'))
            payload = {'id': message['id'], 'result': {'exceptionDetails': {'text': 'failed'}}}
            sock.sendall(server_text(json.dumps(payload)))

        listener, thread, errors = self.server(handler)
        try:
            client = CDPClient(f'ws://localhost:{listener.getsockname()[1]}/devtools/page/test', timeout=1)
            try:
                with self.assertRaisesRegex(CDPError, '^javascript_error$'):
                    client.evaluate('throw Error()')
            finally:
                client.close()
        finally:
            listener.close()
            thread.join(3)
        self.assertEqual(errors, [])


if __name__ == '__main__':
    unittest.main()
