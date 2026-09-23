import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import windows_monitor as monitor


class WindowsPlanTests(unittest.TestCase):
    def test_worker_owns_tray_lifecycle(self):
        class Mutex:
            def __init__(self):
                self.released = False

            def acquire(self):
                return True

            def release(self):
                self.released = True

        class Process:
            def __init__(self):
                self.terminated = False

            def poll(self):
                return None

            def terminate(self):
                self.terminated = True

            def wait(self, timeout=None):
                return 0

        calls = []
        process = Process()

        def fake_popen(command, **kwargs):
            calls.append((command, kwargs))
            return process

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "runtime"
            mutex = Mutex()
            result = monitor.run_worker(
                root=root,
                environ={"LOCALAPPDATA": folder},
                port_finder=lambda: None,
                popen_factory=fake_popen,
                sleep_fn=lambda _seconds: None,
                mutex=mutex,
                max_cycles=0,
            )

        self.assertEqual(result, 0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0][0], "powershell.exe")
        self.assertIn("windows_tray.ps1", calls[0][0][-1])
        self.assertEqual(calls[0][1]["env"]["CODEX_MONITOR_PYTHON"], monitor.current_python())
        self.assertTrue(process.terminated)
        self.assertTrue(mutex.released)

    def test_runtime_root_uses_local_app_data(self):
        root = monitor.runtime_root({"LOCALAPPDATA": r"C:\Users\Ada\AppData\Local"})
        self.assertEqual(root, Path(r"C:\Users\Ada\AppData\Local") / "CodexQuotaMonitor")

    def test_install_plan_is_non_admin_and_persistent(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source"
            source.mkdir()
            (source / "windows_monitor.py").write_text("# worker", encoding="utf-8")
            plan = monitor.build_management_plan(
                "install",
                source_dir=source,
                root=Path(folder) / "runtime",
                python_executable=r"C:\Python\python.exe",
            )
        command = plan["commands"][0]
        self.assertEqual(command[0], "schtasks.exe")
        self.assertIn("/Create", command)
        self.assertIn("ONLOGON", command)
        self.assertIn("LIMITED", command)
        self.assertNotIn("/RU", command)
        self.assertIn("windows_monitor.py", command[command.index("/TR") + 1])
        self.assertEqual(plan["copy_files"], ["windows_monitor.py"])

    def test_stop_plan_is_cooperative_and_has_no_task_end(self):
        plan = monitor.build_management_plan("stop", root=Path("C:/runtime"))
        self.assertTrue(plan["cooperative_stop"])
        self.assertEqual(plan["commands"][0][-1], "/DISABLE")
        self.assertNotIn("/End", str(plan))

    def test_start_reenables_only_the_owned_task_before_running(self):
        plan = monitor.build_management_plan("start", root=Path("C:/runtime"))
        self.assertEqual(plan["commands"][0][-1], "/ENABLE")
        self.assertEqual(plan["commands"][1], ["schtasks.exe", "/Run", "/TN", monitor.TASK_NAME])

    def test_worker_command_uses_current_interpreter_and_run(self):
        command = monitor.build_worker_command(
            r"C:\Python\python.exe",
            r"C:\Users\Ada\CodexQuotaMonitor\scripts\windows_monitor.py",
        )
        self.assertEqual(
            command,
            [
                r"C:\Python\python.exe",
                r"C:\Users\Ada\CodexQuotaMonitor\scripts\windows_monitor.py",
                "run",
            ],
        )

    def test_injector_command_has_port(self):
        command = monitor.build_injector_command(
            9333,
            r"C:\Python\python.exe",
            r"C:\runtime\context_token_injector.py",
        )
        self.assertEqual(command[-2:], ["--port", "9333"])

    def test_configured_port_and_cdp_probe_are_cross_platform(self):
        self.assertEqual(monitor.configured_port(environ={}), 9222)
        self.assertEqual(monitor.configured_port(environ={"CODEX_MONITOR_PORT": "9333"}), 9333)

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return b"[]"

        self.assertEqual(monitor.find_cdp_port(environ={"CODEX_MONITOR_PORT": "9333"}, opener=lambda *a, **k: Response()), 9333)

    def test_copy_plugin_scripts_skips_non_scripts(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source"
            destination = Path(folder) / "destination"
            source.mkdir()
            (source / "context_token_injector.py").write_text("# injector", encoding="utf-8")
            (source / "windows_tray.ps1").write_text("# tray", encoding="utf-8")
            (source / "notes.txt").write_text("not installed", encoding="utf-8")
            copied = monitor.copy_plugin_scripts(destination, source)
            self.assertEqual(
                {path.name for path in copied},
                {"context_token_injector.py", "windows_tray.ps1"},
            )
            self.assertFalse((destination / "notes.txt").exists())

    def test_non_windows_manage_only_returns_plan(self):
        calls = []

        def should_not_run(_args):
            calls.append(True)
            raise AssertionError("Windows command executed during a non-Windows test")

        result = monitor.manage(
            "start",
            root=Path(tempfile.gettempdir()) / "codex-quota-monitor-test",
            platform_name=os.name,
            command_runner=should_not_run,
            emit=False,
        )
        self.assertFalse(result["executed"])
        self.assertFalse(result["supported"])
        self.assertEqual(calls, [])

    def test_launch_instructions_are_manual_and_loopback_only(self):
        instructions = monitor.codex_launch_instructions(
            9333,
            r"C:\Tools\Codex\Codex.exe",
        )
        self.assertIn("CODEX_MONITOR_APP_PATH", instructions)
        self.assertIn("--remote-debugging-port", instructions)
        self.assertIn("127.0.0.1", instructions)
        self.assertIn("does not reopen Codex", instructions)

    def test_tray_command_exports_its_python_helper_environment(self):
        command = monitor.build_tray_command(
            r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            r"C:\runtime\windows_tray.ps1",
        )
        self.assertEqual(command[-2:], ["-File", r"C:\runtime\windows_tray.ps1"])
        environment = monitor.tray_environment(r"C:\Python\python.exe", {"CODEX_MONITOR_PORT": "9333"})
        self.assertEqual(environment["CODEX_MONITOR_PYTHON"], r"C:\Python\python.exe")
        self.assertEqual(environment["CODEX_MONITOR_PORT"], "9333")

    def test_pid_probe_does_not_use_signal_probe(self):
        self.assertFalse(monitor._pid_alive(1))
        self.assertNotIn("os.kill", monitor._pid_alive.__doc__ or "")

    def test_layout_reset_expression_clears_both_storage_versions(self):
        source = Path(__file__).with_name("windows_monitor.py").read_text(encoding="utf-8")
        self.assertIn("codex-context-token-inspector-position", source)
        self.assertIn("cti-layout-v2", source)
        self.assertIn("root.__ctiLayout={}", source)

    def test_stop_expression_clears_the_page_bridge(self):
        self.assertIn("window.__codexContextTokenInspectorHideSidebarTooltip?.();", monitor.STOP_OVERLAY_EXPRESSION)
        self.assertIn("window.__codexContextTokenInspectorPageRefresh?.dispose?.();", monitor.STOP_OVERLAY_EXPRESSION)
        self.assertIn("window.__codexContextTokenInspectorPageBridge?.clearSidebar?.();", monitor.STOP_OVERLAY_EXPRESSION)

    def test_display_action_uses_the_transport_without_importing_the_injector(self):
        target = {"webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/codex"}
        client = mock.Mock()
        client.evaluate.return_value = True
        with mock.patch.object(monitor, "devtools_targets", return_value=[target]) as targets, \
                mock.patch.object(monitor, "select_target", return_value=target) as select, \
                mock.patch.object(monitor, "CDPClient", return_value=client) as connect:
            self.assertEqual(monitor.display_action("show"), {"available": True, "value": True})
        targets.assert_called_once_with(9222)
        select.assert_called_once_with([target])
        connect.assert_called_once_with(target["webSocketDebuggerUrl"])
        client.close.assert_called_once_with()
        self.assertNotIn("import context_token_injector", Path(monitor.__file__).read_text(encoding="utf-8"))

    def test_notification_is_once_per_fresh_timestamp(self):
        self.assertTrue(monitor.notification_is_fresh({"message": "low", "at": 1000}, now=1120))
        self.assertFalse(monitor.notification_is_fresh({"message": "low", "at": 1000}, now=1120.1))
        self.assertFalse(monitor.notification_is_fresh({"message": "low", "at": "bad"}, now=1000))
        self.assertEqual(monitor.notification_text({"message": "  low  "}), "  low  ")

    def test_tray_consumes_runtime_notification_file(self):
        tray = Path(__file__).with_name("windows_tray.ps1").read_text(encoding="utf-8")
        self.assertIn("notification.json", tray)
        self.assertIn("LastNotificationTimestamp", tray)
        self.assertIn("StaleAfterSeconds", tray)
        self.assertIn("ShowBalloonTip", tray)
        self.assertIn("Get-QuotaTimestamp", tray)
        self.assertIn("Get-SnapshotTimestamp", tray)
        self.assertIn("windowStatus -eq 'not_reported'", tray)
        self.assertIn("$script:HistoryPath", tray)
        self.assertNotIn("Open-OwnedFile -Path $historyTarget", tray)


if __name__ == "__main__":
    unittest.main()
