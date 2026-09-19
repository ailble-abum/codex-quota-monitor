"""Checks for the deterministic cat-expression sprite bundle."""

from __future__ import annotations

import base64
import io
import unittest

from companion_expressions import (
    CANVAS_WIDTH,
    COMPANION_EXPRESSIONS,
    EXPRESSION_ORDER,
    RUNTIME_HEIGHT,
)

try:
    from PIL import Image
except ImportError:  # pragma: no cover - CI without the build-time stack
    Image = None

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
    def test_cat_exports_all_six_expressions(self):
        self.assertEqual(sorted(COMPANION_EXPRESSIONS), ["cat"])
        self.assertEqual(tuple(COMPANION_EXPRESSIONS["cat"]), EXPRESSION_ORDER)
        self.assertEqual(EXPRESSION_ORDER, ("idle", "happy", "concerned", "notice", "waiting", "pet"))

    def test_every_expression_is_a_canvas_sized_webp(self):
        for name, uri in COMPANION_EXPRESSIONS["cat"].items():
            with self.subTest(expression=name):
                self.assertTrue(uri.startswith("data:image/webp;base64,"))
                payload = base64.b64decode(uri.split(",", 1)[1])
                self.assertGreater(len(payload), 2048)
                self.assertEqual(webp_size(payload), (CANVAS_WIDTH, RUNTIME_HEIGHT))

    @unittest.skipUnless(HAVE_IMAGE_STACK, "needs the build-time pillow stack")
    def test_every_expression_keeps_alpha_and_reaches_the_right_edge(self):
        for name, uri in COMPANION_EXPRESSIONS["cat"].items():
            with self.subTest(expression=name):
                payload = base64.b64decode(uri.split(",", 1)[1])
                with Image.open(io.BytesIO(payload)) as decoded:
                    self.assertEqual(decoded.mode, "RGBA")
                    alpha = decoded.getchannel("A")
                    alpha_min, alpha_max = alpha.getextrema()
                    self.assertEqual(alpha_min, 0)
                    self.assertGreater(alpha_max, 128)
                    edge = alpha.crop((CANVAS_WIDTH - 1, 0, CANVAS_WIDTH, RUNTIME_HEIGHT))
                    edge_values = edge.tobytes()
                    self.assertGreaterEqual(sum(value >= 32 for value in edge_values), RUNTIME_HEIGHT // 20)


if __name__ == "__main__":
    unittest.main()
