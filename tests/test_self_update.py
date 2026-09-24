import hashlib
from io import BytesIO
import json
from pathlib import Path
import plistlib
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from quota_monitor import self_update
from quota_monitor.service import LABEL, MENU_LABEL, Service


class SelfUpdateTests(unittest.TestCase):
    def test_github_metadata_uses_json_accept_header(self):
        seen = []
        def opened(request, timeout):
            seen.append(request.get_header('Accept'))
            return BytesIO(b'{}')
        with patch.object(self_update, 'urlopen', opened):
            self.assertEqual(self_update._fetch(self_update.RELEASE_API, 100), b'{}')
            self.assertEqual(self_update._fetch('https://example.invalid/file.zip', 100), b'{}')
        self.assertEqual(seen, ['application/vnd.github+json', 'application/octet-stream'])

    def bundle(self, version='2.0.4'):
        files = {
            'run.py': b'pass\n',
            'QuotaMenu': b'\xca\xfe\xba\xbe' + b'menu',
            'renderer/consumer.js': b'(() => {})()',
            'renderer/LICENSE': b'MIT',
            'renderer/NOTICE': b'notice',
        }
        files['renderer/manifest.json'] = json.dumps({
            'status':'independent-v2-release',
            'consumer':{'sha256':hashlib.sha256(files['renderer/consumer.js']).hexdigest()},
        }).encode()
        files['install-manifest.json'] = json.dumps({
            'status':'release', 'version':version,
            'files':{name:hashlib.sha256(data).hexdigest() for name, data in files.items()},
        }).encode()
        output = BytesIO()
        with zipfile.ZipFile(output, 'w') as stream:
            for name, data in files.items():
                stream.writestr('codex-quota-monitor/' + name, data)
        return output.getvalue()

    def test_official_release_download_and_extract(self):
        version = '2.0.5'
        archive = self.bundle(version)
        name = 'codex-quota-monitor-v{}-macos.zip'.format(version)
        base = 'https://github.com/ailble-abum/codex-quota-monitor/releases/download/v{}/'.format(version)
        responses = {
            self_update.RELEASE_API: json.dumps({'tag_name':'v' + version, 'draft':False,
                'prerelease':False, 'assets':[{'name':key,'browser_download_url':base + key}
                    for key in (name, 'SHA256SUMS')]}).encode(),
            base + 'SHA256SUMS': ('{}  {}\n'.format(hashlib.sha256(archive).hexdigest(), name)).encode(),
            base + name: archive,
        }
        fetch = lambda url, limit: responses[url]
        self.assertEqual(self_update._archive(version, fetch), archive)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory, 'bundle')
            root.mkdir()
            digest = self_update._extract(archive, root, version)
            self.assertEqual(digest, hashlib.sha256(b'(() => {})()').hexdigest())
            self.assertTrue((root / 'QuotaMenu').stat().st_mode & 0o100)
            original = Path(directory, 'old', 'config.json')
            original.parent.mkdir()
            original.write_text(json.dumps({'origin':'http://127.0.0.1:9222', 'page_url':'test',
                'session_root':'sessions', 'history_root':'history',
                'consumer':{'path':'old/consumer.js','sha256':'0' * 64}}))
            migrated = self_update._config(original, root, version, digest)
            value = json.loads(migrated.read_text())
            self.assertEqual(value['session_root'], str((original.parent / 'sessions').resolve()))
            self.assertEqual(value['history_root'], str((original.parent / 'history').resolve()))
            self.assertEqual(value['consumer']['sha256'], digest)
            self.assertEqual(value['update_url'], self_update.RELEASE_API)
            self.assertEqual(migrated.stat().st_mode & 0o077, 0)

    def test_bad_checksum_and_traversal_are_rejected(self):
        archive = self.bundle()
        with tempfile.TemporaryDirectory() as directory:
            with zipfile.ZipFile(BytesIO(archive)) as source:
                names = source.namelist()
                values = [(name, source.read(name)) for name in names]
            output = BytesIO()
            with zipfile.ZipFile(output, 'w') as stream:
                for name, data in values:
                    stream.writestr(name, data)
                stream.writestr('codex-quota-monitor/../escape', b'bad')
            with self.assertRaises(self_update.UpdateError):
                self_update._extract(output.getvalue(), Path(directory, 'bundle'), '2.0.4')
            broken = BytesIO()
            with zipfile.ZipFile(broken, 'w') as stream:
                for name, data in values:
                    stream.writestr(name, b'tampered' if name.endswith('/run.py') else data)
            with self.assertRaises(self_update.UpdateError):
                self_update._extract(broken.getvalue(), Path(directory, 'broken'), '2.0.4')

    def test_service_switch_and_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            old = (base / 'old').resolve()
            new = (base / 'new').resolve()
            old.mkdir(); new.mkdir()
            config = old / 'config.json'
            config.write_text('{}')
            service = Service(root=old, agent_dir=base, uid=lambda: 501)
            old_plist = {'Label': LABEL,
                'ProgramArguments':['/usr/bin/python3',str(old / 'run.py'),'--config',str(config),'--wait-for-host'],
                'WorkingDirectory':str(old)}
            with service.path.open('wb') as stream:
                plistlib.dump(old_plist, stream)
            calls = []
            pauses = []
            def success(command, **_):
                calls.append(command)
                return SimpleNamespace(returncode=0)
            self_update._switch(service, config, new, success, settle=pauses.append)
            with service.path.open('rb') as stream:
                self.assertEqual(plistlib.load(stream)['ProgramArguments'][1], str(new / 'run.py'))
            self.assertEqual([call[1] for call in calls], ['bootout', 'bootstrap'])
            self.assertEqual(pauses, [0.8])
            with service.path.open('wb') as stream:
                plistlib.dump(old_plist, stream)
            def fail_new_bootstrap(command, **_):
                with service.path.open('rb') as stream:
                    active = plistlib.load(stream)['WorkingDirectory']
                return SimpleNamespace(returncode=1 if command[1] == 'bootstrap' and
                                       active == str(new) else 0)
            with self.assertRaises(self_update.UpdateError):
                self_update._switch(service, config, new, fail_new_bootstrap, settle=lambda _: None)
            with service.path.open('rb') as stream:
                self.assertEqual(plistlib.load(stream), old_plist)

    def test_menu_switch_failure_restores_both_agents(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            old = (base / 'old').resolve(); new = (base / 'new').resolve()
            old.mkdir(); new.mkdir()
            config = old / 'config.json'; config.write_text('{}')
            service = Service(root=old, agent_dir=base, uid=lambda: 501)
            old_service = {'Label':LABEL, 'ProgramArguments':['/usr/bin/python3',
                str(old / 'run.py'), '--config', str(config), '--wait-for-host'],
                'WorkingDirectory':str(old)}
            old_menu = {'Label':MENU_LABEL, 'ProgramArguments':[str(old / 'QuotaMenu'),
                '--run', str(old / 'history.json')], 'WorkingDirectory':str(old)}
            for path, value in ((service.path, old_service), (service.menu_path, old_menu)):
                with path.open('wb') as stream:
                    plistlib.dump(value, stream)
            def fail_menu(command, **_):
                return SimpleNamespace(returncode=int(command[1] == 'bootstrap' and
                    command[-1] == str(service.menu_path)))
            with self.assertRaises(self_update.UpdateError):
                self_update._switch(service, config, new, fail_menu, settle=lambda _: None)
            for path, expected in ((service.path, old_service), (service.menu_path, old_menu)):
                with path.open('rb') as stream:
                    self.assertEqual(plistlib.load(stream), expected)


if __name__ == '__main__':
    unittest.main()
