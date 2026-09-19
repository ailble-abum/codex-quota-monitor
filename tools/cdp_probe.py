"""Probe only the explicit temporary page endpoint supplied by verify_cdp.cjs."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from quota_monitor.cdp import CDPClient, CDPError


async def probe(endpoint):
    async with CDPClient(endpoint) as client:
        assert await client.evaluate('({answer: 42, title: document.title})') == {
            'answer': 42, 'title': 'isolated CDP probe'}
        assert await client.evaluate('window.probeCount = (window.probeCount || 0) + 1') == 1
        assert await client.evaluate('window.probeCount += 1') == 2
        try:
            await client.evaluate('throw new Error("SYNTHETIC_PRIVATE")')
        except CDPError as error:
            assert str(error) == 'javascript_error'
        else:
            raise AssertionError('JavaScript exception was not reported')
    async with CDPClient(endpoint) as client:
        assert await client.evaluate('window.probeCount') == 2
        assert await client.evaluate('undefined') is None
    print('real Chromium CDP: values, persistence, exception, explicit reconnect passed')


if __name__ == '__main__':
    if not __debug__:
        raise RuntimeError('probe requires assertions enabled')
    asyncio.run(probe(sys.argv[1]))
