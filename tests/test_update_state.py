import asyncio
import unittest

from quota_monitor.update_state import UpdateSource, project


class UpdateStateTests(unittest.TestCase):
    def test_projection_is_bounded_and_compares_release_versions(self):
        self.assertEqual(project({'tag_name': 'v0.2.1', 'html_url': 'https://example.invalid/release'})['status'],
                         'update_available')
        current = project({'version': '0.2.0', 'url': 'https://example.invalid/release'}, current='0.2.0-beta')
        self.assertEqual(current['status'], 'up_to_date')
        self.assertNotIn('secret', repr(project({'version': '0.2.1', 'notes': 'secret'})))
        self.assertEqual(project({'version': '0.2.1', 'url': 'http://example.invalid'})['status'],
                         'update_available')

    def test_source_is_quiet_without_explicit_url(self):
        async def check():
            source = UpdateSource()
            self.assertEqual(source.snapshot(), {'status': 'not_configured'})
            await source.close()
        asyncio.run(check())


if __name__ == '__main__':
    unittest.main()
