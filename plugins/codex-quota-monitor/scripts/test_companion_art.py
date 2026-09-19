"""Checks on the generated companion artwork module.

The annotations are lazy so this file imports under the Python 3.9 that ships
with the plugin's supported systems.
"""
from __future__ import annotations

import base64
import io
import unittest

from companion_art import (
    COMPANION_ART,
    CUT_EDGE_FILL,
    RUNTIME_HEIGHT,
    SOURCE_FRAMES,
    SOURCE_REPAIRS,
    WEBP_QUALITY,
)

# The repair itself can only be exercised with the build-time stack, and the
# CI runner deliberately has neither numpy nor pillow -- the generated module
# is pure standard library so the overlay never needs them. The behavioural
# check below is skipped there and the declaration check still runs.
try:
    import numpy as np
    from PIL import Image

    import build_companion_art as build
except ImportError:  # pragma: no cover - the path CI takes
    np = None
    Image = None
    build = None

HAVE_BUILD_STACK = build is not None

# The overlay pins a docked companion's right edge to the side wall, so the
# rendered body has to reach that edge. Measured as the rightmost column that
# still carries a solid part of the body, over the image width.
MIN_CUT_EDGE_FILL = 0.97
MIN_RETINA_HEIGHT = 48 * 2 * 3
MIN_WEBP_QUALITY = 90


