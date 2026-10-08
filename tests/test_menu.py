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
            self.assertEqual(result.stdout.splitlines()[0], '25%')
            self.assertIn('近 7 天采样：1', result.stdout)
            self.assertIn('常用项目：New 1', result.stdout)
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
                'context': {'latest_context_percent': 42},
                'activity': {'latestDailyTokens': 1234, 'lifetimeTokens': 5678}}]))
            result = subprocess.run([str(binary), '--report', str(history)],
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('5 小时额度：剩余 35%', result.stdout)
            self.assertIn('7 天额度：剩余 80%', result.stdout)
            self.assertIn('重置', result.stdout)
            self.assertIn('上下文已用：42%', result.stdout)
            self.assertIn('Token：最近日用量 1,234 · 累计 5,678', result.stdout)

            history.write_text(json.dumps([{'at': now - 180, 'accountKey': 'a' * 64,
                'windows': [{'key': 'primary', 'remaining': 35}],
                'context': {'latest_context_percent': 42}}]))
            stale = subprocess.run([str(binary), '--report', str(history)],
                                   capture_output=True, text=True, timeout=5)
            self.assertIn('等待用量更新', stale.stdout)
            self.assertNotIn('上下文已用：42%', stale.stdout)
            self.assertNotIn('Token：最近日用量', stale.stdout)
            self.assertEqual(stale.stdout.splitlines()[0], '—')

            history.unlink()
            missing = subprocess.run([str(binary), '--report', str(history)],
                                     capture_output=True, text=True, timeout=5)
            self.assertEqual(missing.stdout.splitlines(), ['—', '用量记录暂不可用'])
            history.write_text('[]')
            empty = subprocess.run([str(binary), '--report', str(history)],
                                   capture_output=True, text=True, timeout=5)
            self.assertIn('等待用量更新', empty.stdout)
            self.assertIn('近 7 天采样：0', empty.stdout)
            self.assertNotIn('V2', empty.stdout)

    def test_report_accepts_full_retention_history_and_bounds_oversized_reads(self):
        import time
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary, history = root / 'QuotaMenu', root / 'history.json'
            source = Path(__file__).resolve().parents[1] / 'quota_monitor/QuotaMenu.swift'
            subprocess.run(['swiftc', str(source), '-o', str(binary)], check=True,
                           capture_output=True, timeout=30)
            now = time.time()
            row = {'accountKey': 'a' * 64, 'model': 'model-' + 'x' * 100,
                   'projectKey': 'b' * 64, 'projectLabel': '示例项目' * 20,
                   'windows': [{'key': 'primary', 'remaining': 49, 'duration': 10080}],
                   'context': {'latest_context_percent': 37}}
            history.write_text(json.dumps([dict(row, at=now - i * 30) for i in range(10080)],
                                          ensure_ascii=False, separators=(',', ':')))
            self.assertGreater(history.stat().st_size, 4_000_000)
            result = subprocess.run([str(binary), '--report', str(history)],
                                    capture_output=True, text=True, check=True, timeout=5)
            self.assertEqual(result.stdout.splitlines()[0], '49%')
            self.assertIn('近 7 天采样：10080', result.stdout)
            self.assertIn('上下文已用：37%', result.stdout)
            with history.open('wb') as stream:
                stream.seek(16 * 1024 * 1024)
                stream.write(b' ')
            result = subprocess.run([str(binary), '--report', str(history)],
                                    capture_output=True, text=True, check=True, timeout=5)
            self.assertEqual(result.stdout.splitlines(), ['—', '用量记录暂不可用'])


if __name__ == '__main__':
    unittest.main()
