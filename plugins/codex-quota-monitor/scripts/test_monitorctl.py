"""Tests for the LaunchAgent lifecycle helper in monitorctl.

These cover the decision that stranded the menu bar agent: rebuilding a healthy
loaded agent with bootout+bootstrap, and losing it when the bootstrap is
refused. launchctl itself is faked so the tests run anywhere.
"""
import plistlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import monitorctl

SERVICE = 'gui/501/local.test'


class LoadAgentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.plist = Path(self.tmp.name) / 'local.test.plist'
        self.previous = {'Label': 'local.test', 'ProgramArguments': ['/bin/old']}
        self.write(self.previous)
        self.calls = []
        sleep = mock.patch.object(monitorctl.time, 'sleep')
        sleep.start()
        self.addCleanup(sleep.stop)

    def write(self, payload):
        with self.plist.open('wb') as handle:
            plistlib.dump(payload, handle)

    def on_disk(self):
        with self.plist.open('rb') as handle:
            return plistlib.load(handle)

    def fake_run(self, failing=(), failing_until=None):
        """Fake launchctl.

        failing lists subcommands that always fail. failing_until maps a
        subcommand to the number of leading attempts that fail, so a later
        retry can be made to succeed.
        """
        seen = {}

        def run(*args):
            self.calls.append(args)
            command = args[1]
            seen[command] = seen.get(command, 0) + 1
            failed = command in failing
            if failing_until and command in failing_until:
                failed = failed or seen[command] <= failing_until[command]
            return mock.Mock(returncode=1 if failed else 0, stdout='', stderr='refused')

        return run

    def subcommands(self):
        return [call[1] for call in self.calls]

    def test_an_unchanged_definition_is_restarted_in_place(self):
        with mock.patch.object(monitorctl, 'run', self.fake_run()):
            ok, detail = monitorctl.load_agent(SERVICE, self.plist, self.previous)
        self.assertTrue(ok)
        self.assertEqual(detail, 'restarted')
        self.assertEqual(self.subcommands(), ['print', 'kickstart'])
        self.assertNotIn('bootout', self.subcommands())

    def test_an_unloaded_agent_is_bootstrapped(self):
        with mock.patch.object(monitorctl, 'run', self.fake_run(failing=('print',))):
            ok, detail = monitorctl.load_agent(SERVICE, self.plist, None)
        self.assertTrue(ok)
        self.assertEqual(detail, 'loaded')
        self.assertEqual(self.subcommands(), ['print', 'bootstrap'])

    def test_a_changed_definition_is_rebuilt(self):
        self.write({'Label': 'local.test', 'ProgramArguments': ['/bin/new']})
        with mock.patch.object(monitorctl, 'run', self.fake_run()):
            ok, detail = monitorctl.load_agent(SERVICE, self.plist, self.previous)
        self.assertTrue(ok)
        self.assertEqual(detail, 'loaded')
        self.assertEqual(self.subcommands(), ['print', 'bootout', 'bootstrap'])

    def test_an_unloaded_agent_with_a_changed_definition_skips_the_teardown(self):
        self.write({'Label': 'local.test', 'ProgramArguments': ['/bin/new']})
        with mock.patch.object(monitorctl, 'run', self.fake_run(failing=('print',))):
            ok, detail = monitorctl.load_agent(SERVICE, self.plist, self.previous)
        self.assertTrue(ok)
        self.assertEqual(detail, 'loaded')
        self.assertEqual(self.subcommands(), ['print', 'bootstrap'])

    def test_a_refused_rebuild_restores_the_previous_definition(self):
        self.write({'Label': 'local.test', 'ProgramArguments': ['/bin/new']})
        with mock.patch.object(monitorctl, 'run', self.fake_run(failing_until={'bootstrap': 5})):
            ok, detail = monitorctl.load_agent(SERVICE, self.plist, self.previous)
        self.assertFalse(ok)
        self.assertIn('previous definition restored', detail)
        self.assertEqual(self.on_disk(), self.previous)
        self.assertEqual(self.subcommands().count('bootstrap'), 6)

    def test_a_refused_rebuild_keeps_the_previous_definition_when_restore_also_fails(self):
        self.write({'Label': 'local.test', 'ProgramArguments': ['/bin/new']})
        with mock.patch.object(monitorctl, 'run', self.fake_run(failing=('bootstrap',))):
            ok, detail = monitorctl.load_agent(SERVICE, self.plist, self.previous)
        self.assertFalse(ok)
        self.assertIn('previous definition kept on disk', detail)
        self.assertEqual(self.on_disk(), self.previous)
        self.assertEqual(self.subcommands().count('bootstrap'), 6)

    def test_a_refused_rebuild_with_nothing_to_restore(self):
        self.write({'Label': 'local.test', 'ProgramArguments': ['/bin/new']})
        with mock.patch.object(monitorctl, 'run', self.fake_run(failing=('print', 'bootstrap'))):
            ok, detail = monitorctl.load_agent(SERVICE, self.plist, None)
        self.assertFalse(ok)
        self.assertEqual(detail, 'refused')
        self.assertEqual(self.subcommands().count('bootstrap'), 5)

    def test_a_refused_kickstart_is_reported(self):
        with mock.patch.object(monitorctl, 'run', self.fake_run(failing=('kickstart',))):
            ok, detail = monitorctl.load_agent(SERVICE, self.plist, self.previous)
        self.assertFalse(ok)
        self.assertEqual(detail, 'refused')


if __name__ == '__main__':
    unittest.main()
