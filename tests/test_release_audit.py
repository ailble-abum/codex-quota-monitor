import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys
import zipfile

spec = importlib.util.spec_from_file_location('audit_release', Path(__file__).parents[1] / 'tools/audit_release.py')
audit_release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_release)


class ReleaseAuditTests(unittest.TestCase):
    def test_candidate_archive_is_reproducible_and_not_labeled_release(self):
        root = self.make_bundle()
        with tempfile.TemporaryDirectory() as directory:
            destinations = [Path(directory, name) for name in ('first', 'second')]
            command = Path(__file__).parents[1] / 'tools/package_candidate.py'
            for destination in destinations:
                result = subprocess.run([sys.executable, str(command), str(root), str(destination),
                    '--label', 'v2.0.0-rc.1'], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            first = destinations[0] / 'codex-quota-monitor-v2.0.0-rc.1-macos.zip'
            second = destinations[1] / first.name
            self.assertEqual(first.read_bytes(), second.read_bytes())
            manifest = json.loads((destinations[0] / 'CANDIDATE.json').read_text())
            self.assertEqual(manifest['status'], 'candidate-not-release')
            self.assertEqual(manifest['sha256'], hashlib.sha256(first.read_bytes()).hexdigest())
            with zipfile.ZipFile(first) as archive:
                self.assertIn('codex-quota-monitor/renderer/LICENSE', archive.namelist())
                self.assertIn('codex-quota-monitor/renderer/NOTICE', archive.namelist())
            repeated = subprocess.run([sys.executable, str(command), str(root), str(destinations[0]),
                '--label', 'v2.0.0-rc.1'], capture_output=True, text=True)
            self.assertEqual(repeated.returncode, 2)

    def make_bundle(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(root))
        for name in audit_release.REQUIRED:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('ok', encoding='utf-8')
        consumer = root / 'renderer/consumer.js'
        data = b'(() => {})()'
        consumer.write_bytes(data)
        (root / 'renderer/manifest.json').write_text(json.dumps({
            'status': 'independent-v2-candidate',
            'consumer': {'path': 'consumer.js', 'sha256': hashlib.sha256(data).hexdigest()},
            'visualResourceSHA256': {name: '0' * 64 for name in audit_release.VISUAL_RESOURCES},
        }))
        files = {path: hashlib.sha256((root / path).read_bytes()).hexdigest()
                 for path in audit_release.REQUIRED if path != 'install-manifest.json'}
        (root / 'install-manifest.json').write_text(json.dumps({'files': files}))
        return root

    def test_audits_required_hashes_and_source_markers(self):
        root = self.make_bundle()
        result = audit_release.audit(root)
        self.assertEqual(result['status'], 'audited')
        (root / 'renderer/consumer.js').write_text('context_token_injector.py')
        with self.assertRaises(ValueError):
            audit_release.audit(root)

    def test_rejects_sensitive_material(self):
        root = self.make_bundle()
        (root / 'session.jsonl').write_text('{}')
        with self.assertRaises(ValueError):
            audit_release.audit(root)

    def test_rejects_unmanifested_release_files(self):
        root = self.make_bundle()
        (root / 'unexpected.txt').write_text('not part of the audited bundle')
        with self.assertRaises(ValueError):
            audit_release.audit(root)

    def test_rejects_manifest_paths_outside_the_release_tree(self):
        root = self.make_bundle()
        manifest_path = root / 'install-manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['files']['../outside.txt'] = '0' * 64
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            audit_release.audit(root)

    def test_rejects_renderer_paths_outside_the_release_tree(self):
        root = self.make_bundle()
        manifest_path = root / 'renderer/manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['consumer']['path'] = '../../outside.js'
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            audit_release.audit(root)

    def test_rejects_release_symlinks(self):
        root = self.make_bundle()
        consumer = root / 'renderer/consumer.js'
        data = consumer.read_bytes()
        outside = root.parent / (root.name + '-consumer.js')
        outside.write_bytes(data)
        self.addCleanup(lambda: outside.unlink(missing_ok=True))
        consumer.unlink()
        try:
            consumer.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest('symlink creation unavailable')
        with self.assertRaises(ValueError):
            audit_release.audit(root)


if __name__ == '__main__':
    unittest.main()
