"""Exercise bundled Codex config RPCs in a temporary CODEX_HOME, never real settings."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from quota_monitor.context_defaults import exchange


async def verify(cli):
    with tempfile.TemporaryDirectory(prefix='quota-context-defaults-') as temporary:
        root = Path(temporary)
        path = root / 'config.toml'
        original = '# preserve this comment\nmodel = "gpt-6.1-sol"\nweb_search = "disabled"\n'
        path.write_text(original)
        env = {**os.environ, 'CODEX_HOME': str(root)}
        command = [cli, 'app-server']
        state = await exchange(command, {'id': 'read', 'action': 'read'}, env=env)
        assert state['windowTokens'] is None and state['compactTokens'] is None
        revision = state['revision']
        state = await exchange(command, {'id': 'save', 'action': 'save', 'revision': revision,
            'windowTokens': 180000, 'compactTokens': 150000}, env=env)
        assert state['feedback'] == 'saved'
        assert (state['windowTokens'], state['compactTokens']) == (180000, 150000)
        assert original in path.read_text()
        after_save = path.read_bytes()
        stale = await exchange(command, {'id': 'stale', 'action': 'reset', 'revision': revision}, env=env)
        assert stale['feedback'] == 'conflict' and path.read_bytes() == after_save
        path.write_text(path.read_text() + '\n# another editor\nmodel_reasoning_effort = "medium"\n')
        concurrent = await exchange(command, {'id': 'concurrent', 'action': 'reset', 'revision': state['revision']}, env=env)
        # Revisions protect semantic configuration changes; comments are preserved.
        assert concurrent['feedback'] == 'conflict'
        state = await exchange(command, {'id': 'reset', 'action': 'reset', 'revision': concurrent['revision']}, env=env)
        assert state['feedback'] == 'saved' and state['windowTokens'] is None and state['compactTokens'] is None
        assert original in path.read_text() and '# another editor' in path.read_text()
        assert 'model_reasoning_effort = "medium"' in path.read_text()
        assert 'model_context_window' not in path.read_text()
        assert 'model_auto_compact_token_limit' not in path.read_text()
    print(json.dumps({'status': 'passed', 'checks': ['read', 'save', 'stale_revision',
        'concurrent_edit', 'reset', 'unrelated_config_and_comments_preserved'],
        'cli': subprocess.check_output([cli, '--version'], text=True).strip()}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cli')
    args = parser.parse_args()
    asyncio.run(verify(args.cli))
