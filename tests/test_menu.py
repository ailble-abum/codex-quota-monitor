import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(sys.platform == 'darwin', 'AppKit is macOS only')
class MenuTests(unittest.TestCase):
    def test_report_uses_latest_account_and_hides_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / 'QuotaMenu'
            source = Path(__file__).resolve().parents[1] / 'quota_monitor/QuotaMenu.swift'
            subprocess.run(['swiftc', str(source), '-o', str(binary)], check=True,
                           capture_output=True, timeout=30)
            import time
            now = time.time()
            rows = [
                {'at': now - 60, 'accountKey': 'a' * 64, 'windows': [{'remaining': 3}],
                 'model': 'old', 'projectLabel': 'Old', 'projectKey': 'c' * 64},
                {'at': now - 10, 'accountKey': 'b' * 64, 'windows': [{'remaining': 25}],
                 'model': 'new', 'projectLabel': 'New', 'projectKey': 'd' * 64},
            ]
            history = root / 'history.json'
            history.write_text(json.dumps(rows))
            result = subprocess.run([str(binary), '--report', str(history)],
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Codex · 25%', result.stdout)
            self.assertIn('本地 7 天采样：1', result.stdout)
            self.assertIn('主要项目：New 1', result.stdout)
            self.assertNotIn('Old', result.stdout)
            self.assertNotIn(str(root), result.stdout)


if __name__ == '__main__':
    unittest.main()
