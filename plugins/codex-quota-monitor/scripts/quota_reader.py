"""Read account limits via the installed Codex protocol; no model calls or auth-file writes."""
import json
import hashlib
import math
import os
import queue
import shutil
import subprocess
import threading
import time


def _window_metrics(used, duration, resets_at, now):
    """Return optional linear pace/forecast metadata for one reported window."""
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
               for value in (used, duration, resets_at)) or duration <= 0:
        return {}
    start = resets_at - duration * 60
    elapsed = max(0, min(duration * 60, now - start))
    expected_used = 100 * elapsed / (duration * 60)
    metrics = {'paceDelta': used - expected_used}
    if used > 0 and elapsed > 0:
        exhaust_at = start + elapsed * 100 / used
        # Carried unconditionally, unlike projectedExhaustAt below: "how long
        # this window can still carry the work" is answerable even when the
        # window would refill first, which is exactly the case the forecast
        # used to drop.
        metrics['exhaustInSec'] = exhaust_at - now
        metrics['projectedExhaustAt'] = exhaust_at if exhaust_at < resets_at else None
    return metrics


def _budget(windows, now):
    """How long the account can keep being used at the pace it has been spent.

    Every reported window is an AND gate, so the account is limited by
    whichever window binds first. A window that refills before it would run out
    cannot bind within that horizon; a period whose windows are all like that
    is therefore reported as a floor, meaning safe at least until the nearest
    reset. Returning kind with the number is what keeps a floor from being read
    as a measurement.
    """
    binding, floors = [], []
    for window in windows:
        resets_at = window.get('resetsAt')
        if not isinstance(resets_at, (int, float)) or isinstance(resets_at, bool):
            continue
        reset_in = resets_at - now
        if reset_in <= 0:
            continue
        exhaust = window.get('exhaustInSec')
        if isinstance(exhaust, (int, float)) and not isinstance(exhaust, bool) and exhaust < reset_in:
            binding.append((exhaust, window['key'], resets_at))
        else:
            floors.append((reset_in, window['key'], resets_at))
    candidates, kind = (binding, 'exhaust') if binding else ((floors, 'floor') if floors else ([], None))
    if not candidates:
        return None
    seconds, key, resets_at = min(candidates)
    return {'kind': kind, 'seconds': seconds, 'key': key, 'resetsAt': resets_at}


def _text(value):
    """A non-empty string, or None. Absent protocol fields are never invented."""
    return value.strip() if isinstance(value, str) and value.strip() else None


def _flag(value):
    """A real boolean, or None. A truthy string is not a reached limit."""
    return value if isinstance(value, bool) else None


def normalize(result, now=None):
    now = time.time() if now is None else now
    buckets = result.get('rateLimitsByLimitId') or {}
    limits = buckets.get('codex') or result.get('rateLimits') or {}
    windows = []
    for key in ('primary', 'secondary'):
        value = limits.get(key)
        if not isinstance(value, dict):
            continue
        used = value.get('usedPercent')
        if not isinstance(used, (int, float)) or isinstance(used, bool) or not math.isfinite(used):
            continue
        duration = value.get('windowDurationMins')
        resets_at = value.get('resetsAt')
        window = {'key': key, 'remaining': max(0, min(100, 100-used)),
                  'duration': duration, 'resetsAt': resets_at}
        window.update(_window_metrics(used, duration, resets_at, now))
        windows.append(window)
    if not windows and (not any(k in limits for k in ('limitId','planType','credits','limitName')) or any(isinstance(limits.get(k),dict) for k in ('primary','secondary'))):
        raise ValueError('No quota windows')
    identity = result.get('accountId')
    # Plan and reach flags travel with the windows because a limit is an AND
    # gate: every reported window needs headroom, and a reached one stops the
    # account even while the other still has some left. Neither is derivable
    # from the percentages alone.
    plan_type = _text(limits.get('planType')) or _text(result.get('planType'))
    reached = _text(limits.get('rateLimitReachedType')) or _text(result.get('rateLimitReachedType'))
    allowed = _flag(limits.get('ordinaryUsageAllowed'))
    if allowed is None:
        allowed = _flag(result.get('ordinaryUsageAllowed'))
    reset = result.get('rateLimitResetCredits') or {}
    credits = (reset.get('credits') or []) if isinstance(reset, dict) else []
    expiries = [item.get('expiresAt') for item in credits if isinstance(item, dict)
                and item.get('status') == 'available'
                and isinstance(item.get('expiresAt'), (int, float)) and not isinstance(item.get('expiresAt'), bool)]
    available = reset.get('availableCount') if isinstance(reset, dict) else None
    reset_credits = {'availableCount': max(0, int(available)), 'nextExpiresAt': min(expiries) if expiries else None} \
        if isinstance(available, (int, float)) and not isinstance(available, bool) and math.isfinite(available) else None
    return {'status': 'live', 'source': 'Codex app-server', 'updatedAt': time.time(), 'windows': windows,
            'windowStatus':'reported' if windows else 'not_reported', 'resetCredits': reset_credits,
            'budget': _budget(windows, now),
            'planType': plan_type, 'ordinaryUsageAllowed': allowed, 'rateLimitReachedType': reached,
            'accountKey': hashlib.sha256(str(identity).encode()).hexdigest() if identity else None}


