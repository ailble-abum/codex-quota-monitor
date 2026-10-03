import asyncio
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from quota_monitor.host_restart import HostRestarter, HostRestartSource, host_app
from quota_monitor.cdp import CDPError


class RestartTests(unittest.TestCase):
    def service(self, states=None):
        service = Mock()
        service._owned.return_value = True
        service._menu_owned.return_value = True
        service.status.return_value = 'running'
        service.menu_status.return_value = 'running'
        service.domain = 'gui/123'
        service.path = '/synthetic/collector.plist'
        service.menu_path = '/synthetic/menu.plist'
        service._launchctl.return_value = SimpleNamespace(returncode=0)
        return service

    def follower(self):
        follower = Mock()
        follower.bundle = 'com.example.codex'
        follower.ensure.return_value = 'launch_requested'
        follower.launch.return_value = 'launch_requested'
        return follower

    def test_cli_host_mapping_accepts_only_known_app_bundle_layouts(self):
        for layout in ('codex', 'codex-cli/bin/codex', 'codex-cli/CodexCLI.app/Contents/MacOS/codex'):
            self.assertEqual(host_app('/synthetic/Codex.app/Contents/Resources/' + layout), '/synthetic/Codex.app')
        for path in ('/synthetic/codex', '/synthetic/Codex.app/Contents/Resources/other/codex'):
            with self.assertRaises(ValueError): host_app(path)

    def test_restart_waits_for_exact_page_and_preserves_owned_collectors(self):
        service, follower = self.service(), self.follower()
        time = [0]
        def sleep(duration): time[0] += duration
        probe = Mock(side_effect=[CDPError('discovery_unavailable'), False, True])
        restarter = HostRestarter('/synthetic/cli', 'http://127.0.0.1:19222', 'app://-/index.html',
            service, follower=follower, probe=probe, clock=lambda:time[0], sleeper=sleep)
        self.assertEqual(restarter.restart(), 'reopened')
        follower.ensure.assert_called_once()
        service._launchctl.assert_not_called()
        self.assertEqual(probe.call_count,3)

    def test_existing_loaded_or_unloaded_monitor_is_started_before_host(self):
        service, follower = self.service(), self.follower()
        service.status.side_effect = ['not_loaded', 'running', 'running']
        service.menu_status.side_effect = ['loaded', 'running', 'running']
        restarter = HostRestarter('/synthetic/cli','http://127.0.0.1:19222','app://-/index.html',service,
            follower=follower,probe=lambda:True)
        self.assertEqual(restarter.restart(),'reopened')
        self.assertEqual(service._launchctl.call_args_list[0].args,('bootstrap','gui/123','/synthetic/collector.plist'))
        self.assertEqual(service._launchctl.call_args_list[1].args,('kickstart','gui/123/local.codex-quota-monitor-v2-menu'))

    def test_foreign_monitor_quit_failure_and_page_timeout_do_not_claim_success(self):
        service, follower = self.service(), self.follower()
        service._owned.return_value = False
        with self.assertRaises(ValueError):
            HostRestarter('/synthetic/cli','http://127.0.0.1:19222','app://-/index.html',service,follower=follower)
        follower.ensure.assert_not_called()
        service._owned.return_value = True
        time = [0]
        restarter = HostRestarter('/synthetic/cli','http://127.0.0.1:19222','app://-/index.html',service,
            follower=follower,probe=lambda:False,clock=lambda:time[0],sleeper=lambda duration:time.__setitem__(0,time[0]+duration))
        follower.ensure.return_value = 'quit_failed'
        self.assertEqual(restarter.restart(),'quit_failed')
        follower.launch.assert_not_called()
        follower.ensure.return_value = 'launch_requested'
        self.assertEqual(restarter.restart(),'connection_timeout')


class RestartSourceTests(unittest.IsolatedAsyncioTestCase):
    async def test_restart_is_explicit_single_flight_and_new_revision_can_restart_again(self):
        restarter = Mock()
        source = HostRestartSource(restarter)
        restarter.restart.assert_not_called()
        restarter.restart.return_value = 'reopened'
        self.assertTrue(source.request('one'))
        self.assertFalse(source.request('one'))
        await source.task
        self.assertEqual(source.snapshot('one'),{'status':'reopened','revision':'one','attempt':1})
        self.assertEqual(source.snapshot('two'),{'status':'available','attempt':1})
        await source.close()

    async def test_exception_is_contained_without_private_error_text(self):
        restarter = Mock()
        restarter.restart.side_effect = OSError('private path')
        source = HostRestartSource(restarter)
        source.request('one')
        await source.task
        self.assertEqual(source.value,{'status':'failed','revision':'one','attempt':1})
