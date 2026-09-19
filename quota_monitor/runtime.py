"""Opt-in page selection and numeric updates; no installed-app discovery."""
import asyncio
import http.client
import ipaddress
import json
import math
import socket
import threading
from urllib.parse import urlsplit

from .cdp import CDPClient, CDPError
from .compat import panel_payload, thread_key
from .journal import SessionJournal
from .reader import finite_float, reject_constant


def local_origin(value):
    try:
        url = urlsplit(value)
        address = ipaddress.ip_address(url.hostname)
        if (not isinstance(value, str) or not value.isascii()
                or any(c.isspace() or ord(c) < 32 for c in value)
                or url.scheme != 'http' or not address.is_loopback
                or url.port is None or url.port < 1 or url.path not in ('', '/')
                or url.username is not None or url.query or url.fragment):
            raise ValueError()
        return str(address), url.port
    except (ValueError, TypeError, AttributeError):
        raise ValueError('invalid local discovery origin') from None


def list_pages(origin):
    """One bounded direct HTTP request, without proxies or redirects."""
    host, port = local_origin(origin)
    connection = http.client.HTTPConnection(host, port, timeout=2)
    timer = None
    try:
        connection.connect()
        sock = connection.sock
        def expire():
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        timer = threading.Timer(2, expire)
        timer.daemon = True
        timer.start()
        connection.request('GET', '/json/list')
        response = connection.getresponse()
        if response.status != 200:
            raise CDPError('discovery_unavailable')
        body = response.read(1048577)
        if len(body) > 1048576:
            raise CDPError('target_limit')
        rows = json.loads(body, parse_constant=reject_constant, parse_float=finite_float)
        if not isinstance(rows, list) or len(rows) > 256 or any(not isinstance(r, dict) for r in rows):
            raise CDPError('invalid_targets')
        return rows
    except (OSError, http.client.HTTPException, ValueError, RecursionError):
        raise CDPError('discovery_unavailable') from None
    finally:
        if timer is not None:
            timer.cancel()
        connection.close()


def select_page(rows, page_url, origin):
    host, port = local_origin(origin)
    matches = [row for row in rows if row.get('type') == 'page' and row.get('url') == page_url]
    if len(matches) != 1:
        raise CDPError('ambiguous' if matches else 'not_found')
    row = matches[0]
    try:
        client = CDPClient(row.get('webSocketDebuggerUrl'))
        if ((str(client.address), client.port) != (host, port)
                or urlsplit(client.endpoint).path != '/devtools/page/' + row.get('id', '')):
            raise ValueError()
    except (ValueError, TypeError):
        raise CDPError('invalid_target') from None
    return client.endpoint


class JournalSource:
    """Explicit task-to-file mapping, cached incremental readers; no tree scans."""
    def __init__(self, paths):
        if any(thread_key(key) != key or key is None for key in paths):
            raise ValueError('invalid task mapping')
        self.journals = {key: SessionJournal(path) for key, path in paths.items()}

    def read(self, key):
        journal = self.journals.get(key)
        readings = {key: journal.poll()} if journal else {}
        return panel_payload(readings, key)


class UpdateLoop:
    """Single owner. The selected page must opt in via __quotaMonitorV2Thread.

    __quotaMonitorV2Snapshot is a read-only expiring numeric bridge, not a UI.
    Host task/DOM integration is deliberately outside this contract.
    """
    def __init__(self, origin, page_url, paths):
        local_origin(origin)
        if not isinstance(page_url, str) or not page_url:
            raise ValueError('explicit page URL required')
        self.origin, self.page_url = origin, page_url
        self.source = JournalSource(paths)
        self.client = None
        self.status = 'idle'

    async def close(self):
        client, self.client = self.client, None
        if client is not None:
            await client.close()

    async def step(self):
        try:
            rows = await asyncio.wait_for(asyncio.to_thread(list_pages, self.origin), 5)
            endpoint = select_page(rows, self.page_url, self.origin)
            if self.client is None or self.client.endpoint != endpoint:
                await self.close()
                self.client = CDPClient(endpoint)
                await self.client.__aenter__()
            expected = json.dumps(self.page_url)
            key = await self.client.evaluate(
                'location.href === ' + expected + ' ? window.__quotaMonitorV2Thread : null')
            key = thread_key(key)
            payload = self.source.read(key)
            # JSON is data only. Recheck page/task in the same JS turn as assignment.
            expression = '''(() => {
                const expected = %s, key = %s, data = %s;
                const current = () => {
                    const t = window.__quotaMonitorV2Thread;
                    return typeof t === 'string' ? t.replace(/^local:/, '') : null;
                };
                if (location.href !== expected || current() !== key) return false;
                const deadline = performance.now() + 120000;
                Object.defineProperty(window, '__quotaMonitorV2Snapshot', {
                    configurable: true,
                    get: () => location.href === expected && current() === key &&
                        performance.now() < deadline ? data : null
                });
                return true;
            })()''' % (expected, json.dumps(key), json.dumps(payload, allow_nan=False))
            applied = await self.client.evaluate(expression)
            self.status = 'updated' if applied is True else 'changed'
        except (CDPError, asyncio.TimeoutError) as error:
            await self.close()
            self.status = str(error) if isinstance(error, CDPError) else 'discovery_timeout'
        except BaseException:
            await self.close()
            raise
        return self.status

    async def run(self, *, interval=1.0):
        if type(interval) not in (int, float) or not math.isfinite(interval) or interval <= 0:
            raise ValueError('invalid update interval')
        try:
            while True:
                await self.step()
                await asyncio.sleep(interval)
        finally:
            await self.close()
