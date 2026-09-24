"""Read-only app-server quota client; never sends model, login or reset requests."""
import asyncio
import hashlib
import json
import math
import time


def unavailable(code='account_unavailable'):
    return {'status': 'unavailable', 'windows': [], 'errorCode': code}


def number(value, low=0, high=8.64e12):
    return type(value) in (int, float) and low <= value <= high and math.isfinite(value)


def project_usage(raw):
    if not isinstance(raw, dict):
        return None
    summary = raw.get('summary')
    lifetime = summary.get('lifetimeTokens') if isinstance(summary, dict) else None
    buckets = []
    for item in raw.get('dailyUsageBuckets', []) if isinstance(raw.get('dailyUsageBuckets'), list) else []:
        if isinstance(item, dict) and number(item.get('tokens')):
            day = item.get('startDate')
            buckets.append({'tokens': item['tokens'], 'startDate': day}
                           if isinstance(day, str) and len(day) <= 32 else {'tokens': item['tokens']})
    if not buckets and not number(lifetime):
        return None
    return {'dailyUsageBuckets': buckets[-90:],
            'summary': {'lifetimeTokens': lifetime} if number(lifetime) else {}}


def project(raw, *, now):
    """Only the codex bucket, known numeric fields and bounded plan text reach UI."""
    if not isinstance(raw, dict):
        return unavailable()
    buckets = raw.get('rateLimitsByLimitId')
    limits = buckets.get('codex') if isinstance(buckets, dict) else raw.get('rateLimits')
    if buckets is not None and not isinstance(buckets, dict):
        return unavailable()
    if not isinstance(limits, dict) or limits.get('limitId') not in (None, 'codex'):
        return unavailable()
    windows = []
    for key in ('primary', 'secondary'):
        item = limits.get(key)
        if item is None:
            continue
        if not isinstance(item, dict) or not number(item.get('usedPercent'), high=100):
            return unavailable()
        window = {'key': key, 'remaining': 100 - item['usedPercent']}
        duration, reset = item.get('windowDurationMins'), item.get('resetsAt')
        if duration is not None:
            if not number(duration, low=1, high=5256000):
                return unavailable()
            window['duration'] = duration
        if reset is not None:
            if not number(reset):
                return unavailable()
            window['resetsAt'] = reset
        windows.append(window)
    result = {'status': 'live', 'updatedAt': now, 'windows': windows,
              'windowStatus': 'reported' if windows else 'not_reported'}
    account_id = raw.get('accountId')
    if isinstance(account_id, str) and 0 < len(account_id) <= 256:
        result['accountKey'] = hashlib.sha256(account_id.encode('utf-8')).hexdigest()
    plan = limits.get('planType')
    if isinstance(plan, str) and len(plan) <= 64:
        result['planType'] = plan
    # Preserve an explicit server block even if percentages look available.
    blocked = limits.get('rateLimitReachedType')
    result['ordinaryUsageAllowed'] = not bool(blocked) and not any(w['remaining'] == 0 for w in windows)
    usage = project_usage(raw.get('usage'))
    if usage is not None:
        result['usage'] = usage
    credits = raw.get('rateLimitResetCredits', raw.get('resetCredits'))
    if isinstance(credits, dict):
        available, expiry = credits.get('availableCount'), credits.get('nextExpiresAt')
        rows = credits.get('credits')
        if isinstance(rows, list):
            expiries = [item.get('expiresAt') for item in rows if isinstance(item, dict)
                        and item.get('status') == 'available' and number(item.get('expiresAt'))]
            if expiries:
                expiry = min(expiries)
        if (type(available) is int and 0 <= available <= 10000 and
                (expiry is None or number(expiry))):
            result['resetCredits'] = {'availableCount': available}
            if expiry is not None:
                result['resetCredits']['nextExpiresAt'] = expiry
    budget = raw.get('budget')
    if isinstance(budget, dict) and budget.get('kind') in ('floor', 'exhaust') and number(budget.get('seconds')):
        result['budget'] = {'kind': budget['kind'], 'seconds': budget['seconds']}
    return result


async def read_account(command, *, timeout=12):
    process = None
    async def exchange():
        nonlocal process
        process = await asyncio.create_subprocess_exec(*command, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, limit=1048576)
        async def send(message):
            process.stdin.write((json.dumps(message) + '\n').encode())
            await process.stdin.drain()
        async def response(request_id):
            total = 0
            for _ in range(128):
                line = await process.stdout.readline()
                total += len(line)
                if not line or total > 1048576:
                    raise ValueError('invalid response')
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise ValueError('invalid response')
                if type(message.get('id')) is int and message['id'] == request_id:
                    if 'error' in message or 'result' not in message:
                        raise ValueError('request failed')
                    return message['result']
            raise ValueError('message limit')
        await send({'id': 1, 'method': 'initialize', 'params': {'clientInfo': {
            'name': 'quota_monitor_v2', 'version': '0.2.0'}}})
        await response(1)
        await send({'method': 'initialized'})
        await send({'id': 2, 'method': 'account/rateLimits/read'})
        quota = project(await response(2), now=time.time())
        if quota['status'] != 'live':
            return quota
        try:
            await send({'id': 3, 'method': 'account/usage/read'})
            usage = project_usage(await asyncio.wait_for(response(3), 3))
            if usage is not None:
                quota['usage'] = usage
        except (OSError, ValueError, asyncio.TimeoutError):
            pass
        return quota
    try:
        return await asyncio.wait_for(exchange(), timeout)
    except FileNotFoundError:
        return unavailable('cli_missing')
    except asyncio.TimeoutError:
        return unavailable('timeout')
    except (OSError, ValueError, RecursionError):
        return unavailable('app_server')
    finally:
        if process is not None:
            if process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
            await process.wait()


class AccountSource:
    """One background request at most per minute; local token updates never wait."""
    def __init__(self, cli):
        self.command = [cli, 'app-server']
        self.value = unavailable()
        self.task = None
        self.next_read = 0

    async def refresh(self):
        self.value = await read_account(self.command)

    def snapshot(self):
        if time.monotonic() >= self.next_read and (self.task is None or self.task.done()):
            self.next_read = time.monotonic() + 60
            self.task = asyncio.create_task(self.refresh())
        stamp = self.value.get('updatedAt')
        if self.value['status'] == 'live' and (not number(stamp) or not 0 <= time.time() - stamp < 120):
            return unavailable()
        return self.value

    def request_refresh(self):
        self.next_read = 0

    async def close(self):
        if self.task is not None:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
