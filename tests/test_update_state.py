import asyncio
import unittest
from unittest.mock import patch

from quota_monitor.update_state import CURRENT_VERSION, UpdateSource, project


class UpdateStateTests(unittest.TestCase):
    def test_release_version(self):
        self.assertEqual(CURRENT_VERSION, '2.0.3')

    def test_projection_is_bounded_and_compares_release_versions(self):
        self.assertEqual(project({'tag_name': 'v2.0.4', 'html_url': 'https://example.invalid/release'})['status'],
                         'update_available')
        current = project({'version': '0.2.0', 'url': 'https://example.invalid/release'}, current='0.2.0-beta')
        self.assertEqual(current['status'], 'up_to_date')
        self.assertNotIn('secret', repr(project({'version': '0.2.1', 'notes': 'secret'})))
        self.assertEqual(project({'version': '2.0.4', 'url': 'http://example.invalid'})['status'],
                         'update_available')

    def test_source_is_quiet_without_explicit_url(self):
        async def check():
            source = UpdateSource()
            self.assertEqual(source.snapshot(), {'status': 'not_configured'})
            await source.close()
        asyncio.run(check())

    def test_manual_request_bypasses_interval_without_duplicate_task(self):
        async def check():
            source = UpdateSource('https://example.invalid/manifest', interval=3600, clock=lambda: 100)
            calls = []
            async def fake_read(_):
                calls.append(1)
                return {'status': 'up_to_date'}
            with patch('quota_monitor.update_state.read_manifest', fake_read):
                self.assertEqual(source.snapshot()['status'], 'checking')
                await source.task
                self.assertEqual(source.snapshot()['status'], 'up_to_date')
                self.assertEqual(len(calls), 1)
                self.assertEqual(source.snapshot(force=True)['status'], 'checking')
                await source.task
                self.assertEqual(len(calls), 2)
            await source.close()
        asyncio.run(check())


if __name__ == '__main__':
    unittest.main()
