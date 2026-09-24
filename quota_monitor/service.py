"""Explicit per-user macOS service control for an installed V2 runtime."""
import argparse
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys

from .live import load_config
from .consumer import load_consumer
from .host_follow import HostFollower


LABEL = 'local.codex-quota-monitor-v2'
MENU_LABEL = LABEL + '-menu'


class ServiceError(ValueError):
    pass


class Service:
    def __init__(self, root=None, agent_dir=None, *, runner=subprocess.run, uid=os.getuid,
                 python=None):
        self.root = Path(root or Path(__file__).resolve().parent.parent).resolve()
        self.agent_dir = Path(agent_dir or Path.home() / 'Library/LaunchAgents')
        self.path = self.agent_dir / (LABEL + '.plist')
        self.menu_path = self.agent_dir / (MENU_LABEL + '.plist')
        self.runner, self.uid = runner, uid
        self.python = str(Path(python or sys.executable).resolve())
        self.domain = 'gui/{}'.format(uid)

    def _launchctl(self, *args):
        try:
            return self.runner(['/bin/launchctl', *args], capture_output=True, text=True,
                               timeout=10, check=False)
        except (OSError, subprocess.TimeoutExpired):
            raise ServiceError('launchctl_unavailable') from None

    def _owned(self):
        if self.path.is_symlink():
            return False
        try:
            with self.path.open('rb') as stream:
                value = plistlib.load(stream)
            args = value.get('ProgramArguments')
            return (value.get('Label') == LABEL and isinstance(args, list) and
                    len(args) >= 2 and args[1] == str(self.root / 'run.py'))
        except (OSError, ValueError, plistlib.InvalidFileException, AttributeError):
            return False

    @staticmethod
    def _validate_config(config):
        try:
            from .runtime import local_origin
        except ModuleNotFoundError:
            raise ServiceError('dependency_unavailable') from None
        settings = load_config(config)
        if (settings.get('host') != 'codex-sidebar' or settings.get('panel') is not True or
                not settings.get('host_app') or not settings.get('consumer')):
            raise ServiceError('service_config_incomplete')
        HostFollower(settings['host_app'], local_origin(settings['origin'])[1])
        load_consumer(settings['consumer'])

    def install(self, config):
        config = Path(config).resolve()
        if self.path.exists() or self.path.is_symlink():
            raise ServiceError('service_exists')
        if not (self.root / 'run.py').is_file() or not Path(self.python).is_file():
            raise ServiceError('runtime_missing')
        self._validate_config(config)
        value = {'Label': LABEL, 'ProgramArguments': [self.python, str(self.root / 'run.py'),
                 '--config', str(config), '--wait-for-host'], 'WorkingDirectory': str(self.root),
                 'RunAtLoad': True, 'KeepAlive': True}
        self.agent_dir.mkdir(parents=True, exist_ok=True)
        created = False
        try:
            with self.path.open('xb') as stream:
                created = True
                plistlib.dump(value, stream)
            if self._launchctl('bootstrap', self.domain, str(self.path)).returncode != 0:
                raise ServiceError('bootstrap_failed')
        except BaseException:
            if created:
                self.path.unlink(missing_ok=True)
            raise
        return 'installed'

    def status(self):
        if not self._owned():
            return 'not_installed' if not self.path.exists() else 'foreign_service'
        result = self._launchctl('print', self.domain + '/' + LABEL)
        if result.returncode != 0:
            return 'not_loaded'
        return 'running' if 'state = running' in result.stdout else 'loaded'

    def doctor(self):
        state = self.status()
        if state not in ('running', 'loaded'):
            return {'service': state, 'config': 'unchecked'}
        with self.path.open('rb') as stream:
            value = plistlib.load(stream)
        try:
            self._validate_config(value['ProgramArguments'][3])
            config = 'valid'
        except (OSError, ValueError, TypeError, KeyError):
            config = 'invalid'
        return {'service': state, 'config': config}

    def uninstall(self):
        if not self._owned():
            raise ServiceError('service_not_owned')
        if self.menu_path.exists() or self.menu_path.is_symlink():
            raise ServiceError('menu_still_installed')
        if self.status() in ('running', 'loaded'):
            if self._launchctl('bootout', self.domain + '/' + LABEL).returncode != 0:
                raise ServiceError('bootout_failed')
        self.path.unlink()
        return 'uninstalled'

    def menu_install(self, config):
        if not self._owned():
            raise ServiceError('service_not_owned')
        if self.menu_path.exists() or self.menu_path.is_symlink():
            raise ServiceError('menu_exists')
        settings = load_config(Path(config).resolve())
        history = settings.get('history_root')
        binary = self.root / 'QuotaMenu'
        if history is None or not binary.is_file() or not os.access(binary, os.X_OK):
            raise ServiceError('menu_config_incomplete')
        value = {'Label': MENU_LABEL,
                 'ProgramArguments': [str(binary), '--run', str(history / 'history.json')],
                 'WorkingDirectory': str(self.root), 'RunAtLoad': True, 'KeepAlive': True}
        with self.menu_path.open('xb') as stream:
            plistlib.dump(value, stream)
        try:
            if self._launchctl('bootstrap', self.domain, str(self.menu_path)).returncode != 0:
                raise ServiceError('menu_bootstrap_failed')
        except BaseException:
            self.menu_path.unlink(missing_ok=True)
            raise
        return 'menu_installed'

    def _menu_owned(self):
        if self.menu_path.is_symlink():
            return False
        try:
            with self.menu_path.open('rb') as stream:
                value = plistlib.load(stream)
            return (value.get('Label') == MENU_LABEL and
                    value.get('ProgramArguments', [])[:2] == [str(self.root / 'QuotaMenu'), '--run'])
        except (OSError, ValueError, plistlib.InvalidFileException, AttributeError):
            return False

    def menu_status(self):
        if not self._menu_owned():
            return 'not_installed' if not self.menu_path.exists() else 'foreign_service'
        result = self._launchctl('print', self.domain + '/' + MENU_LABEL)
        if result.returncode != 0:
            return 'not_loaded'
        return 'running' if 'state = running' in result.stdout else 'loaded'

    def menu_uninstall(self):
        if not self._menu_owned():
            raise ServiceError('service_not_owned')
        if self.menu_status() in ('running', 'loaded'):
            if self._launchctl('bootout', self.domain + '/' + MENU_LABEL).returncode != 0:
                raise ServiceError('bootout_failed')
        self.menu_path.unlink()
        return 'menu_uninstalled'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('install', 'status', 'doctor', 'uninstall',
                                           'menu-install', 'menu-status', 'menu-uninstall'))
    parser.add_argument('--config', type=Path)
    args = parser.parse_args(argv)
    if args.action in ('install', 'menu-install') and args.config is None:
        parser.error('install requires --config')
    service = Service()
    try:
        result = getattr(service, args.action.replace('-', '_'))(args.config) if args.action in (
            'install', 'menu-install') else getattr(service, args.action.replace('-', '_'))()
    except (OSError, ValueError, TypeError):
        print(json.dumps({'status': 'service_error'}))
        return 2
    print(json.dumps(result if isinstance(result, dict) else {'status': result}))
    return 0 if args.action != 'doctor' or result == {'service': 'running', 'config': 'valid'} else 2


if __name__ == '__main__':
    raise SystemExit(main())
