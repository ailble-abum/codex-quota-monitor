"""Drive the real update loop against explicit synthetic test inputs over stdin."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, os.environ.get('QUOTA_RUNTIME_ROOT', str(Path(__file__).resolve().parents[1])))
from quota_monitor.runtime import UpdateLoop


async def main():
    origin, url, directory = sys.argv[1:4]
    root = Path(directory)
    loop = UpdateLoop(origin, url, session_root=root / 'logs', session_layout='codex-rollout',
                      panel=True, host='codex-sidebar', account_cli=os.environ.get('QUOTA_ACCOUNT_CLI'), consumer={
                          'path': root / 'consumer.js',
                          'sha256': hashlib.sha256((root / 'consumer.js').read_bytes()).hexdigest()})
    try:
        while True:
            command = await asyncio.to_thread(sys.stdin.readline)
            if not command or command.strip() == 'stop':
                break
            if command.strip() != 'step':
                raise ValueError('invalid probe command')
            print(json.dumps({'status': await loop.step()}), flush=True)
    finally:
        await loop.shutdown()


if __name__ == '__main__':
    asyncio.run(main())
