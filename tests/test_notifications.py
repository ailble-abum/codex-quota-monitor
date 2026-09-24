import json
import tempfile
import unittest
from pathlib import Path

from quota_monitor.notifications import QuotaNotifier


class QuotaNotificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.messages = []
        self.now = 2000000000
        self.root = Path(self.temp.name)
        self.notifier = QuotaNotifier(self.root, sender=lambda message: self.messages.append(message) or True,
                                      clock=lambda: self.now)
        self.quota = {'status': 'live', 'updatedAt': self.now, 'accountKey': 'a' * 64,
                      'windows': [{'key': 'primary', 'duration': 300, 'remaining': 20,
                                   'resetsAt': self.now + 3600}]}

    def test_fresh_low_quota_sends_once_per_account_and_reset(self):
        self.assertEqual(self.notifier.notify(self.quota), 1)
        self.assertEqual(self.notifier.notify(self.quota), 0)
        self.assertEqual(QuotaNotifier(self.root, sender=lambda _: True,
                                       clock=lambda: self.now).notify(self.quota), 0)
        self.assertEqual(len(self.messages), 1)
        state = (self.root / 'notifications.json').read_text()
        self.assertNotIn('a' * 64, state)
        self.assertEqual(len(json.loads(state)), 1)
        self.quota['accountKey'] = 'b' * 64
        self.assertEqual(self.notifier.notify(self.quota), 1)
        self.quota['windows'][0]['resetsAt'] += 3600
        self.assertEqual(self.notifier.notify(self.quota), 1)

    def test_stale_or_invalid_data_never_sends(self):
        self.quota['updatedAt'] -= 120
        self.assertEqual(self.notifier.notify(self.quota), 0)
        self.quota['updatedAt'] = self.now
        for remaining in (21, -1, '10'):
            self.quota['windows'][0]['remaining'] = remaining
            self.assertEqual(self.notifier.notify(self.quota), 0)
        self.quota['windows'][0]['remaining'] = 10
        self.quota['status'] = 'stale'
        self.assertEqual(self.notifier.notify(self.quota), 0)
        self.assertEqual(self.messages, [])

    def test_failed_sender_does_not_record_delivery(self):
        notifier = QuotaNotifier(self.root, sender=lambda _: False, clock=lambda: self.now)
        self.assertEqual(notifier.notify(self.quota), 0)
        self.assertFalse((self.root / 'notifications.json').exists())
