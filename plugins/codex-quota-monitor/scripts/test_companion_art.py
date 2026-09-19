import base64
import unittest

from companion_art import COMPANION_ART, RUNTIME_HEIGHT, SOURCE_FRAMES


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


if __name__ == "__main__":
    unittest.main()
