"""Checks for the plugin artwork exposed in Codex surfaces."""

import json
import struct
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PLUGIN_DIR / ".codex-plugin" / "plugin.json"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class PluginBrandingTests(unittest.TestCase):
    def test_plugin_uses_a_square_png_for_both_logo_surfaces(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        interface = manifest["interface"]

        for field in ("composerIcon", "logo"):
            relative_path = interface[field]
            self.assertTrue(relative_path.startswith("./assets/"))

            asset = PLUGIN_DIR / relative_path.removeprefix("./")
            data = asset.read_bytes()
            self.assertEqual(PNG_SIGNATURE, data[:8])

            width, height = struct.unpack(">II", data[16:24])
            self.assertEqual(width, height)
            self.assertGreaterEqual(width, 512)


if __name__ == "__main__":
    unittest.main()
