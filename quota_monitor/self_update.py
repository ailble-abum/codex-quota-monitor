"""Install an official macOS release beside the current managed installation."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import plistlib
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, urlopen
import zipfile

from .service import LABEL, MENU_LABEL, Service
from .update_state import CURRENT_VERSION, RELEASE_API, _version


REPOSITORY = 'ailble-abum/codex-quota-monitor'
MAX_ARCHIVE = 30 * 1024 * 1024


class UpdateError(ValueError):
    pass


def _fetch(url, limit):
    accept = 'application/vnd.github+json' if url == RELEASE_API else 'application/octet-stream'
    with urlopen(Request(url, headers={'User-Agent': 'codex-quota-monitor-v2',
                                       'Accept': accept}), timeout=30) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise UpdateError('download_too_large')
    return data


def _release(version, fetch=_fetch):
    if _version(version) is None or _version(version)[:3] <= _version(CURRENT_VERSION)[:3]:
        raise UpdateError('invalid_target_version')
    data = json.loads(fetch(RELEASE_API, 65536))
    if (data.get('tag_name') != 'v' + version or data.get('draft') or data.get('prerelease')
            or not isinstance(data.get('assets'), list)):
        raise UpdateError('release_mismatch')
    prefix = 'https://github.com/{}/releases/download/v{}/'.format(REPOSITORY, version)
    names = {'codex-quota-monitor-v{}-macos.zip'.format(version), 'SHA256SUMS'}
    assets = {item.get('name'): item.get('browser_download_url') for item in data['assets']
              if isinstance(item, dict) and item.get('name') in names}
    if set(assets) != names or any(assets[name] != prefix + name for name in names):
        raise UpdateError('release_assets_missing')
    return assets


def _archive(version, fetch=_fetch):
    assets = _release(version, fetch)
    name = 'codex-quota-monitor-v{}-macos.zip'.format(version)
    checksum = fetch(assets['SHA256SUMS'], 4096).decode('ascii').strip()
    expected = checksum.split('  ')
    if (len(expected) != 2 or expected[1] != name or len(expected[0]) != 64
            or any(char not in '0123456789abcdef' for char in expected[0])):
        raise UpdateError('invalid_checksum')
    archive = fetch(assets[name], MAX_ARCHIVE)
    if hashlib.sha256(archive).hexdigest() != expected[0]:
        raise UpdateError('checksum_mismatch')
    return archive


def _extract(archive, destination, version):
    from io import BytesIO
    with zipfile.ZipFile(BytesIO(archive)) as source:
        files = {}
        if len(source.infolist()) > 256 or sum(item.file_size for item in source.infolist()) > 50 * 1024 * 1024:
            raise UpdateError('archive_too_large')
        for item in source.infolist():
            parts = PurePosixPath(item.filename).parts
            if (len(parts) < 2 or parts[0] != 'codex-quota-monitor' or '..' in parts
                    or item.is_dir() or item.file_size > MAX_ARCHIVE
                    or (item.external_attr >> 16) & 0o170000 not in (0, 0o100000)):
                raise UpdateError('invalid_archive_entry')
            relative = '/'.join(parts[1:])
            if relative in files:
                raise UpdateError('duplicate_archive_entry')
            files[relative] = source.read(item)
    if 'install-manifest.json' not in files or 'renderer/manifest.json' not in files:
        raise UpdateError('release_manifest_missing')
    manifest = json.loads(files['install-manifest.json'])
    renderer = json.loads(files['renderer/manifest.json'])
    expected = manifest.get('files')
    if (manifest.get('status') != 'release' or manifest.get('version') != version
            or not isinstance(expected, dict) or set(expected) != set(files) - {'install-manifest.json'}
            or renderer.get('status') != 'independent-v2-release'):
        raise UpdateError('release_manifest_invalid')
    for name, digest in expected.items():
        if hashlib.sha256(files[name]).hexdigest() != digest:
            raise UpdateError('release_file_mismatch')
    consumer = renderer.get('consumer', {})
    if (consumer.get('sha256') != hashlib.sha256(files['renderer/consumer.js']).hexdigest()
            or not {'run.py', 'QuotaMenu', 'renderer/LICENSE', 'renderer/NOTICE'} <= set(files)):
        raise UpdateError('release_content_invalid')
    if files['QuotaMenu'][:4] not in (b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca'):
        raise UpdateError('menu_binary_invalid')
    if destination.exists():
        if not destination.is_dir() or any(destination.iterdir()):
            raise UpdateError('destination_not_empty')
    else:
        destination.mkdir(mode=0o700)
    for name, data in files.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        if name == 'QuotaMenu':
            path.chmod(0o755)
    return consumer['sha256']


def _config(old_path, new_root, version, consumer_digest):
    old_path = Path(old_path).resolve()
    config = json.loads(old_path.read_text())
    for key in ('session_root', 'history_root', 'notification_root', 'status_root'):
        if key in config:
            config[key] = str((old_path.parent / config[key]).resolve())
    if 'journals' in config:
        config['journals'] = {key: str((old_path.parent / value).resolve())
                              for key, value in config['journals'].items()}
    config['consumer'] = {'path':'renderer/consumer.js', 'sha256':consumer_digest}
    config['version'] = version
    config['update_url'] = RELEASE_API
    target = new_root / 'config.json'
    with target.open('x') as stream:
        json.dump(config, stream, indent=2)
        stream.write('\n')
    target.chmod(0o600)
    return target


def _switch(service, config, new_root, runner=subprocess.run, settle=time.sleep):
    if not service._owned():
        raise UpdateError('managed_service_required')
    with service.path.open('rb') as stream:
        old_service = plistlib.load(stream)
    if Path(old_service['ProgramArguments'][3]).resolve() != Path(config).resolve():
        raise UpdateError('service_config_mismatch')
    menu = service._menu_owned()
    if service.menu_path.exists() and not menu:
        raise UpdateError('foreign_menu')
    old_menu = None
    if menu:
        with service.menu_path.open('rb') as stream:
            old_menu = plistlib.load(stream)
    new_service = dict(old_service)
    new_service['ProgramArguments'] = [old_service['ProgramArguments'][0],
        str(new_root / 'run.py'), '--config', str(new_root / 'config.json'), '--wait-for-host']
    new_service['WorkingDirectory'] = str(new_root)
    new_menu = None
    if menu:
        new_menu = dict(old_menu)
        new_menu['ProgramArguments'] = [str(new_root / 'QuotaMenu'), '--run',
            old_menu['ProgramArguments'][2]]
        new_menu['WorkingDirectory'] = str(new_root)

    def launch(*args):
        result = runner(['/bin/launchctl', *args], capture_output=True, timeout=15, check=False)
        if result.returncode:
            raise UpdateError('launchctl_failed')

    def write(path, value):
        temporary = path.with_suffix('.update-tmp')
        with temporary.open('wb') as stream:
            plistlib.dump(value, stream)
        temporary.replace(path)

    domain = service.domain
    stopped_menu = stopped_service = False
    try:
        if menu:
            launch('bootout', domain + '/' + MENU_LABEL); stopped_menu = True; settle(0.8)
        launch('bootout', domain + '/' + LABEL); stopped_service = True; settle(0.8)
        write(service.path, new_service)
        launch('bootstrap', domain, str(service.path))
        if menu:
            write(service.menu_path, new_menu)
            launch('bootstrap', domain, str(service.menu_path))
    except (OSError, UpdateError):
        # Restore the old plists and ask launchd to run the previous installation.
        try:
            if stopped_service:
                runner(['/bin/launchctl', 'bootout', domain + '/' + LABEL],
                       capture_output=True, timeout=15, check=False)
                settle(0.8)
                write(service.path, old_service)
                launch('bootstrap', domain, str(service.path))
            if stopped_menu:
                runner(['/bin/launchctl', 'bootout', domain + '/' + MENU_LABEL],
                       capture_output=True, timeout=15, check=False)
                settle(0.8)
                write(service.menu_path, old_menu)
                launch('bootstrap', domain, str(service.menu_path))
        except (OSError, UpdateError):
            pass
        raise UpdateError('service_switch_failed') from None


def install(version, config, *, fetch=_fetch, switch=_switch):
    if sys.platform != 'darwin':
        raise UpdateError('macos_required')
    root = Path(__file__).resolve().parent.parent
    service = Service(root=root)
    if not service._owned():
        raise UpdateError('managed_service_required')
    target = root.parent / ('codex-quota-monitor-v' + version)
    if target.exists() or target.is_symlink():
        raise UpdateError('target_exists')
    archive = _archive(version, fetch)
    stage = Path(tempfile.mkdtemp(prefix='.quota-update-', dir=str(root.parent)))
    try:
        digest = _extract(archive, stage, version)
        _config(config, stage, version, digest)
        stage.rename(target)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    switch(service, config, target)
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True)
    parser.add_argument('--config', required=True)
    args = parser.parse_args(argv)
    try:
        install(args.version, args.config)
    except (OSError, ValueError, TypeError, KeyError, zipfile.BadZipFile):
        try:
            result = Path(args.config).resolve().parent / '.quota-update-result.json'
            with result.open('w') as stream:
                json.dump({'status':'failed', 'version':args.version, 'at':time.time()}, stream)
            result.chmod(0o600)
        except OSError:
            pass
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
