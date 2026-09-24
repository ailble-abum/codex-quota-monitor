"""Opt-in HTTPS release manifest projection for the V2 diagnostics panel."""

import asyncio
import json
import re
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


CURRENT_VERSION = '2.0.6'
RELEASE_API = 'https://api.github.com/repos/ailble-abum/codex-quota-monitor/releases/latest'
_VERSION = re.compile(r'^[vV]?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:[-+]([0-9A-Za-z.-]+))?$')


def _version(value):
    if not isinstance(value, str) or len(value) > 64:
        return None
    match = _VERSION.fullmatch(value)
    if not match:
        return None
    return tuple(int(match.group(index)) for index in (1, 2, 3)) + (match.group(4) or '',)


def _url(value):
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 32 or c.isspace() for c in value):
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        return None
    return value


def unavailable(code='update_unavailable'):
    return {'status': 'unavailable', 'errorCode': code}


def project(raw, current=CURRENT_VERSION):
    """Project one bounded JSON manifest without exposing unrelated fields."""
    current_version = _version(current)
    if current_version is None or not isinstance(raw, dict):
        return unavailable('invalid_manifest')
    latest = raw.get('latestVersion', raw.get('version', raw.get('tag_name')))
    if isinstance(latest, str) and latest.startswith(('v', 'V')):
        latest = latest[1:]
    latest_version = _version(latest)
    if latest_version is None:
        return unavailable('invalid_manifest')
    link = _url(raw.get('url', raw.get('html_url')))
    if latest_version[:3] <= current_version[:3]:
        return {'status': 'up_to_date', 'currentSemver': '.'.join(map(str, current_version[:3]))}
    result = {'status': 'update_available', 'latestSemver': '.'.join(map(str, latest_version[:3]))}
    if link:
        result['url'] = link
    return result


async def read_manifest(url, *, timeout=5):
    """Fetch only an explicitly configured HTTPS manifest with a small limit."""
    safe = _url(url)
    if safe is None:
        return unavailable('invalid_url')

    def fetch():
        request = Request(safe, headers={'Accept': 'application/json', 'User-Agent': 'codex-quota-monitor-v2'})
        with urlopen(request, timeout=timeout) as response:
            data = response.read(65537)
        if len(data) > 65536:
            raise ValueError('manifest_limit')
        return json.loads(data)

    try:
        return project(await asyncio.to_thread(fetch))
    except (OSError, ValueError, TypeError, json.JSONDecodeError, TimeoutError):
        return unavailable('network')


class UpdateSource:
    """Refresh an optional manifest in the background; never delays token reads."""

    def __init__(self, url=None, *, current=CURRENT_VERSION, interval=6 * 3600, clock=time.monotonic):
        if url is not None and _url(url) is None:
            raise ValueError('invalid update URL')
        if _version(current) is None or type(interval) not in (int, float) or interval <= 0:
            raise ValueError('invalid update settings')
        self.url, self.current, self.interval, self.clock = url, current, interval, clock
        self.value = {'status': 'not_configured'} if url is None else {'status': 'checking'}
        self.task, self.next_read = None, float('-inf')

    async def refresh(self):
        value = await read_manifest(self.url)
        current = _version(self.current)
        if value.get('status') == 'up_to_date' and current is not None:
            value['currentSemver'] = '.'.join(map(str, current[:3]))
        self.value = value

    def snapshot(self, force=False):
        if (self.url is not None and (force or self.clock() >= self.next_read) and
                (self.task is None or self.task.done())):
            self.next_read = self.clock() + self.interval
            self.value = {'status': 'checking'}
            self.task = asyncio.create_task(self.refresh())
        return dict(self.value)

    async def close(self):
        if self.task is not None:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
