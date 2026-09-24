"""Explicit foreground runner; host relaunch is opt-in through host_app."""
import argparse
import asyncio
import json
import math
from pathlib import Path
import signal
import sys
from urllib.parse import urlsplit

from .compat import thread_key
from .reader import reject_constant


def emit(event, *, error=False, **fields):
    print(json.dumps({'event': event, **fields}), file=sys.stderr if error else sys.stdout, flush=True)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default diagnostics may echo private paths or endpoints.
        raise ValueError('invalid_arguments')


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate key')
        result[key] = value
    return result


def load_config(path):
    path = Path(path).absolute()
    with path.open('rb') as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError('config limit')
    config = json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)
    if (not isinstance(config, dict) or set(config) - {'origin', 'page_url', 'journals', 'session_root', 'host', 'panel', 'consumer', 'account_cli', 'session_layout', 'host_app', 'history_root', 'notification_root', 'status_root', 'update_url', 'version'}
            or not {'origin', 'page_url'} <= set(config)
            or ('journals' in config) == ('session_root' in config)):
        raise ValueError('invalid config fields')
    if 'journals' in config:
        paths = config.pop('journals')
        if not isinstance(paths, dict) or not 1 <= len(paths) <= 256:
            raise ValueError('invalid journals')
        for key, value in paths.items():
            if (thread_key(key) != key or not isinstance(value, str) or not value or '\0' in value):
                raise ValueError('invalid journal mapping')
        config['paths'] = {key: path.parent / value for key, value in paths.items()}
    else:
        root = config['session_root']
        if not isinstance(root, str) or not root or '\0' in root:
            raise ValueError('invalid session root')
        config['session_root'] = path.parent / root
    if 'history_root' in config:
        root = config['history_root']
        if not isinstance(root, str) or not root or '\0' in root:
            raise ValueError('invalid history root')
        config['history_root'] = path.parent / root
    if 'notification_root' in config:
        root = config['notification_root']
        if not isinstance(root, str) or not root or '\0' in root:
            raise ValueError('invalid notification root')
        config['notification_root'] = path.parent / root
    if 'status_root' in config:
        root = config['status_root']
        if not isinstance(root, str) or not root or '\0' in root:
            raise ValueError('invalid status root')
        config['status_root'] = path.parent / root
    if 'update_url' in config:
        root = config['update_url']
        valid = False
        if isinstance(root, str):
            try:
                parsed = urlsplit(root)
                valid = (parsed.scheme == 'https' and bool(parsed.hostname) and
                         not parsed.username and not parsed.password and not parsed.fragment)
            except ValueError:
                pass
        if (not isinstance(root, str) or len(root) > 2048 or
                any(ord(c) < 32 or c.isspace() for c in root) or not valid):
            raise ValueError('invalid update URL')
        config['update_url'] = root
    if 'version' in config and (not isinstance(config['version'], str) or not config['version'] or len(config['version']) > 64):
        raise ValueError('invalid version')
    if 'consumer' in config:
        consumer = config['consumer']
        if (not isinstance(consumer, dict) or set(consumer) != {'path', 'sha256'}
                or not isinstance(consumer['path'], str) or not consumer['path'] or '\0' in consumer['path']):
            raise ValueError('invalid consumer config')
        consumer['path'] = path.parent / consumer['path']
    url = config['page_url']
    if not isinstance(url, str) or not 1 <= len(url) <= 8192 or any(ord(c) < 32 for c in url):
        raise ValueError('invalid page URL')
    return config


async def supervise(loop, *, interval, max_failures, once, wait_for_host=False):
    task = asyncio.current_task()
    event_loop = asyncio.get_running_loop()
    stopped_by = None
    finishing = False
    previous_handlers = {}

    def stop(signum, frame):
        nonlocal stopped_by
        if stopped_by is None:
            stopped_by = signum
            event_loop.call_soon_threadsafe(lambda: None if finishing else task.cancel())

    reason, code, previous_status, failures = 'error', 3, None, 0
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[sig] = signal.signal(sig, stop)
        while True:
            status = await loop.step()
            marker = getattr(loop, 'status_store', None)
            if marker is not None:
                try:
                    marker.write(status)
                except OSError:
                    pass
            if status != previous_status:
                emit('state', status=status)
                previous_status = status
            if once:
                reason, code = 'once', 0 if status == 'updated' else 2
                break
            if getattr(loop, 'host_follower', None) is not None and status in {
                    'discovery_unavailable', 'not_found'}:
                action = await loop.follow_host() if status == 'discovery_unavailable' else 'waiting_page'
                emit('host_follow', action=action)
                failures = 0
                await asyncio.sleep(min(15, interval))
                continue
            if wait_for_host and status in ('discovery_unavailable', 'not_found'):
                failures = 0
                await asyncio.sleep(15)
                continue
            failures = 0 if status in ('updated', 'unselected', 'changed',
                'data_index_wait', 'data_loading', 'data_incomplete', 'data_unavailable',
                'data_not_found', 'data_ambiguous') else failures + 1
            if failures >= max_failures:
                reason, code = 'failure_limit', 2
                break
            await asyncio.sleep(min(60, interval * 2 ** min(max(0, failures - 1), 10)))
    except asyncio.CancelledError:
        reason = 'sigterm' if stopped_by == signal.SIGTERM else 'sigint' if stopped_by == signal.SIGINT else 'cancelled'
        code = 143 if stopped_by == signal.SIGTERM else 130
    except Exception:
        emit('error', error=True, status='runtime_error')
        marker = getattr(loop, 'status_store', None)
        if marker is not None:
            try:
                marker.write('runtime_error')
            except OSError:
                pass
    finally:
        finishing = True
        try:
            try:
                cleanup = await loop.shutdown()
            except Exception:
                cleanup = 'cleanup_failed'
                emit('error', error=True, status=cleanup)
                if code == 0:
                    code = 3
            if stopped_by is not None:
                reason = 'sigterm' if stopped_by == signal.SIGTERM else 'sigint'
                code = 143 if stopped_by == signal.SIGTERM else 130
            emit('stopped', reason=reason, cleanup=cleanup)
            marker = getattr(loop, 'status_store', None)
            if marker is not None:
                try:
                    marker.write('stopped')
                except OSError:
                    pass
        finally:
            for sig, handler in previous_handlers.items():
                signal.signal(sig, handler)
    return code


def main():
    parser = Parser(description=__doc__)
    parser.add_argument('--config', required=True, help='Explicit JSON configuration file')
    parser.add_argument('--once', action='store_true', help='Check and publish once, then release')
    parser.add_argument('--wait-for-host', action='store_true',
                        help='Wait quietly for the explicit endpoint/page; host_app remains opt-in')
    parser.add_argument('--interval', type=float, default=1.0)
    parser.add_argument('--max-failures', type=int, default=5)
    try:
        args = parser.parse_args()
        if not math.isfinite(args.interval) or not 0.1 <= args.interval <= 60 or not 1 <= args.max_failures <= 100:
            raise ValueError('invalid_arguments')
    except ValueError:
        emit('error', error=True, status='invalid_arguments')
        return 2
    try:
        config = load_config(args.config)
        from .runtime import UpdateLoop
        loop = UpdateLoop(**config)
    except ModuleNotFoundError:
        emit('error', error=True, status='dependency_unavailable')
        return 2
    except (OSError, ValueError, TypeError, RecursionError):
        emit('error', error=True, status='invalid_config')
        return 2
    try:
        return asyncio.run(supervise(loop, interval=args.interval, max_failures=args.max_failures, once=args.once,
                                     wait_for_host=args.wait_for_host))
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
