"""Opt-in page selection and numeric updates; no installed-app discovery."""
import asyncio
import http.client
import ipaddress
import json
import math
import socket
import threading
import uuid
from urllib.parse import urlsplit
from pathlib import Path

from .cdp import CDPClient, CDPError
from .account import AccountSource
from .compat import panel_payload, thread_key
from .journal import SessionJournal
from .indexed import DirectorySource, NamedDirectorySource
from .consumer import load_consumer
from .reader import finite_float, reject_constant


_PAGE_BRIDGE = Path(__file__).with_name('page_bridge.js').read_text(encoding='utf-8')


def page_expression(**options):
    return _PAGE_BRIDGE + '(' + json.dumps(options, allow_nan=False) + ')'


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
    """Single owner, explicit target and task files, optional local sidebar adapter.

    panel=True forwards to an existing consumer or an explicitly pinned initializer.
    """
    def __init__(self, origin, page_url, paths=None, *, panel=False, host='explicit', session_root=None, consumer=None, account_cli=None, session_layout=None):
        local_origin(origin)
        if host not in ('explicit', 'codex-sidebar'):
            raise ValueError('invalid host adapter')
        if account_cli is not None and (not isinstance(account_cli, str) or not Path(account_cli).is_absolute() or "\0" in account_cli):
            raise ValueError("invalid account CLI")
        self.account = AccountSource(account_cli) if account_cli is not None else None
        self.host = host
        if type(panel) is not bool:
            raise ValueError('invalid panel mode')
        self.panel = panel
        if consumer is not None and not panel:
            raise ValueError('consumer requires panel mode')
        self.consumer = load_consumer(consumer) if consumer is not None else None
        if not isinstance(page_url, str) or not page_url:
            raise ValueError('explicit page URL required')
        self.origin, self.page_url = origin, page_url
        if (paths is None) == (session_root is None):
            raise ValueError('exactly one session source required')
        if session_layout not in (None, 'codex-rollout') or (session_layout is not None and session_root is None):
            raise ValueError('invalid session layout')
        source_type = NamedDirectorySource if session_layout == 'codex-rollout' else DirectorySource
        self.source = source_type(session_root) if session_root is not None else JournalSource(paths)
        self.client = None
        self.status = 'idle'
        self.owner = uuid.uuid4().hex
        self._published = False
        self._initialized = False

    async def close(self):
        client, self.client = self.client, None
        if client is not None:
            await client.close()

    async def shutdown(self):
        """Release this runner's page state when connected, without reconnecting."""
        result = 'lease_pending' if self._published or self._initialized else 'closed'
        try:
            if (self._published or self._initialized) and self.client is not None:
                released = await self.client.evaluate(page_expression(
                    action='release', expected=self.page_url, owner=self.owner))
                if released is True:
                    self._published = False
                    self._initialized = False
                    result = 'released'
        except CDPError:
            result = 'lease_pending'
        finally:
            try:
                if self.account is not None:
                    await self.account.close()
            finally:
                await self.close()
        return result

    async def step(self):
        try:
            rows = await asyncio.wait_for(asyncio.to_thread(list_pages, self.origin), 5)
            endpoint = select_page(rows, self.page_url, self.origin)
            if self.client is None or self.client.endpoint != endpoint:
                await self.close()
                self.client = CDPClient(endpoint)
                await self.client.__aenter__()
            key = await self.client.evaluate(page_expression(
                action='read', expected=self.page_url, host=self.host))
            key = thread_key(key)
            if key is None:
                if self.panel:
                    await self.client.evaluate(page_expression(
                        action='invalidate', expected=self.page_url, owner=self.owner))
                self.status = 'unselected'
                return self.status
            if self.consumer is not None:
                ready = await self.client.evaluate(page_expression(
                    action='prepare', expected=self.page_url, key=key, host=self.host))
                if ready == 'missing':
                    self._initialized = True
                    ready = await self.client.evaluate(page_expression(
                        action='initialize', expected=self.page_url, key=key, host=self.host,
                        consumer=self.consumer, owner=self.owner))
                if ready != 'ready':
                    self.status = 'changed'
                    return self.status
            payload = self.source.read(key)
            if self.account is not None:
                payload["quota"] = self.account.snapshot()
            applied = await self.client.evaluate(page_expression(
                action='publish', expected=self.page_url, key=key,
                payload=payload, panel=self.panel, host=self.host, owner=self.owner))
            self.status = 'updated' if applied is True else 'changed'
            if applied is True:
                self._published = True
                source_status = getattr(self.source, 'status', 'ok')
                if source_status != 'ok':
                    self.status = 'data_' + source_status
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
            if self.account is not None:
                await self.account.close()
            await self.close()
