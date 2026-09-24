"""Package an audited V2 preview as a reproducible release candidate."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import zipfile

from audit_release import audit


LABEL = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$')


def package(preview, destination, label):
    preview, destination = Path(preview).resolve(), Path(destination).absolute()
    if (not isinstance(label, str) or not LABEL.fullmatch(label) or
            destination.exists() or destination.is_symlink() or preview in destination.parents):
        raise ValueError('invalid candidate output')
    result = audit(preview)
    files = sorted(path for path in preview.rglob('*') if path.is_file())
    name = 'codex-quota-monitor-{}-macos.zip'.format(label)
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.v2-package-', dir=str(destination.parent)))
    try:
        archive = stage / name
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as stream:
            for path in files:
                relative = path.relative_to(preview).as_posix()
                info = zipfile.ZipInfo('codex-quota-monitor/' + relative, (2020, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                stream.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED,
                                compresslevel=9)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        (stage / 'SHA256SUMS').write_text('{}  {}\n'.format(digest, name), encoding='ascii')
        (stage / 'CANDIDATE.json').write_text(json.dumps({
            'status': 'candidate-not-release', 'label': label, 'archive': name,
            'sha256': digest, 'consumer': result['consumer'], 'files': result['files']},
            indent=2) + '\n', encoding='utf-8')
        destination.mkdir(mode=0o700)
        try:
            for path in stage.iterdir():
                shutil.move(str(path), str(destination / path.name))
        except BaseException:
            shutil.rmtree(destination)
            raise
    finally:
        shutil.rmtree(stage)
    return {'status': 'candidate-not-release', 'archive': name, 'sha256': digest}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('preview', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--label', required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(package(args.preview, args.destination, args.label)))
    except (OSError, ValueError, KeyError, TypeError):
        parser.exit(2, 'candidate_package_failed\n')


if __name__ == '__main__':
    main()
