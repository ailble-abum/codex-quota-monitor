import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

class BundleTests(unittest.TestCase):
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