def reach(alpha, row: int) -> int:
    """Rightmost solidly opaque column of one row, -1 if the row is empty."""
    columns = np.nonzero(alpha[row] > build.REPAIR_PROFILE_THRESHOLD)[0]
    return int(columns.max()) if len(columns) else -1


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

    def test_artwork_has_retina_headroom_and_high_quality_encoding(self):
        """The largest 2x companion stays native on a 3x display."""
        self.assertGreaterEqual(RUNTIME_HEIGHT, MIN_RETINA_HEIGHT)
        self.assertGreaterEqual(WEBP_QUALITY, MIN_WEBP_QUALITY)

    @unittest.skipUnless(HAVE_BUILD_STACK, "needs the build-time pillow stack")
    def test_every_companion_webp_keeps_real_alpha(self):
        """The inlined WebP payloads must retain transparent keyed backdrops."""
        for skin, uri in COMPANION_ART.items():
            with self.subTest(skin=skin):
                payload = base64.b64decode(uri.split(",", 1)[1])
                with Image.open(io.BytesIO(payload)) as decoded:
                    self.assertEqual(decoded.mode, "RGBA", skin)
                    alpha_min, alpha_max = decoded.getchannel("A").getextrema()
                self.assertEqual(alpha_min, 0, skin)
                self.assertEqual(alpha_max, 255, skin)

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

    def test_the_stray_hand_repairs_are_declared(self):
        """Three renders came back from the generator with a second, bare hand.

        The model drew the figure gripping its cut edge twice: once with the
        sleeved arm that reads as theirs, and once as a detached fist with no
        arm attached to it. At the companion's 48px display size that reads as
        a spare hand hovering beside the face, and it was reported as such.
        The build rebuilds those three regions; this checks the record of it
        survived into the bundle, so a redrawn render that quietly drops the
        repair is a reviewable diff instead of a silent regression.
        """
        self.assertEqual(sorted(SOURCE_REPAIRS), ["frost", "mint", "tea"])
        for skin, box in SOURCE_REPAIRS.items():
            with self.subTest(skin=skin):
                x0, y0, x1, y1 = box
                self.assertLess(x0, x1, skin)
                self.assertLess(y0, y1, skin)
                self.assertIn(skin, SOURCE_FRAMES, skin)

    @unittest.skipUnless(HAVE_BUILD_STACK, "needs the build-time numpy/pillow stack")
    def test_the_rebuilt_silhouette_stops_at_the_cut_edge(self):
        """The stray hand is drawn reaching out past the render's cut edge.

        Every one of these renders is cut at a straight vertical edge, which
        is what the overlay pins to the side wall. The stray fist is drawn
        curling around that edge, so it is the one thing in the region that
        sticks out past it. A repaired source therefore has to keep the body
        inside the silhouette measured just outside the repair box, while the
        render as generated bulges well past it -- that bulge is the hand.
        """
        for skin, box in sorted(SOURCE_REPAIRS.items()):
            with self.subTest(skin=skin):
                path = build.resolve_source(skin)
                self.assertIsNotNone(path, f"{skin}: no source render resolves")
                rgb = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32)
                alpha = build.key_alpha(rgb, skin)
                x0, y0, x1, y1 = box
                limit = max(reach(alpha, y0 - 1), reach(alpha, y1 + 1)) + 2
                rows = range(y0, y1 + 1)
                self.assertGreater(
                    max(reach(alpha, y) for y in rows), limit,
                    f"{skin}: nothing reaches past the cut edge to repair",
                )
                repaired = build.prepare_source(rgb, skin)[1]
                self.assertLessEqual(
                    max(reach(repaired, y) for y in rows), limit,
                    f"{skin}: the stray hand still reaches past the cut edge",
                )

    @unittest.skipUnless(HAVE_BUILD_STACK, "needs the build-time numpy/pillow stack")
    def test_the_repair_leaves_the_surviving_hand_alone(self):
        """Each figure grips its cut edge once, and that hand has to survive.

        A repair clears everything right of the cut edge inside its own box, so
        the box has to stop above the hand that stays. When frost's box was
        stretched to cover a smudge below its stray fist it reached into the
        gloved hand under it and sliced 158px off the top -- a silent
        amputation of the very hand the render is meant to keep, which nothing
        else in this file would have noticed.

        The survivor is named outright rather than derived from the box, and
        the sample is taken right of the cut edge, because those are the pixels
        a repair is uniquely able to destroy.
        """
        self.assertEqual(sorted(build.SURVIVING_HANDS), sorted(SOURCE_REPAIRS))
        for skin, hand in sorted(build.SURVIVING_HANDS.items()):
            with self.subTest(skin=skin):
                path = build.resolve_source(skin)
                self.assertIsNotNone(path, f"{skin}: no source render resolves")
                rgb = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32)
                before = build.key_alpha(rgb, skin)
                after = build.prepare_source(rgb, skin)[1]
                x0, y0, x1, y1 = hand

                profile = build.right_profile(before)
                tail = profile[int(before.shape[0] * build.REPAIR_WALL_FROM):]
                tail = tail[tail >= 0]
                wall = int(np.median(tail))
                self.assertGreater(x0, wall, f"{skin}: no hand reaches past the cut edge")

                was = int((before[y0:y1 + 1, x0:x1 + 1] > 0.5).sum())
                now = int((after[y0:y1 + 1, x0:x1 + 1] > 0.5).sum())
                self.assertGreater(was, 1000, f"{skin}: no hand survives below the repair")
                self.assertEqual(was, now, f"{skin}: the repair ate into the surviving hand")

    @unittest.skipUnless(HAVE_BUILD_STACK, "needs the build-time numpy/pillow stack")
    def test_a_repair_box_that_reaches_the_surviving_hand_is_refused(self):
        """The guard, not just the current boxes, is what keeps this fixed.

        The value that broke frost was a box bottom of 828 against a glove at
        y821 -- caught only after the fact. Handing the same overshoot back to
        the builder has to stop the build instead of quietly shipping a
        clipped hand.
        """
        path = build.resolve_source("frost")
        rgb = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32)
        x0, y0, x1, _ = build.REPAIRS["frost"]
        with self.assertRaises(SystemExit) as caught:
            build.repair_region(rgb, "frost", (x0, y0, x1, 828))
        self.assertIn("surviving hand", str(caught.exception))
        # And its real box still builds, so the guard is not simply always on.
        build.repair_region(rgb, "frost", build.REPAIRS["frost"])


if __name__ == "__main__":
    unittest.main()
