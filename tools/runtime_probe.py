"""Synthetic browser probe. Never discovers an installed application."""
import asyncio
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from quota_monitor.cdp import CDPClient
from quota_monitor.runtime import UpdateLoop, list_pages, select_page


async def probe(origin):
    url = 'about:blank'
    if len(sys.argv) > 2 and sys.argv[2] == 'ambiguous':
        loop = UpdateLoop(origin, url, {})
        assert await loop.step() == 'ambiguous'
        assert loop.client is None
        print('runtime Chromium: duplicate pages stop writes passed')
        return
    endpoint = select_page(await asyncio.to_thread(list_pages, origin), url, origin)
    with tempfile.TemporaryDirectory(prefix='quota-runtime-journal-') as root:
        paths = {}
        for key, count in [('one', 250), ('two', 500)]:
            path = Path(root) / (key + '.jsonl')
            path.write_text('\n'.join(json.dumps(row) for row in [
                {'type': 'session_meta', 'payload': {'id': key}},
                {'type': 'event_msg', 'payload': {'type': 'token_count', 'info': {
                    'last_token_usage': {'input_tokens': count}, 'model_context_window': 1000}}}]) + '\n')
            paths[key] = path
        loop = UpdateLoop(origin, url, paths)
        try:
            async with CDPClient(endpoint) as page:
                await page.evaluate('window.__quotaMonitorV2Thread = "one"')
                runner = asyncio.create_task(loop.run(interval=.02))
                try:
                    for _ in range(100):
                        if await page.evaluate('Boolean(window.__quotaMonitorV2Snapshot)'):
                            break
                        await asyncio.sleep(.01)
                    else:
                        raise AssertionError('run did not publish')
                finally:
                    runner.cancel()
                    try:
                        await runner
                    except asyncio.CancelledError:
                        pass
                assert loop.client is None
                assert await loop.step() == 'updated'
                assert await page.evaluate('window.__quotaMonitorV2Snapshot.summaries[0].latest_context_tokens') == 250
                connection = loop.client
                assert await loop.step() == 'updated'
                assert loop.client is connection
                with paths['one'].open('a') as stream:
                    stream.write(json.dumps({'type': 'event_msg', 'payload': {
                        'type': 'token_count', 'info': {'last_token_usage': {'input_tokens': 300},
                                                       'model_context_window': 1000}}}) + '\n')
                assert await loop.step() == 'updated'
                assert await page.evaluate('window.__quotaMonitorV2Snapshot.summaries[0].latest_context_tokens') == 300
                await loop.client.connection.close()
                assert await loop.step() == 'disconnected'
                assert loop.client is None
                assert await loop.step() == 'updated'
                await page.evaluate('''(() => {
                    let n = 0;
                    Object.defineProperty(window, '__quotaMonitorV2Thread', {
                        configurable: true, get: () => ++n === 1 ? 'one' : 'two'});
                })()''')
                assert await loop.step() == 'changed'
                await page.evaluate('''Object.defineProperty(window, '__quotaMonitorV2Thread', {
                    configurable: true, writable: true, value: 'one'}); true''')
                await page.evaluate('window.__quotaMonitorV2Thread = "two"')
                assert await page.evaluate('window.__quotaMonitorV2Snapshot') is None
                assert await loop.step() == 'updated'
                assert await page.evaluate('window.__quotaMonitorV2Snapshot.summaries[0].latest_context_tokens') == 500
                await page.evaluate('window.__quotaMonitorV2Thread = "missing"')
                assert await loop.step() == 'updated'
                assert await page.evaluate('window.__quotaMonitorV2Snapshot.summaries') == []
                await page.evaluate('window.__quotaMonitorV2Thread = "one"')
                assert await loop.step() == 'updated'
                await loop.close()
                await page.evaluate('performance.now = () => 1e15')
                assert await page.evaluate('window.__quotaMonitorV2Snapshot') is None
                await page.evaluate('delete performance.now; location.reload(); true')
                for _ in range(30):
                    if await loop.step() == 'updated':
                        break
                    await asyncio.sleep(.05)
                async with CDPClient(endpoint) as refreshed:
                    await refreshed.evaluate('window.__quotaMonitorV2Thread = "two"')
                    assert await loop.step() == 'updated'
                    assert await refreshed.evaluate('window.__quotaMonitorV2Snapshot.summaries[0].latest_context_tokens') == 500
            # Navigation/closed target handled by normal rediscovery without app restart.
            loop.page_url = 'http://not-selected.invalid/'
            assert await loop.step() == 'not_found'
            assert loop.client is None
        finally:
            await loop.close()
    print('runtime Chromium: exact selection, reuse, append, disconnect/reconnect, task race, task switch, missing, expiry, reload, missing target passed')


if __name__ == '__main__':
    if not __debug__:
        raise RuntimeError('probe requires assertions enabled')
    asyncio.run(probe(sys.argv[1]))
