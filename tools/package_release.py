"""Promote an audited V2 preview into a macOS release archive."""
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


VERSION = re.compile(r'^[0-9]+\.[0-9]+\.[0-9]+$')
COMMIT = re.compile(r'^[0-9a-f]{40}$')
FAT_MACHO = (b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca')


def package(preview, menu_binary, destination, version, source_commit):
    preview, menu_binary = Path(preview).resolve(), Path(menu_binary)
    destination = Path(destination).absolute()
    if (not VERSION.fullmatch(version) or not COMMIT.fullmatch(source_commit)
            or destination.exists() or destination.is_symlink() or preview in destination.parents
            or menu_binary.is_symlink() or not menu_binary.is_file()
            or not os.access(menu_binary, os.X_OK) or menu_binary.stat().st_size > 20 * 1024 * 1024):
        raise ValueError('invalid release input')
    with menu_binary.open('rb') as stream:
        if stream.read(4) not in FAT_MACHO:
            raise ValueError('menu binary must be universal Mach-O')
    if audit(preview)['kind'] != 'preview':
        raise ValueError('release input must be a preview')
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.v2-release-', dir=str(destination.parent)))
    try:
        bundle = stage / 'codex-quota-monitor'
        shutil.copytree(preview, bundle)
        (bundle / 'PREVIEW.txt').unlink()
        (bundle / 'RELEASE.txt').write_text(
            'Codex Quota Monitor v{} · macOS\n'
            '手动安装包；需要 macOS、Python 3.9+。当前未签名或公证。\n'
            '先建立虚拟环境并安装 requirements-cdp.txt，复制 config.example.json 为私有 config.json。\n'
            '填写准确的 page_url、session_root、host_app；菜单栏另需 history_root。\n'
            '前台验证：python run.py --config /absolute/config.json --wait-for-host\n'
            '服务安装：python -m quota_monitor.service install --config /absolute/config.json\n'
            '检查：python -m quota_monitor.service doctor\n'
            '菜单栏：python -m quota_monitor.service menu-install --config /absolute/config.json\n'
            '回退：先 menu-uninstall，再 uninstall。保留 LICENSE 与 NOTICE。\n'.format(version),
            encoding='utf-8')
        shutil.copyfile(menu_binary, bundle / 'QuotaMenu')
        (bundle / 'QuotaMenu').chmod(0o755)
        renderer = bundle / 'renderer/manifest.json'
        manifest = json.loads(renderer.read_text())
        manifest['status'] = 'independent-v2-release'
        renderer.write_text(json.dumps(manifest, indent=2) + '\n')
        files = {str(path.relative_to(bundle)): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in sorted(bundle.rglob('*')) if path.is_file()
                 and path.name != 'install-manifest.json'}
        (bundle / 'install-manifest.json').write_text(json.dumps(
            {'status': 'release', 'version': version, 'sourceCommit': source_commit,
             'files': files}, indent=2) + '\n')
        result = audit(bundle)
        if result['kind'] != 'release':
            raise ValueError('release audit failed')
        name = 'codex-quota-monitor-v{}-macos.zip'.format(version)
        archive = stage / name
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as stream:
            for path in sorted(bundle.rglob('*')):
                if not path.is_file():
                    continue
                relative = path.relative_to(stage).as_posix()
                info = zipfile.ZipInfo(relative, (2020, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (0o100755 if path.name == 'QuotaMenu' else 0o100644) << 16
                stream.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED,
                                compresslevel=9)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        (stage / 'SHA256SUMS').write_text('{}  {}\n'.format(digest, name), encoding='ascii')
        (stage / 'RELEASE.json').write_text(json.dumps({
            'status': 'release', 'version': version, 'sourceCommit': source_commit,
            'archive': name, 'sha256': digest, 'consumer': result['consumer'],
            'files': result['files']}, indent=2) + '\n', encoding='utf-8')
        destination.mkdir(mode=0o700)
        try:
            for path in (archive, stage / 'SHA256SUMS', stage / 'RELEASE.json'):
                shutil.move(str(path), str(destination / path.name))
        except BaseException:
            shutil.rmtree(destination)
            raise
    finally:
        shutil.rmtree(stage)
    return {'status': 'release', 'archive': name, 'sha256': digest}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('preview', type=Path)
    parser.add_argument('menu_binary', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--version', required=True)
    parser.add_argument('--source-commit', required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(package(args.preview, args.menu_binary, args.destination,
                                 args.version, args.source_commit)))
    except (OSError, ValueError, KeyError, TypeError):
        parser.exit(2, 'release_package_failed\n')


if __name__ == '__main__':
    main()
