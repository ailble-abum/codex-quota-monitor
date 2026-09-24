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

    def test_report_shows_current_windows_and_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / 'QuotaMenu'
            source = Path(__file__).resolve().parents[1] / 'quota_monitor/QuotaMenu.swift'
            subprocess.run(['swiftc', str(source), '-o', str(binary)], check=True,
                           capture_output=True, timeout=30)
            import time
            now = time.time()
            history = root / 'history.json'
            history.write_text(json.dumps([{
                'at': now - 10, 'accountKey': 'a' * 64,
                'windows': [{'key': 'primary', 'remaining': 35, 'duration': 300,
                             'resetsAt': now + 3600},
                            {'key': 'secondary', 'remaining': 80, 'duration': 10080}],
                'context': {'latest_context_percent': 42}}]))
            result = subprocess.run([str(binary), '--report', str(history)],
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('5 小时额度：剩余 35%', result.stdout)
            self.assertIn('7 天额度：剩余 80%', result.stdout)
            self.assertIn('重置', result.stdout)
            self.assertIn('当前上下文：42%', result.stdout)

            history.write_text(json.dumps([{'at': now - 180, 'accountKey': 'a' * 64,
                'windows': [{'key': 'primary', 'remaining': 35}],
                'context': {'latest_context_percent': 42}}]))
            stale = subprocess.run([str(binary), '--report', str(history)],
                                   capture_output=True, text=True, timeout=5)
            self.assertIn('当前数据：暂无有效采样', stale.stdout)
            self.assertNotIn('当前上下文：42%', stale.stdout)


if __name__ == '__main__':
    unittest.main()
