"""Tests for the LaunchAgent lifecycle helper in monitorctl.

These cover the decision that stranded the menu bar agent: rebuilding a healthy
loaded agent with bootout+bootstrap, and losing it when the bootstrap is
refused. launchctl itself is faked so the tests run anywhere.
"""
import json
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


class BuildRecordTest(unittest.TestCase):
    """The stamp that makes "I installed it and nothing changed" answerable.

    The declared version, the cachebuster Codex keys its cache directory on,
    and the injected runtime version move independently, and a plugin cache
    does not refresh on its own, so all three have to be recorded together.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        plugin = root / 'plugin'
        (plugin / '.codex-plugin').mkdir(parents=True)
        (plugin / 'scripts').mkdir()
        self.write_manifest('0.1.0+codex.20260920002813', plugin)
        self.write_runtime(20, plugin)
        self.root = root / 'CodexQuotaMonitor'
        for name, value in (('PLUGIN', plugin), ('SCRIPTS', plugin / 'scripts'), ('RUNTIME_ROOT', self.root)):
            patched = mock.patch.object(monitorctl, name, value)
            patched.start()
            self.addCleanup(patched.stop)

    def write_manifest(self, version, plugin=None):
        plugin = plugin or monitorctl.PLUGIN
        (plugin / '.codex-plugin/plugin.json').write_text(json.dumps({'version': version}), encoding='utf-8')

    def write_runtime(self, version, plugin=None):
        plugin = plugin or monitorctl.PLUGIN
        (plugin / 'scripts/context_token_injector.py').write_text(
            f'INJECTION_SCRIPT = """\n  const RUNTIME_VERSION = {version};\n"""\n', encoding='utf-8')

    def test_the_record_splits_the_cachebuster_from_the_declared_version(self):
        info = monitorctl.record_build(self.root)
        self.assertEqual(info['pluginVersion'], '0.1.0')
        self.assertEqual(info['cachebuster'], 'codex.20260920002813')
        self.assertEqual(info['runtimeVersion'], 20)
        self.assertIsInstance(info['installedAt'], float)

    def test_the_record_is_read_back_from_disk(self):
        monitorctl.record_build(self.root)
        summary = monitorctl.describe_build()
        self.assertIn('plugin 0.1.0', summary)
        self.assertIn('build codex.20260920002813', summary)
        self.assertIn('runtime 20', summary)

    def test_a_version_without_build_metadata_still_records(self):
        # The cachebuster is build metadata, not a required field: a plain
        # version must not be dropped or split into a stray empty part.
        self.write_manifest('1.2.3')
        info = monitorctl.record_build(self.root)
        self.assertEqual(info['pluginVersion'], '1.2.3')
        self.assertIsNone(info['cachebuster'])

    def test_a_missing_manifest_or_runtime_line_records_nothing_invented(self):
        (monitorctl.PLUGIN / '.codex-plugin/plugin.json').write_text('{', encoding='utf-8')
        (monitorctl.SCRIPTS / 'context_token_injector.py').write_text('RUNTIME_VERSION = 4\n', encoding='utf-8')
        info = monitorctl.record_build(self.root)
        self.assertIsNone(info['pluginVersion'])
        self.assertIsNone(info['runtimeVersion'])
        self.assertTrue(monitorctl.describe_build().startswith('installed '))

    def test_an_absent_record_is_named_rather_than_guessed(self):
        self.assertEqual(monitorctl.describe_build(), 'not recorded')

    def test_a_corrupt_record_is_named_rather_than_guessed(self):
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / monitorctl.BUILD_INFO).write_text('{ not json', encoding='utf-8')
        self.assertEqual(monitorctl.describe_build(), 'not recorded')

    def test_the_stamp_never_carries_a_credential(self):
        # The record is written into the runtime directory, so it has to stay a
        # description of the build and nothing else.
        info = monitorctl.record_build(self.root)
        self.assertEqual(sorted(info), ['cachebuster', 'installedAt', 'pluginVersion', 'runtimeVersion'])


class RendererClientTest(unittest.TestCase):
    def test_renderer_client_uses_the_transport_without_loading_the_injector(self):
        target = {'webSocketDebuggerUrl': 'ws://127.0.0.1:9222/devtools/page/codex'}
        client = mock.sentinel.client
        with mock.patch.object(monitorctl, 'devtools_targets', return_value=[target]) as targets, \
                mock.patch.object(monitorctl, 'select_target', return_value=target) as select, \
                mock.patch.object(monitorctl, 'CDPClient', return_value=client) as connect:
            self.assertIs(monitorctl.renderer_client(9222), client)
        targets.assert_called_once_with(9222)
        select.assert_called_once_with([target])
        connect.assert_called_once_with(target['webSocketDebuggerUrl'])
        self.assertNotIn('import context_token_injector', Path(monitorctl.__file__).read_text(encoding='utf-8'))


class OverlayCleanupTest(unittest.TestCase):
    def test_stop_clears_the_page_bridge_before_removing_the_overlay(self):
        source = Path(monitorctl.__file__).read_text(encoding='utf-8')
        self.assertIn('window.__codexContextTokenInspectorHideSidebarTooltip?.();', source)
        self.assertIn('window.__codexContextTokenInspectorPageRefresh?.dispose?.();', source)
        self.assertIn('window.__codexContextTokenInspectorPageBridge?.clearSidebar?.();', source)


if __name__ == '__main__':
    unittest.main()
