"""Bounded transport for a monitor-owned Codex app-server process."""
import asyncio
import json
import os
import signal


class RPCError(ValueError):
    pass


class AppServer:
    def __init__(self, command, *, env=None):
        self.command, self.env = command, env
        self.process = None
        self.request_id = 0

    async def __aenter__(self):
        try:
            self.process = await asyncio.create_subprocess_exec(
                *self.command, env=self.env, stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
                limit=1048576, start_new_session=os.name == 'posix')
            await self.request('initialize', {'clientInfo': {
                'name': 'quota_monitor_v2', 'version': '0.2.0'}})
            await self.send({'method': 'initialized'})
            return self
        except BaseException:
            await self.close()
            raise

    async def send(self, message):
        self.process.stdin.write((json.dumps(message, allow_nan=False) + '\n').encode())
        await self.process.stdin.drain()

    async def request(self, method, params=None):
        self.request_id += 1
        request_id = self.request_id
        message = {'id': request_id, 'method': method}
        if params is not None:
            message['params'] = params
        await self.send(message)
        total = 0
        for _ in range(128):
            line = await self.process.stdout.readline()
            total += len(line)
            if not line or total > 1048576:
                raise RPCError('invalid response')
            row = json.loads(line)
            if not isinstance(row, dict):
                raise RPCError('invalid response')
            if type(row.get('id')) is int and row['id'] == request_id:
                if 'error' in row or 'result' not in row:
                    raise RPCError('request failed')
                return row['result']
        raise RPCError('message limit')

    async def close(self):
        process, self.process = self.process, None
        if process is None:
            return
        # Kill only the group created by this query, never the desktop host.
        if os.name == 'posix':
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass
        elif process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        try:
            await asyncio.wait_for(process.wait(), 2)
        except asyncio.TimeoutError:
            pass

    async def __aexit__(self, *_):
        await self.close()
