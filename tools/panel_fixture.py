"""Offline consumer probe: read source constants without importing legacy code.

The external renderer remains legacy code, not an independently rewritten V2
asset. Its source/artwork are only emitted to the isolated test process.
"""
import argparse
import ast
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from quota_monitor.compat import panel_payload
from quota_monitor.discovery import discover


def literal(path, name):
    for node in ast.parse(path.read_text(encoding='utf-8')).body:
        targets = node.targets if isinstance(node, ast.Assign) else (
            [node.target] if isinstance(node, ast.AnnAssign) else [])
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            return ast.literal_eval(node.value)
    raise ValueError('required renderer constant missing')


def renderer(scripts):
    script = literal(scripts / 'context_token_injector.py', 'INJECTION_SCRIPT')
    for marker, filename, name in (
            ('__COMPANION_FEEDBACK__', 'companion_feedback.py', 'COMPANION_FEEDBACK_JS'),
            ('__COMPANION_ART__', 'companion_art.py', 'COMPANION_ART'),
            ('__COMPANION_EXPRESSIONS__', 'companion_expressions.py', 'COMPANION_EXPRESSIONS')):
        value = literal(scripts / filename, name)
        script = script.replace(marker, value if isinstance(value, str) else json.dumps(value))
    return script


def fixtures():
    with tempfile.TemporaryDirectory(prefix='quota-panel-fixture-') as directory:
        root = Path(directory)
        for key, input_tokens, total in (('one', 250, 700), ('two', 500, 900)):
            rows = [
                {'type': 'session_meta', 'payload': {'id': key}},
                {'type': 'turn_context', 'payload': {'model': 'synthetic', 'effort': 'high'}},
                {'type': 'event_msg', 'payload': {'type': 'token_count', 'info': {
                    'total_token_usage': {'total_tokens': total},
                    'last_token_usage': {'input_tokens': input_tokens, 'total_tokens': input_tokens + 50},
                    'model_context_window': 1000}}}]
            (root / (key + '.jsonl')).write_text(''.join(json.dumps(row) + '\n' for row in rows))
        payloads = {}
        for key in ('one', 'two', 'missing'):
            result = discover(root, key)
            readings = {key: result['reading']} if result['status'] == 'ok' else {}
            payloads[key] = panel_payload(readings, key)
        return payloads


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('legacy_scripts', type=Path)
    args = parser.parse_args()
    print(json.dumps({'script': renderer(args.legacy_scripts), 'payloads': fixtures()}))


if __name__ == '__main__':
    main()
