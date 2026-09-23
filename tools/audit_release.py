"""Audit a generated preview directory before a release review."""
import argparse
import hashlib
import json
from pathlib import Path

FORBIDDEN_SOURCE_MARKERS = ('context_token_injector.py', 'companion_feedback.py',
                            'build_panel_candidate.py', '__COMPANION_ART__',
                            '__COMPANION_EXPRESSIONS__', '__COMPANION_FEEDBACK__')
FORBIDDEN_NAMES = {'auth', 'authentication', 'session.jsonl', 'snapshot', 'history',
                   '.ds_store'}
REQUIRED = {'run.py', 'requirements-cdp.txt', 'config.example.json', 'PREVIEW.txt',
            'renderer/consumer.js', 'renderer/manifest.json', 'renderer/LICENSE',
            'renderer/NOTICE', 'install-manifest.json'}
VISUAL_RESOURCES = {
    'assets/companions/web/candy.webp', 'assets/companions/web/cat.webp',
    'assets/companions/web/corgi.webp', 'assets/companions/web/frost.webp',
    'assets/companions/web/mint.webp', 'assets/companions/web/tea.webp',
    'assets/companions/expressions/cat-concerned.webp',
    'assets/companions/expressions/cat-happy.webp',
    'assets/companions/expressions/cat-idle.webp',
    'assets/companions/expressions/cat-notice.webp',
    'assets/companions/expressions/cat-pet.webp',
    'assets/companions/expressions/cat-waiting.webp'}


def _files(root):
    return {str(path.relative_to(root)) for path in root.rglob('*') if path.is_file()}


def audit(root):
    root = Path(root).absolute()
    files = _files(root)
    missing = sorted(REQUIRED - files)
    suspicious = sorted(path for path in files if any(marker in path.lower() for marker in FORBIDDEN_NAMES)
                        or path.endswith(('.jsonl', '.log')) or '__pycache__' in path)
    if missing or suspicious:
        raise ValueError({'missing': missing, 'suspicious': suspicious})
    try:
        manifest = json.loads((root / 'renderer/manifest.json').read_text())
        install = json.loads((root / 'install-manifest.json').read_text())
    except (OSError, ValueError) as error:
        raise ValueError('invalid release manifests') from error
    if manifest.get('status') != 'independent-v2-candidate':
        raise ValueError('renderer is not an independent V2 candidate')
    visual_hashes = manifest.get('visualResourceSHA256')
    if (not isinstance(visual_hashes, dict) or set(visual_hashes) != VISUAL_RESOURCES or
            any(not isinstance(value, str) or len(value) != 64 or
                any(char not in '0123456789abcdef' for char in value)
                for value in visual_hashes.values())):
        raise ValueError('visual resource manifest missing or invalid')
    consumer_path = Path(manifest.get('consumer', {}).get('path', ''))
    consumer = root / (Path('renderer') / consumer_path if consumer_path.parts[:1] != ('renderer',)
                       else consumer_path)
    data = consumer.read_bytes()
    if hashlib.sha256(data).hexdigest() != manifest.get('consumer', {}).get('sha256'):
        raise ValueError('consumer digest mismatch')
    source = data.decode('utf-8')
    found = [marker for marker in FORBIDDEN_SOURCE_MARKERS if marker in source]
    if found:
        raise ValueError({'legacy_source_markers': found})
    hashes = install.get('files')
    if not isinstance(hashes, dict):
        raise ValueError('missing install file hashes')
    mismatched = []
    for path, expected in hashes.items():
        candidate = root / path
        if not candidate.is_file() or hashlib.sha256(candidate.read_bytes()).hexdigest() != expected:
            mismatched.append(path)
    if mismatched:
        raise ValueError({'install_hash_mismatch': sorted(mismatched)})
    return {'status': 'audited', 'files': len(files), 'hashedFiles': len(hashes),
            'consumer': manifest['consumer']['sha256']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(audit(args.directory), ensure_ascii=False, sort_keys=True))
    except (OSError, TypeError, ValueError, KeyError):
        parser.exit(2, 'release_audit_failed\n')


if __name__ == '__main__':
    main()
