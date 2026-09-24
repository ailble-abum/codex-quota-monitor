import hashlib
import json
from pathlib import Path
import plistlib
import sys
import tempfile
import unittest

from quota_monitor.service import LABEL, Service, ServiceError


class Result:
    def __init__(self, code=0, stdout='state = running'):
        self.returncode, self.stdout = code, stdout


class ServiceTests(unittest.TestCase):
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
            self.assertEqual(service.doctor(), {'service': 'running', 'config': 'valid'})
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
