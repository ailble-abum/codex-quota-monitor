import hashlib
import json
import os
from pathlib import Path
import plistlib
import sys
import tempfile
import unittest
from unittest.mock import patch

from quota_monitor.service import LABEL, MENU_LABEL, Service, ServiceError, main
from quota_monitor.runtime_marker import StatusStore


class Result:
    def __init__(self, code=0, stdout='state = running'):
        self.returncode, self.stdout = code, stdout


class ServiceTests(unittest.TestCase):
    def test_default_launch_domain_uses_numeric_user_id(self):
        with tempfile.TemporaryDirectory() as directory:
            service = Service(root=directory, agent_dir=directory)
            self.assertEqual(service.domain, 'gui/{}'.format(os.getuid()))

    def test_doctor_requires_reported_panel_update(self):
        for panel, expected in [(None, 2), ('missing', 2), ('updated', 0)]:
            result = {'service': 'running', 'config': 'valid'}
            if panel is not None:
                result['panel'] = panel
            with self.subTest(panel=panel), patch('quota_monitor.service.Service') as factory, \
                    patch('builtins.print'):
                factory.return_value.doctor.return_value = result
                self.assertEqual(main(['doctor']), expected)

    def test_menu_agent_requires_owned_service_and_explicit_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'run.py').write_text('pass\n')
            binary = root / 'QuotaMenu'
            binary.write_text('#!/bin/sh\n')
            binary.chmod(0o700)
            calls = []
            def run(args, **_):
                calls.append(args)
                return Result()
            service = Service(root, root / 'agents', runner=run, uid=501, python=sys.executable)
            config = root / 'config.json'
            config.write_text(json.dumps({'origin': 'http://127.0.0.1:9222',
                'page_url': 'app://-/index.html', 'session_root': 'sessions',
                'history_root': 'private-history'}))
            with self.assertRaisesRegex(ServiceError, 'service_not_owned'):
                service.menu_install(config)
            service.agent_dir.mkdir()
            with service.path.open('wb') as stream:
                plistlib.dump({'Label': LABEL, 'ProgramArguments': [sys.executable,
                    str(service.root / 'run.py')]}, stream)
            self.assertEqual(service.menu_install(config), 'menu_installed')
            with service.menu_path.open('rb') as stream:
                agent = plistlib.load(stream)
            self.assertEqual(agent['Label'], MENU_LABEL)
            self.assertEqual(agent['ProgramArguments'][-1], str(service.root / 'private-history/history.json'))
            self.assertEqual(service.menu_status(), 'running')
            with self.assertRaisesRegex(ServiceError, 'menu_still_installed'):
                service.uninstall()
            self.assertEqual(service.menu_uninstall(), 'menu_uninstalled')
            self.assertEqual(calls[-1][1:3], ['bootout', 'gui/501/' + MENU_LABEL])
            config.write_text(json.dumps({'origin': 'http://127.0.0.1:9222',
                'page_url': 'app://-/index.html', 'session_root': 'sessions'}))
            with self.assertRaisesRegex(ServiceError, 'menu_config_incomplete'):
                service.menu_install(config)

    def test_install_doctor_and_uninstall_only_owned_agent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'run.py').write_text('pass\n')
            app = root / 'Codex.app'
            (app / 'Contents/MacOS').mkdir(parents=True)
            (app / 'Contents/MacOS/Codex').touch()
            with (app / 'Contents/Info.plist').open('wb') as stream:
                plistlib.dump({'CFBundleIdentifier': 'example.codex',
                               'CFBundleExecutable': 'Codex'}, stream)
            consumer = root / 'consumer.js'
            consumer.write_text('(() => {})()')
            config = root / 'config.json'
            config.write_text(json.dumps({
                'origin': 'http://127.0.0.1:9222', 'page_url': 'app://-/index.html',
                'session_root': 'sessions', 'host': 'codex-sidebar', 'panel': True,
                'status_root': 'runtime-state',
                'host_app': str(app), 'consumer': {'path': 'consumer.js',
                    'sha256': hashlib.sha256(consumer.read_bytes()).hexdigest()}}))
            calls = []
            def run(args, **_):
                calls.append(args)
                return Result()
            service = Service(root, root / 'agents', runner=run, uid=501, python=sys.executable)
            self.assertEqual(service.install(config), 'installed')
            with service.path.open('rb') as stream:
                agent = plistlib.load(stream)
            self.assertEqual(agent['Label'], LABEL)
            self.assertEqual(agent['ProgramArguments'][-1], '--wait-for-host')
            self.assertEqual(calls[0][1:3], ['bootstrap', 'gui/501'])
            self.assertEqual(service.doctor(), {'service': 'running', 'config': 'valid', 'panel': 'missing'})
            StatusStore(root / 'runtime-state').write('updated')
            self.assertEqual(service.doctor(), {'service': 'running', 'config': 'valid', 'panel': 'updated'})
            self.assertEqual(service.uninstall(), 'uninstalled')
            self.assertFalse(service.path.exists())
            self.assertEqual(calls[-1][1:3], ['bootout', 'gui/501/' + LABEL])
            service.runner = lambda *_args, **_kw: Result(5)
            with self.assertRaisesRegex(ServiceError, 'bootstrap_failed'):
                service.install(config)
            self.assertFalse(service.path.exists())
            service.path.write_text('foreign')
            with self.assertRaisesRegex(ServiceError, 'service_exists'):
                service.install(config)
            self.assertEqual(service.status(), 'foreign_service')
            self.assertEqual(service.path.read_text(), 'foreign')


if __name__ == '__main__':
    unittest.main()
