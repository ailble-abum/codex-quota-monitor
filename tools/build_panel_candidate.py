"""Build an attributed, isolated candidate from one frozen external renderer.

Not a general JS rewriter, installer, or claim of independent renderer authorship.
Only the newly written adapter is stored in V2; retained source stays external.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path

BASE = '2705f32a6f080ee1bdbecdc5b43f5fe0f9045eed'
HASHES = {
    'context_token_injector.py': '2b308296d1b928e39d847cd1de477ebc4587191aa6b5813838d7fdc9074d1b57',
    'companion_feedback.py': 'e954ed4ce8f4e026779a61ebeba4b5b87774ab6073cd3e6355f744e62c0a80fa',
    'companion_art.py': 'bf82328005097b4af6df60b5c158f5f15230e0378b2cad06693ced15a5bb1865',
    'companion_expressions.py': '1be738c3a9d7a1965df6cff09c3929ee12a5550b1fb88c893da165888e13138a',
    'LICENSE': '3173384c5ec386cd808211ded2d3634f2521f9a92de981d2a104a2b42b291b40',
    'NOTICE': '5e524e54bbf3d1839d6e695e5adc189e459921e619612e153d9da703c1729267',
}


def literal(source, name):
    for node in ast.parse(source).body:
        targets = node.targets if isinstance(node, ast.Assign) else (
            [node.target] if isinstance(node, ast.AnnAssign) else [])
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            return ast.literal_eval(node.value)
    raise ValueError('constant missing')


def cut(source, start, end):
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError('unexpected source boundary')
    a, b = source.index(start), source.index(end)
    if b <= a:
        raise ValueError('reversed source boundary')
    return source[:a] + source[b:]


def build(directory):
    texts = {}
    for name, digest in HASHES.items():
        with (Path(directory) / name).open('rb') as stream:
            data = stream.read(1048577)
        if len(data) > 1048576 or hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('unrecognized source revision')
        texts[name] = data.decode('utf-8')
    script = literal(texts['context_token_injector.py'], 'INJECTION_SCRIPT')
    # Exact source digests make these bounded spans safe; unknown revisions stop.
    for start, end in (
            ('  function summaryHover(', '  function ensureStyle('),
            ('  function cleanOriginalTitle(', '  function hudMode('),
            ('  function applySidebar(', '  function applyHud(')):
        script = cut(script, start, end)
    tail = '  function clearFooters('
    if script.count(tail) != 1:
        raise ValueError('unexpected lifecycle boundary')
    script = script[:script.index(tail)] + (Path(__file__).parents[1] / 'quota_monitor/panel_adapter.js').read_text()
    guard = """(payload => {
  if (document.getElementById('codex-context-token-inspector-root') ||
      document.getElementById('codex-context-token-inspector-style') ||
      document.getElementById('codex-context-token-inspector-mascot'))
    throw new Error('consumer DOM occupied');"""
    script = script.replace('(payload => {', guard, 1)
    for marker, filename, name in (
            ('__COMPANION_FEEDBACK__', 'companion_feedback.py', 'COMPANION_FEEDBACK_JS'),
            ('__COMPANION_ART__', 'companion_art.py', 'COMPANION_ART'),
            ('__COMPANION_EXPRESSIONS__', 'companion_expressions.py', 'COMPANION_EXPRESSIONS')):
        value = literal(texts[filename], name)
        script = script.replace(marker, value if isinstance(value, str) else json.dumps(value))
    header = ('// Isolated derived candidate; retained renderer from ' + BASE + '.\n'
              '// Copyright (c) 2026 Kevin Ke; Copyright (c) 2026 Ailble.\n'
              '// MIT: accompanying LICENSE and NOTICE must travel with this file.\n')
    return header + script, texts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_dir', type=Path, help='Four frozen scripts plus original LICENSE/NOTICE')
    parser.add_argument('output_dir', type=Path, help='New directory; never overwrites an existing bundle')
    args = parser.parse_args()
    script, texts = build(args.source_dir)
    args.output_dir.mkdir()  # Existing output must be explicitly retained or removed by its owner.
    (args.output_dir / 'consumer.js').write_text(script, encoding='utf-8')
    for name in ('LICENSE', 'NOTICE'):
        (args.output_dir / name).write_text(texts[name], encoding='utf-8')
    manifest = {'sourceCommit': BASE, 'sourceSHA256': HASHES,
                'consumer': {'path': 'consumer.js', 'sha256': hashlib.sha256(script.encode()).hexdigest()},
                'status': 'derived-isolated-candidate',
                'changes': 'Removed host/sidebar/message scans and observer lifecycle; V2 snapshot-only adapter.'}
    (args.output_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest['consumer']))


if __name__ == '__main__':
    main()