def normalize_usage(result):
    summary = result.get('summary') if isinstance(result, dict) else None
    buckets = result.get('dailyUsageBuckets') if isinstance(result, dict) else None
    clean_summary = {}
    for key in ('lifetimeTokens', 'peakDailyTokens', 'longestRunningTurnSec',
                'currentStreakDays', 'longestStreakDays'):
        value = summary.get(key) if isinstance(summary, dict) else None
        clean_summary[key] = value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None
    clean_buckets = []
    for item in buckets if isinstance(buckets, list) else []:
        tokens = item.get('tokens') if isinstance(item, dict) else None
        date = item.get('startDate') if isinstance(item, dict) else None
        if isinstance(date, str) and isinstance(tokens, (int, float)) and not isinstance(tokens, bool) and math.isfinite(tokens):
            clean_buckets.append({'startDate': date, 'tokens': max(0, tokens)})
    return {'summary': clean_summary, 'dailyUsageBuckets': clean_buckets[-90:]}


def read_quota():
    executable = os.environ.get('CODEX_MONITOR_CLI_PATH') or shutil.which('codex.exe') or shutil.which('codex')
    if not executable:
        executable = next((p for p in ('/Applications/ChatGPT.app/Contents/Resources/codex',
                                       '/Applications/Codex.app/Contents/Resources/codex') if os.path.isfile(p)), None)
    if not executable:
        raise FileNotFoundError('Codex CLI unavailable')
    process = subprocess.Popen([executable, 'app-server'], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               shell=os.name=='nt' and executable.lower().endswith(('.cmd','.bat')),
                               creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0) if os.name=='nt' else 0)
    messages = queue.Queue()
    def consume():
        try:
            for line in iter(process.stdout.readline, b''):
                try: messages.put(json.loads(line))
                except ValueError: continue
        finally: messages.put(None)
    threading.Thread(target=consume,daemon=True).start()

    def call(number, method, params=None):
        process.stdin.write((json.dumps({'id': number, 'method': method, 'params': params})+'\n').encode())
        process.stdin.flush()
        deadline = time.monotonic()+15
        while time.monotonic() < deadline:
            try: message=messages.get(timeout=max(.01,deadline-time.monotonic()))
            except queue.Empty: break
            if message is None: raise OSError('app-server exited')
            if message.get('id') == number:
                if 'error' in message: raise ValueError('Account limits unavailable')
                return message['result']
        raise TimeoutError('Account read timed out')
    try:
        call(1, 'initialize', {'clientInfo': {'name': 'codex_quota_monitor', 'version': '0.1.0'}})
        process.stdin.write(b'{"method":"initialized"}\n')
        process.stdin.flush()
        value = normalize(call(2, 'account/rateLimits/read'))
        try:
            value['usage'] = normalize_usage(call(3, 'account/usage/read'))
        except (ValueError, TimeoutError, OSError, KeyError):
            value['usage'] = {'summary': {}, 'dailyUsageBuckets': []}
        return value
    finally:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        process.stdin.close()
        process.stdout.close()


class QuotaReader:
    def __init__(self):
        self.value = {'status': 'loading', 'windows': []}
        self.next_read = 0
        self.busy = False
        self.lock = threading.Lock()

    def snapshot(self, force=False):
        with self.lock:
            if force and self.next_read-time.monotonic() < 55:
                self.next_read = 0
            if not self.busy and time.monotonic() >= self.next_read:
                self.busy = True
                threading.Thread(target=self._refresh, daemon=True).start()
            return dict(self.value)

    def _refresh(self):
        try:
            value = read_quota()
        except Exception as exc:
            # Clear values on failure: account identity cannot be verified then.
            error = type(exc).__name__
            value = {'status': 'unavailable', 'windows': [], 'error': error,
                     'errorCode': {'FileNotFoundError':'cli_missing','TimeoutError':'timeout',
                                   'OSError':'app_server','ValueError':'account_unavailable'}.get(error,'unknown')}
        with self.lock:
            self.value = value
            self.next_read = time.monotonic()+60
            self.busy = False


if __name__ == '__main__':
    print(json.dumps(read_quota(), ensure_ascii=False))
