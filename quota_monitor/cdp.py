"""Optional explicit-endpoint CDP client."""
import asyncio
import ipaddress
import json
import logging
import math
import re
import socket
from urllib.parse import urlsplit

from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from .reader import finite_float, reject_constant

_QUIET = logging.Logger('quota-monitor-cdp-private')
_QUIET.disabled = True


class CDPError(Exception):
    pass


class CDPClient:
    def __init__(self, endpoint, *, timeout=2.0, max_message=1048576):
        try:
            url = urlsplit(endpoint)
            address = ipaddress.ip_address(url.hostname)
            valid = (isinstance(endpoint, str) and endpoint.isascii()
                     and not any(c.isspace() or ord(c) < 32 for c in endpoint)
                     and url.scheme == 'ws' and address.is_loopback
                     and url.port is not None and url.port > 0
                     and url.username is None and not url.query and not url.fragment
                     and re.fullmatch(r'/devtools/page/[A-Za-z0-9_-]+', url.path))
        except (ValueError, TypeError, AttributeError):
            valid = False
        if not valid:
            raise ValueError('invalid local page endpoint')
        if (type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0
                or type(max_message) is not int or max_message < 1):
            raise ValueError('invalid connection limits')
        self.endpoint, self.address, self.port = endpoint, address, url.port
        self.timeout, self.max_message = timeout, max_message
        self.connection = None
        self._busy = False
        self._next_id = 0

    async def __aenter__(self):
        if self.connection is not None:
            raise CDPError('already_connected')
        sock = socket.socket(socket.AF_INET6 if self.address.version == 6 else socket.AF_INET,
                             socket.SOCK_STREAM)
        sock.setblocking(False)

        async def open_local():
            await asyncio.get_running_loop().sock_connect(sock, (str(self.address), self.port))
            # A preconnected socket also makes websockets reject HTTP redirects.
            return await connect(self.endpoint, sock=sock, proxy=None, compression=None,
                                 open_timeout=self.timeout, close_timeout=0.2,
                                 ping_interval=None, max_size=self.max_message, max_queue=4,
                                 logger=_QUIET)
        try:
            self.connection = await asyncio.wait_for(open_local(), self.timeout)
        except asyncio.CancelledError:
            sock.close()
            raise
        except (OSError, ValueError, WebSocketException, asyncio.TimeoutError):
            sock.close()
            raise CDPError('unavailable') from None
        return self

    async def close(self):
        connection, self.connection = self.connection, None
        if connection is not None:
            await connection.close()

    async def __aexit__(self, *exception):
        await self.close()

    async def evaluate(self, expression):
        if self.connection is None:
            raise CDPError('disconnected')
        if self._busy:
            raise CDPError('busy')
        if not isinstance(expression, str):
            raise ValueError('expression must be text')
        self._next_id += 1
        request_id = self._next_id
        request = json.dumps({'id': request_id, 'method': 'Runtime.evaluate', 'params': {
            'expression': expression, 'returnByValue': True, 'awaitPromise': True,
            'timeout': self.timeout * 1000}}, allow_nan=False)
        if len(request.encode('utf-8')) > self.max_message:
            raise CDPError('request_too_large')

        async def exchange():
            await self.connection.send(request)
            for _ in range(128):
                raw = await self.connection.recv()
                if not isinstance(raw, str):
                    raise CDPError('protocol_error')
                response = json.loads(raw, parse_constant=reject_constant, parse_float=finite_float)
                if not isinstance(response, dict):
                    raise CDPError('protocol_error')
                if 'id' not in response and isinstance(response.get('method'), str):
                    continue
                if type(response.get('id')) is not int:
                    raise CDPError('protocol_error')
                if response['id'] != request_id:
                    continue
                if 'error' in response:
                    raise CDPError('remote_error')
                result = response.get('result')
                if not isinstance(result, dict):
                    raise CDPError('protocol_error')
                if 'exceptionDetails' in result:
                    raise CDPError('javascript_error')
                remote = result.get('result')
                if not isinstance(remote, dict):
                    raise CDPError('protocol_error')
                if 'value' in remote:
                    return remote['value']
                if remote.get('type') == 'undefined':
                    return None
                raise CDPError('unsupported_value')
            raise CDPError('message_limit')

        self._busy = True
        try:
            return await asyncio.wait_for(exchange(), self.timeout)
        except asyncio.CancelledError:
            await self.close()
            raise
        except asyncio.TimeoutError:
            await self.close()
            raise CDPError('timeout') from None
        except (OSError, WebSocketException):
            await self.close()
            raise CDPError('disconnected') from None
        except (ValueError, RecursionError):
            await self.close()
            raise CDPError('protocol_error') from None
        except CDPError:
            await self.close()
            raise
        finally:
            self._busy = False
