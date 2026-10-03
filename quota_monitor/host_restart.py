"""User-requested Codex restart with the owned monitor kept available."""
import asyncio
from pathlib import Path
import re
import time

from .account import resolve_cli
from .host_follow import HostFollower
from .cdp import CDPError
from .service import LABEL, MENU_LABEL


def host_app(cli):
    path = Path(resolve_cli(cli))
    layouts = ('codex', 'codex-cli/CodexCLI.app/Contents/MacOS/codex', 'codex-cli/bin/codex')
    for resources in path.parents:
        if (resources.name == 'Resources' and resources.parent.name == 'Contents'
                and resources.parent.parent.suffix == '.app'
                and path.relative_to(resources).as_posix() in layouts):
            return str(resources.parent.parent)
    raise ValueError('unsupported host')


class HostRestarter:
    def __init__(self, cli, origin, page_url, service, *, follower=None,
                 probe=None, sleeper=time.sleep, clock=time.monotonic):
        from .runtime import local_origin
        address, port = local_origin(origin)
        if address != '127.0.0.1' or not service._owned():
            raise ValueError('restart unavailable')
        self.follower = follower or HostFollower(host_app(cli), port)
        if not re.fullmatch(r'[A-Za-z0-9.-]+', self.follower.bundle):
            raise ValueError('invalid host bundle')
        self.origin, self.page_url, self.service = origin, page_url, service
        self.probe, self.sleeper, self.clock = probe, sleeper, clock

    def _ensure_monitors(self):
        service = self.service
        agents = [(LABEL, service.path, service.status)]
        if service._menu_owned():
            agents.append((MENU_LABEL, service.menu_path, service.menu_status))
        for label, path, status in agents:
            state = status()
            if state == 'running':
                continue
            if state == 'not_loaded':
                result = service._launchctl('bootstrap', service.domain, str(path))
            elif state == 'loaded':
                result = service._launchctl('kickstart', service.domain + '/' + label)
            else:
                return False
            if result.returncode != 0:
                return False
            deadline = self.clock() + 5
            while status() != 'running':
                if self.clock() >= deadline:
                    return False
                self.sleeper(.1)
        return True

    def restart(self):
        # Keep the collector alive across closing the host, so it reattaches.
        if not self._ensure_monitors():
            return 'monitor_failed'
        self.follower.last_attempt = None  # The user explicitly requested this restart.
        outcome = self.follower.ensure()
        if outcome == 'waiting_host':
            outcome = self.follower.launch()
        if outcome != 'launch_requested':
            return outcome
        from .runtime import list_pages, select_page
        def ready():
            select_page(list_pages(self.origin), self.page_url, self.origin)
            return True
        probe = self.probe or ready
        deadline = self.clock() + 30
        while self.clock() < deadline:
            try:
                if probe():
                    return 'reopened' if self._ensure_monitors() else 'monitor_failed'
            except (OSError, ValueError, CDPError):
                pass
            self.sleeper(.5)
        return 'connection_timeout'


class HostRestartSource:
    def __init__(self, restarter):
        self.restarter, self.task = restarter, None
        self.attempt = 0
        self.value = {'status': 'available', 'attempt': 0}

    def snapshot(self, revision):
        if (self.value.get('status') != 'restarting' and self.value.get('revision') is not None
                and self.value['revision'] != revision):
            return {'status': 'available', 'attempt': self.attempt}
        return self.value

    def request(self, revision):
        if self.task is not None and not self.task.done():
            return False
        self.attempt += 1
        self.value = {'status': 'restarting', 'revision': revision, 'attempt': self.attempt}
        self.task = asyncio.create_task(self._run(revision, self.attempt))
        return True

    async def _run(self, revision, attempt):
        try:
            status = await asyncio.to_thread(self.restarter.restart)
            self.value = {'status': 'reopened' if status == 'reopened' else 'failed', 'revision': revision, 'attempt': attempt}
        except (OSError, ValueError, RuntimeError):
            self.value = {'status': 'failed', 'revision': revision, 'attempt': attempt}

    async def close(self):
        if self.task is not None:
            # A chosen restart owns a bounded operation; finish reconnecting.
            await self.task
