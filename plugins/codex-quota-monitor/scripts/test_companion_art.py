"""Checks on the generated companion artwork module.

The annotations are lazy so this file imports under the Python 3.9 that ships
with the plugin's supported systems.
"""
from __future__ import annotations

import base64
import unittest

from companion_art import COMPANION_ART, CUT_EDGE_FILL, RUNTIME_HEIGHT, SOURCE_FRAMES

# The overlay pins a docked companion's right edge to the side wall, so the
# rendered body has to reach that edge. Measured as the rightmost column that
# still carries a solid part of the body, over the image width.
MIN_CUT_EDGE_FILL = 0.97


def webp_size(data: bytes) -> tuple[int, int] | None:
    """Canvas size of a WebP container, without pulling in an image library."""
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    chunk = data[12:16]
    if chunk == b"VP8X":
        width = int.from_bytes(data[24:27], "little") + 1
        height = int.from_bytes(data[27:30], "little") + 1
        return width, height
    if chunk == b"VP8 ":
        return (
            int.from_bytes(data[26:28], "little") & 0x3FFF,
            int.from_bytes(data[28:30], "little") & 0x3FFF,
        )
    return None


class CompanionArtTests(unittest.TestCase):
    def test_every_entry_is_an_inlined_webp(self):
        self.assertTrue(COMPANION_ART, "the generated artwork module is empty")
        for skin, uri in COMPANION_ART.items():
            with self.subTest(skin=skin):
                self.assertTrue(uri.startswith("data:image/webp;base64,"), skin)
                payload = base64.b64decode(uri.split(",", 1)[1])
                self.assertEqual(payload[:4], b"RIFF", skin)
                self.assertEqual(payload[8:12], b"WEBP", skin)
                # A placeholder or a one-pixel stub would defeat the point.
                self.assertGreater(len(payload), 2048, skin)

    def test_artwork_shares_one_vertical_scale(self):
        for skin, uri in COMPANION_ART.items():
            with self.subTest(skin=skin):
                payload = base64.b64decode(uri.split(",", 1)[1])
                size = webp_size(payload)
                self.assertIsNotNone(size, f"{skin}: unreadable WebP header")
                width, height = size
                self.assertEqual(height, RUNTIME_HEIGHT, skin)
                # Cropped flush against a vertical cut edge, so never square-wide.
                self.assertLess(width, height, skin)

    def test_frames_cover_exactly_the_bundled_skins(self):
        self.assertEqual(sorted(SOURCE_FRAMES), sorted(COMPANION_ART))

    def test_the_whole_roster_is_bundled(self):
        """All six companions ship artwork, none of them a vector fallback.

        The overlay still falls back to its inline vector when an entry is
        missing, so a render that stopped resolving would not fail anything
        else -- the picker would just quietly show the drawn mascot for that
        skin. The mint cat was the last one waiting on art.
        """
        self.assertEqual(sorted(COMPANION_ART), ["candy", "cat", "corgi", "frost", "mint", "tea"])

    def test_every_companion_reaches_its_cut_edge(self):
        """A gutter between the body and its cut edge floats the mascot.

        The key can leave isolated specks far from the character. When those
        decided the frame, the corgi shipped ~90px of empty frame to the
        right of its body and the docked companion sat visibly off the screen
        edge. The build now fails below MIN_CUT_EDGE_FILL; this checks what
        actually got bundled.
        """
        self.assertEqual(sorted(CUT_EDGE_FILL), sorted(COMPANION_ART))
        for skin, fill in CUT_EDGE_FILL.items():
            with self.subTest(skin=skin):
                self.assertGreaterEqual(
                    fill, MIN_CUT_EDGE_FILL, f"{skin} does not reach its cut edge"
                )


if __name__ == "__main__":
    unittest.main()
