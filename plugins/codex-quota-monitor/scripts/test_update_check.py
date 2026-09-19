import unittest
from unittest import mock

import update_check


class VersionParsingTests(unittest.TestCase):
    def test_split_version(self):
        self.assertEqual(update_check.split_version("0.1.0+codex.20260920005609"),
                         ("0.1.0", "codex.20260920005609"))
        self.assertEqual(update_check.split_version("1.2.3"), ("1.2.3", None))
        self.assertEqual(update_check.split_version(None), (None, None))
        self.assertEqual(update_check.split_version(""), (None, None))

    def test_cachebuster_stamp(self):
        self.assertEqual(update_check.cachebuster_stamp("codex.20260920005609"), 20260920005609)
        self.assertIsNone(update_check.cachebuster_stamp("codex.notanumber"))
        self.assertIsNone(update_check.cachebuster_stamp("20260920005609"))
        self.assertIsNone(update_check.cachebuster_stamp(None))

    def test_is_valid_version(self):
        self.assertTrue(update_check.is_valid_version("0.1.0+codex.20260920005609"))
        self.assertTrue(update_check.is_valid_version("1.2.3"))
        self.assertFalse(update_check.is_valid_version("not-a-version"))
        self.assertFalse(update_check.is_valid_version("0.1"))
        self.assertFalse(update_check.is_valid_version("0.1.0+codex.notanumber"))
        self.assertFalse(update_check.is_valid_version(None))
        self.assertFalse(update_check.is_valid_version(""))

    def test_is_newer_by_cachebuster(self):
        # The cachebuster timestamp is authoritative and monotonically increasing.
        self.assertTrue(update_check.is_newer("0.1.0+codex.20260920000000",
                                              "0.1.0+codex.20260920000001"))
        self.assertFalse(update_check.is_newer("0.1.0+codex.20260920000001",
                                               "0.1.0+codex.20260920000000"))
        self.assertFalse(update_check.is_newer("0.1.0+codex.20260920000000",
                                               "0.1.0+codex.20260920000000"))
        self.assertTrue(update_check.is_newer("0.1.0+codex.9", "0.1.0+codex.10"))

    def test_is_newer_falls_back_to_semver(self):
        # Without cachebusters, semver ordering decides.
        self.assertTrue(update_check.is_newer("0.1.0", "0.2.0"))
        self.assertFalse(update_check.is_newer("0.2.0", "0.1.0"))
        self.assertTrue(update_check.is_newer("0.1.9", "0.1.10"))

    def test_is_newer_unparseable_is_not_older(self):
        # A side that cannot be parsed is never treated as "older".
        self.assertFalse(update_check.is_newer(None, "0.2.0"))
        self.assertFalse(update_check.is_newer("0.1.0", None))


class CheckTests(unittest.TestCase):
    def _stamp(self, plugin="0.1.0", cachebuster="codex.20260920005609"):
        return {"pluginVersion": plugin, "cachebuster": cachebuster,
                "runtimeVersion": 24, "installedAt": 1.0}

    def test_update_available_when_remote_is_newer(self):
        local = self._stamp()
        remote = "0.2.0+codex.20260921000000"
        with mock.patch.object(update_check, "read_local_version",
                               return_value=(local["pluginVersion"], local["cachebuster"])), \
             mock.patch.object(update_check, "fetch_remote_version", return_value=remote):
            result = update_check.check_for_update()
        self.assertEqual(result["status"], "update_available")
        self.assertEqual(result["latestSemver"], "0.2.0")

    def test_up_to_date_when_remote_matches(self):
        local = self._stamp()
        remote = "0.1.0+codex.20260920005609"
        with mock.patch.object(update_check, "read_local_version",
                               return_value=(local["pluginVersion"], local["cachebuster"])), \
             mock.patch.object(update_check, "fetch_remote_version", return_value=remote):
            result = update_check.check_for_update()
        self.assertEqual(result["status"], "up_to_date")

    def test_unavailable_when_network_fails(self):
        with mock.patch.object(update_check, "read_local_version", return_value=("0.1.0", "codex.1")), \
             mock.patch.object(update_check, "fetch_remote_version", side_effect=OSError("offline")):
            result = update_check.check_for_update()
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["latestSemver"])

    def test_unavailable_when_remote_is_malformed(self):
        for remote in (None, "", "not-a-version"):
            with mock.patch.object(update_check, "read_local_version", return_value=("0.1.0", "codex.1")), \
                 mock.patch.object(update_check, "fetch_remote_version", return_value=remote):
                result = update_check.check_for_update()
            self.assertEqual(result["status"], "unavailable", remote)

    def test_unavailable_without_an_installed_version(self):
        with mock.patch.object(update_check, "read_local_version", return_value=(None, None)), \
             mock.patch.object(update_check, "fetch_remote_version",
                               return_value="0.1.0+codex.20260920005609"):
            result = update_check.check_for_update()
        self.assertEqual(result["status"], "unavailable")


class UpdateCheckerTests(unittest.TestCase):
    def test_snapshot_checks_in_the_background_and_throttles(self):
        checker = update_check.UpdateChecker()
        value = {"status": "up_to_date"}
        with mock.patch.object(update_check, "check_for_update", return_value=value) as check, \
             mock.patch.object(update_check.threading, "Thread") as thread:
            self.assertEqual(checker.snapshot(), {"status": "checking"})
            thread.return_value.start.assert_called_once_with()
            checker._refresh()
            self.assertEqual(checker.snapshot(), value)
            self.assertEqual(thread.call_count, 1)
        check.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
