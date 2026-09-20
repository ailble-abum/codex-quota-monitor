import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

class BundleTests(unittest.TestCase):
    def test_rejects_malformed_manifest_and_consumer_shapes(self):
        tool = Path(__file__).resolve().parents[1] / 'tools/install_preview.py'
        invalid_manifests = (
            ('manifest-list', []),
            ('manifest-null', None),
            ('manifest-string', 'not-an-object'),
            ('manifest-integer', 17),
            ('consumer-missing', {'status': 'derived-isolated-candidate'}),
            ('consumer-null', {'status': 'derived-isolated-candidate', 'consumer': None}),
            ('consumer-list', {'status': 'derived-isolated-candidate', 'consumer': []}),
            ('consumer-missing-sha256', {
                'status': 'derived-isolated-candidate', 'consumer': {},
            }),
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, manifest in invalid_manifests:
                with self.subTest(name=name):
                    candidate = root / f'{name}-candidate'
                    candidate.mkdir()
                    (candidate / 'consumer.js').write_bytes(b'(() => {})()')
                    (candidate / 'manifest.json').write_text(json.dumps(manifest))
                    for attribution in ('LICENSE', 'NOTICE'):
                        (candidate / attribution).write_text('Synthetic attribution')
                    target = root / f'{name}-installed'
                    result = subprocess.run(
                        [sys.executable, str(tool), str(candidate), str(target)],
                        capture_output=True, text=True,
                    )
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(result.stderr, 'preview_install_failed\n')
                    self.assertEqual(result.stdout, '')
                    self.assertFalse(target.exists())
                    self.assertEqual(list(root.glob('.quota-v2-*')), [])

    def test_standalone_bundle_and_refuse_overwrite(self):
        tool = Path(__file__).resolve().parents[1] / 'tools/install_preview.py'
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); candidate = root / 'candidate'; candidate.mkdir()
            data = b'(() => {})()'
            (candidate / 'consumer.js').write_bytes(data)
            (candidate / 'manifest.json').write_text(json.dumps({'status': 'derived-isolated-candidate',
                'consumer': {'sha256': hashlib.sha256(data).hexdigest()}}))
            for name in ('LICENSE', 'NOTICE'):
                (candidate / name).write_text('Synthetic attribution')
            target = root / 'installed'
            command = [sys.executable, str(tool), str(candidate), str(target)]
            result = subprocess.run(command, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((target / 'quota_monitor/account.py').exists())
            self.assertEqual((target / 'renderer/NOTICE').read_text(), 'Synthetic attribution')
            result = subprocess.run([sys.executable, str(target / 'run.py'), '--help'], cwd=temp, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            other = root / 'bad'
            (candidate / 'consumer.js').write_text('tampered')
            self.assertNotEqual(subprocess.run(command[:-1] + [str(other)], capture_output=True).returncode, 0)
            self.assertFalse(other.exists())
