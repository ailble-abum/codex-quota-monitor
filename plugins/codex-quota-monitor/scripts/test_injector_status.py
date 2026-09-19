import tempfile
import unittest
from pathlib import Path
from unittest import mock

import injector_status


class InjectorStatusTests(unittest.TestCase):
    def test_status_is_owner_only_and_carries_only_safe_diagnostics(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(injector_status.time, 'time', return_value=12.5):
            injector_status.write_status('error','CDPError',folder)
            value=injector_status.read_status(folder)
            self.assertEqual(value,{'status':'error','errorCode':'CDPError','updatedAt':12.5})
            self.assertEqual(Path(folder,'injector_status.json').stat().st_mode & 0o777,0o600)

    def test_missing_status_is_unknown(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(injector_status.read_status(folder),{'status':'unknown'})


if __name__ == '__main__':
    unittest.main()
