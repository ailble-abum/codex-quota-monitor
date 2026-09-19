"""Checks for the deterministic companion-expression sprite bundle."""

from __future__ import annotations

import base64
import io
import unittest

from companion_expressions import (
    COMPANION_EXPRESSIONS,
    EXPRESSION_ORDER,
    RUNTIME_HEIGHT,
)

try:
    from PIL import Image
except ImportError:  # pragma: no cover - CI without the build-time stack
    Image = None

try:
    import numpy
except ImportError:  # pragma: no cover - optional build-time dependency
    numpy = None

HAVE_IMAGE_STACK = Image is not None


def webp_size(data: bytes) -> tuple[int, int] | None:
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    chunk = data[12:16]
    if chunk == b"VP8X":
        return int.from_bytes(data[24:27], "little") + 1, int.from_bytes(data[27:30], "little") + 1
    if chunk == b"VP8 ":
        return int.from_bytes(data[26:28], "little") & 0x3FFF, int.from_bytes(data[28:30], "little") & 0x3FFF
    return None


class CompanionExpressionTests(unittest.TestCase):
    def test_all_skins_export_six_distinct_expressions(self):
        self.assertEqual(sorted(COMPANION_EXPRESSIONS), ["candy", "cat", "corgi", "frost", "mint", "tea"])
        for skin, frames in COMPANION_EXPRESSIONS.items():
            self.assertEqual(tuple(frames), EXPRESSION_ORDER, skin)
            self.assertEqual(len(set(frames.values())), 6, skin)
        self.assertEqual(EXPRESSION_ORDER, ("idle", "happy", "concerned", "notice", "waiting", "pet"))

    def test_every_expression_is_a_canvas_sized_webp(self):
        for skin, frames in COMPANION_EXPRESSIONS.items():
            for name, uri in frames.items():
                with self.subTest(skin=skin, expression=name):
                    self.assertTrue(uri.startswith("data:image/webp;base64,"))
                    payload = base64.b64decode(uri.split(",", 1)[1])
                    self.assertGreater(len(payload), 2048)
                    size = webp_size(payload)
                    self.assertEqual(size[1], RUNTIME_HEIGHT)
                    self.assertEqual(size, webp_size(base64.b64decode(frames["idle"].split(",", 1)[1])))
                    self.assertGreaterEqual(size[0], 96)
                    self.assertLessEqual(size[0], 384)

    @unittest.skipUnless(HAVE_IMAGE_STACK, "needs the build-time pillow stack")
    def test_every_expression_keeps_alpha_and_reaches_the_right_edge(self):
        for skin, frames in COMPANION_EXPRESSIONS.items():
            for name, uri in frames.items():
                with self.subTest(skin=skin, expression=name):
                    payload = base64.b64decode(uri.split(",", 1)[1])
                    with Image.open(io.BytesIO(payload)) as decoded:
                        self.assertEqual(decoded.mode, "RGBA")
                        alpha = decoded.getchannel("A")
                        alpha_min, alpha_max = alpha.getextrema()
                        self.assertEqual(alpha_min, 0)
                        self.assertGreater(alpha_max, 128)
                        # Hair/fingertip contours can touch the wall in only a few
                        # pixels; require a visible edge, not the cat-specific
                        # minimum length of a straight body cut.
                        visible = alpha.point(lambda value: 255 if value >= 32 else 0)
                        self.assertEqual(visible.getbbox()[2], decoded.width)

    @unittest.skipUnless(HAVE_IMAGE_STACK and numpy is not None, "needs the build-time pillow/numpy stack")
    def test_builder_rejects_opaque_and_empty_source_sheets(self):
        from build_companion_expressions import source_cells
        for rgba in [(10, 20, 30, 255), (0, 0, 0, 0)]:
            with self.subTest(rgba=rgba), self.assertRaises(SystemExit):
                source_cells(Image.new("RGBA", (1536, 1024), rgba))


if __name__ == "__main__":
    unittest.main()
