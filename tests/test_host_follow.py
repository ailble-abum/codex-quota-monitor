import plistlib
from pathlib import Path
import tempfile
import unittest

from quota_monitor.host_follow import HostFollower, HostFollowError


class Result:
    def __init__(self, returncode=0, stdout=''):
        self.returncode, self.stdout = returncode, stdout


class HostFollowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = Path(self.temp.name) / 'Codex.app'
        (self.app / 'Contents/MacOS').mkdir(parents=True)
        (self.app / 'Contents/MacOS/Codex').touch()
        with (self.app / 'Contents/Info.plist').open('wb') as stream:
            plistlib.dump({'CFBundleIdentifier':'com.example.codex', 'CFBundleExecutable':'Codex'}, stream)
        self.calls, self.running, self.now = [], [None], [100.0]

        def run(args, **_):
            self.calls.append(args)
            if args[:2] == ['pgrep', '-x']:
                return Result(0, str(self.running[0]) if self.running[0] else '')
            if args[:1] == ['osascript']:
                self.running[0] = None
            return Result()
        self.run = run

    def tearDown(self):
        self.temp.cleanup()

    def test_relaunches_known_app_with_local_debug_flags_once(self):
        self.running[0] = 1234
        follower = HostFollower(str(self.app), 9222, runner=self.run, sleeper=lambda _: None,
                                clock=lambda: self.now[0], cooldown=30)
        self.assertEqual(follower.ensure(), 'launch_requested')
        self.running[0] = 5678
        self.assertEqual(follower.ensure(), 'backoff')
        self.assertEqual(self.calls[0], ['pgrep', '-x', 'Codex'])
        self.assertEqual(next(call for call in self.calls if call[0] == 'open')[-1],
                         '--remote-allow-origins=http://127.0.0.1:9222')

    def test_waits_after_user_quit_until_app_is_opened_again(self):
        follower = HostFollower(str(self.app), 9222, runner=self.run, sleeper=lambda _: None,
                                clock=lambda: self.now[0], cooldown=30)
        self.assertEqual(follower.ensure(), 'waiting_host')
        self.assertEqual([call for call in self.calls if call[0] in ('open', 'osascript')], [])
        self.running[0] = 1234
        self.assertEqual(follower.ensure(), 'launch_requested')
        self.running[0] = None
        self.assertEqual(follower.ensure(), 'waiting_host')
        self.assertEqual(len([call for call in self.calls if call[0] == 'open']), 1)

    def test_rejects_untrusted_or_incomplete_app(self):
        with self.assertRaises(HostFollowError):
            HostFollower('/tmp/Codex.app', 9222)
        with self.assertRaises(HostFollowError):
            HostFollower(str(self.app), 0)


if __name__ == '__main__':
    unittest.main()
