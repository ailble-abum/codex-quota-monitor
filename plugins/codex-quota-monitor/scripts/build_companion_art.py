#!/usr/bin/env python3
"""Build the runtime companion artwork used by the injected overlay.

The source renders in ``assets/companions`` are images whose "transparency"
was baked in rather than carried as a real alpha channel, in one of two
styles:

* checkerboard -- the square full-figure renders, where the backdrop is
  neutral grey squares painted in behind the character, and
* studio -- the mint cat, shot on a flat near-black backdrop with a lit wall
  rim down the right edge, which is the edge the cat hides behind.

This script

1. keys one of those backdrops out into a real alpha channel,
2. crops to a shared content frame so every companion keeps the same
   relative scale,
3. resizes with premultiplied alpha (avoids light fringes), and
4. writes ``assets/companions/web/<skin>.webp`` plus the generated module
   ``scripts/companion_art.py`` that inlines the same bytes as data URIs.

The overlay falls back to its bundled vector mascot whenever an entry is
missing, so a companion can be added later without breaking the build.

Build-time dependencies (not needed at runtime, the generated module is
pure standard library):

    pip install pillow numpy

Run from anywhere:

    python3 scripts/build_companion_art.py          # rebuild everything
    python3 scripts/build_companion_art.py --list   # report sources only
"""

from __future__ import annotations

import argparse
import base64
import io
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_DIR = SCRIPT_DIR.parent
SOURCE_DIR = PLUGIN_DIR / "assets" / "companions"
WEB_DIR = SOURCE_DIR / "web"
GENERATED_MODULE = "companion_art.py"

# Skin id -> candidate source file names, in priority order. Ids must match
# MASCOT_SKINS in context_token_injector.py.
SOURCES = {
    "cat": ["cat.png", "mint-cat.png"],
    "candy": ["candy-girl.png", "candy.png"],
    "corgi": ["corgi-helper.png", "corgi.png"],
    "mint": ["mint-boy.png", "mint.png"],
    "frost": ["mr-frost.png", "frost.png"],
    "tea": ["tea-lady.png", "tea.png"],
}

RUNTIME_HEIGHT = 256
WEBP_QUALITY = 82
SPECKLE_ALPHA_LIMIT = 40
SPECKLE_NEIGHBOUR_LIMIT = 24

# Breathing room kept around the keyed character, in source pixels.
SOURCE_MARGIN = 6

# The checkerboard is perfectly neutral grey/white, while the renders keep a
# slight colour cast even in their brightest areas. Colour spread therefore
# separates the two far more reliably than an exact shade match.
NEUTRAL_SPREAD = 5
NEUTRAL_LUM_MIN = 175
KEY_BLUR = 0.8
SPECKLE_BLUR = 1.2

# A row or column only counts towards the content frame once this share of
# it is foreground, which keeps border speckles from inflating the frame.
#
# The threshold has to be high enough that isolated keying artefacts lose to
# the character. The corgi render carries a few specks out around x=1190 of
# its 1254px frame, ten rows tall at most, while the body's own columns are
# covered tens of percent deep. At the original 0.5% those specks decided
# where the cut edge was, so the frame kept ~90px of empty space beyond the
# body and the docked companion visibly floated off the screen edge it is
# supposed to peek in from. At 2% the specks fall below the line and every
# companion's cut edge lands within a couple of pixels of its body.
FRAME_COVERAGE = 0.02

# The rendered companion has to reach its own right edge -- that edge is the
# cut edge the overlay pins to the side wall, so a transparent gutter there
# shows up as the mascot hovering away from the window border.
CUT_EDGE_FILL_MIN = 0.97

# --- studio renders, keyed on a flat dark backdrop ------------------------
#
# The mint cat did not arrive on a checkerboard. It is a small studio render:
# a near-black backdrop with the character only a few levels above it, and a
# lit wall rim running the full frame height down its right edge, which the
# cat's right ear and paw are cropped by.
#
# The rim's glow dies out by x=239 (rows above and below the cat read a flat
# 19-20 there), so the frame is clipped just to its left and the cat is cut
# exactly where the wall hides it.
STUDIO_CLIP_RIGHT = {"cat": 239}

# Brightness window that separates cat from backdrop. The backdrop drifts from
# 17 in the bottom corner to 24 on the left, so the floor sits at 25 -- below
# it every backdrop pixel is fully clear, which is what stops the whole frame
# from picking up a grey wash. The ceiling is where the soft rim of the key
# light has climbed to full opacity.
STUDIO_BG_LUM = 25.5
STUDIO_FG_LUM = 33.0

# The ramp alone is not enough: the shaded underside of the head sits at 27-29,
# barely above the backdrop, and would render as a washed-out fade. So the
# body is also taken as the largest connected blob at this brightness, with
# its interior filled, and the ramp only supplies the soft edge around it.
STUDIO_CORE_LUM = 30.0
STUDIO_EDGE_BLUR = 1.1

# The cat is a head study, where the five checkerboard renders are busts that
# spend roughly half their frame on head and half on shoulders. Letting its
# head fill the sprite would make it read about twice the size of every other
# companion's head, so its frame is padded out to this multiple of the content
# before it is scaled down. Calibrated against the corgi, whose head is the
# closest match in the set. Cannot exceed the source height / content height.
STUDIO_FRAME_SCALE = {"cat": 1.35}

def previous_frames() -> dict[str, tuple[int, int, int, int]]:
    """Frames recorded by the last build, used to report reframing."""
    module = SCRIPT_DIR / GENERATED_MODULE
    if not module.exists():
        return {}
    import importlib.util

    spec = importlib.util.spec_from_file_location("_previous_companion_art", module)
    if spec is None or spec.loader is None:
        return {}
    loaded = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(loaded)
    except Exception:
        return {}
    return dict(getattr(loaded, "SOURCE_FRAMES", {}))


def resolve_source(skin: str) -> Path | None:
    for name in SOURCES.get(skin, []):
        candidate = SOURCE_DIR / name
        if candidate.exists():
            return candidate
    return None


def background_mask(rgb: np.ndarray) -> np.ndarray:
    """Pixels that belong to the neutral checkerboard behind a render."""
    spread = rgb.max(axis=2).astype(np.int16) - rgb.min(axis=2).astype(np.int16)
    lum = rgb.mean(axis=2)
    return (spread <= NEUTRAL_SPREAD) & (lum >= NEUTRAL_LUM_MIN)


def checkerboard_alpha(rgb: np.ndarray) -> np.ndarray:
    """Foreground coverage for a render with a baked-in checkerboard."""
    mask = background_mask(rgb)
    image = Image.fromarray((mask * 255).astype(np.uint8), "L")
    blurred = image.filter(ImageFilter.GaussianBlur(KEY_BLUR))
    return 1.0 - np.asarray(blurred, dtype=np.float32) / 255.0


def largest_blob(mask: np.ndarray) -> np.ndarray:
    """The single biggest four-connected run of True, as a boolean mask."""
    height, width = mask.shape
    labels = np.zeros(mask.shape, dtype=np.int32)
    best = np.zeros(mask.shape, dtype=bool)
    best_size = 0
    count = 0
    for y, x in zip(*np.nonzero(mask)):
        if labels[y, x]:
            continue
        count += 1
        stack = [(int(y), int(x))]
        labels[y, x] = count
        size = 0
        while stack:
            cy, cx = stack.pop()
            size += 1
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not labels[ny, nx]:
                    labels[ny, nx] = count
                    stack.append((ny, nx))
        if size > best_size:
            best_size = size
            best = labels == count
    return best


def fill_holes(mask: np.ndarray) -> np.ndarray:
    """Everything the mask encloses, so shaded interior detail stays opaque."""
    height, width = mask.shape
    free = ~mask
    outside = np.zeros(mask.shape, dtype=bool)
    stack: list[tuple[int, int]] = []
    for y in range(height):
        for x in (0, width - 1):
            if free[y, x] and not outside[y, x]:
                outside[y, x] = True
                stack.append((y, x))
    for x in range(width):
        for y in (0, height - 1):
            if free[y, x] and not outside[y, x]:
                outside[y, x] = True
                stack.append((y, x))
    while stack:
        cy, cx = stack.pop()
        for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
            if 0 <= ny < height and 0 <= nx < width and free[ny, nx] and not outside[ny, nx]:
                outside[ny, nx] = True
                stack.append((ny, nx))
    return mask | (free & ~outside)


def studio_alpha(rgb: np.ndarray, clip_right: int) -> np.ndarray:
    """Foreground coverage for a render shot on a flat dark backdrop.

    Columns at and past ``clip_right`` are forced transparent: that is the lit
    wall rim the cat hides behind, and keeping any of it would both widen the
    frame to the full image height and leave a lit stripe on the mascot.
    """
    lum = rgb[:, :clip_right].mean(axis=2)
    ramp = np.clip((lum - STUDIO_BG_LUM) / (STUDIO_FG_LUM - STUDIO_BG_LUM), 0.0, 1.0)

    body = fill_holes(largest_blob(lum > STUDIO_CORE_LUM)).astype(np.float32)
    # The body is pinned opaque and the ramp only paints the soft rim around
    # it, so the shaded underside of the head cannot fade into the backdrop.
    alpha = np.maximum(ramp, body)
    softened = Image.fromarray((alpha * 255.0).round().astype(np.uint8), "L")
    alpha = np.asarray(softened.filter(ImageFilter.GaussianBlur(STUDIO_EDGE_BLUR)), dtype=np.float32)

    padded = np.zeros(rgb.shape[:2], dtype=np.float32)
    padded[:, :clip_right] = alpha / 255.0
    return padded


def key_alpha(rgb: np.ndarray, skin: str) -> np.ndarray:
    """Foreground coverage in 0..1 for the backdrop style this skin shipped on."""
    clip = STUDIO_CLIP_RIGHT.get(skin)
    if clip is None:
        return checkerboard_alpha(rgb)
    return studio_alpha(rgb, clip)


def content_box(alpha: np.ndarray) -> tuple[int, int, int, int]:
    """Bounding box of the character, ignoring stray keyed noise.

    A plain nonzero() scan picks up isolated compression speckles along the
    border and inflates the box to the full frame, so rows and columns only
    count once they carry a real share of foreground.
    """
    foreground = alpha > 0.35
    rows = np.nonzero(foreground.mean(axis=1) > FRAME_COVERAGE)[0]
    cols = np.nonzero(foreground.mean(axis=0) > FRAME_COVERAGE)[0]
    return int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1


def resolve_frames(verbose: bool = False) -> dict[str, tuple[int, int, int, int]]:
    """Crop frames that keep every companion flush against its cut edge.

    Each render ends its character with a straight vertical edge, but that
    edge sits at a different offset per image (roughly 81% to 96% of the
    frame). A single square crop would therefore leave a wide transparent
    gutter on the right of the narrower ones, and a docked companion would
    visibly float away from the screen edge it is supposed to peek in from.

    So the horizontal extent is trimmed to each companion's own cut edge. For
    the vertical extent, renders shot at the same size share one span -- that
    preserves the headroom each artist left around their character, which is
    what keeps the set at one relative scale. A render shot at a different
    size cannot share a span with them, because no pixel unit relates a
    1254px figure study to a 362px cat; it falls back to its own content box,
    which is the same "the character fills the sprite" convention the shared
    span already approximates for the other five.

    The overlay then only has to pin the image to the docked edge, with no
    per-skin offset table.
    """
    boxes: dict[str, tuple[int, int, int, int]] = {}
    sizes: dict[str, tuple[int, int]] = {}
    for skin in SOURCES:
        path = resolve_source(skin)
        if path is None:
            continue
        with Image.open(path) as source:
            sizes[skin] = source.size
            rgb = np.asarray(source.convert("RGB"), dtype=np.float32)
        boxes[skin] = content_box(key_alpha(rgb, skin))
    if not boxes:
        raise SystemExit("no companion sources found in " + str(SOURCE_DIR))

    spans: dict[tuple[int, int], tuple[int, int]] = {}
    for skin, (_, top, _, bottom) in boxes.items():
        low, high = spans.get(sizes[skin], (top, bottom))
        spans[sizes[skin]] = (min(low, top), max(high, bottom))

    frames: dict[str, tuple[int, int, int, int]] = {}
    for skin, (left, content_top, right, content_bottom) in sorted(boxes.items()):
        top, bottom = spans[sizes[skin]]
        scale = STUDIO_FRAME_SCALE.get(skin)
        if scale is not None:
            # Padded symmetrically about the character instead, since a head
            # study has no pixel scale in common with the busts it shares a
            # span with. Clamped to the source, so the requested framing can
            # only be missed by padding less, never by running off the image.
            source_height = sizes[skin][1]
            height = min(source_height, round((content_bottom - content_top) * scale))
            centre = (content_top + content_bottom) / 2
            top = max(0, min(int(round(centre - height / 2)), source_height - height))
            bottom = top + height
        # Breathing room on the cut edge, except where the character is cut by
        # something the key removed -- padding past the clip would put a
        # transparent gutter back on the edge the overlay pins to.
        cut = right + SOURCE_MARGIN
        clip = STUDIO_CLIP_RIGHT.get(skin)
        if clip is not None:
            cut = min(cut, clip)
        frames[skin] = (max(0, left - SOURCE_MARGIN), top, cut, bottom)
        if verbose:
            print(f"  {skin:6s} content={boxes[skin]} frame={frames[skin]}")
    return frames


def clean_speckles(image: Image.Image) -> Image.Image:
    """Drop isolated slivers left behind by the key."""
    alpha = np.asarray(image.getchannel("A"), dtype=np.float32)
    neighbour = np.asarray(
        image.getchannel("A").filter(ImageFilter.GaussianBlur(SPECKLE_BLUR)), dtype=np.float32
    )
    dropped = (alpha > 0) & (alpha < SPECKLE_ALPHA_LIMIT) & (neighbour < SPECKLE_NEIGHBOUR_LIMIT)
    out = image.copy()
    out.putalpha(Image.fromarray(np.where(dropped, 0.0, alpha).astype(np.uint8), "L"))
    return out


def render(path: Path, skin: str, frame: tuple[int, int, int, int], height: int) -> Image.Image:
    """Key, crop and resize one render into straight-alpha RGBA.

    The crop is scaled to a fixed height and a proportional width, so every
    companion shares one vertical scale and stays flush on its cut edge.
    """
    rgb = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32)
    alpha = key_alpha(rgb, skin)
    left, top, right, bottom = frame
    width = max(1, round(height * (right - left) / (bottom - top)))
    size = (width, height)
    box = (left, top, right, bottom)

    # Premultiplied resize: transparent pixels contribute no colour, which is
    # what keeps the silhouette free of the original light background.
    planes = []
    for index in range(3):
        plane = Image.fromarray(rgb[..., index] * alpha, "F")
        planes.append(np.asarray(plane.resize(size, Image.LANCZOS, box=box), dtype=np.float32))
    alpha_plane = Image.fromarray(alpha * 255.0, "F")
    alpha_small = np.asarray(alpha_plane.resize(size, Image.LANCZOS, box=box), dtype=np.float32) / 255.0

    safe = np.clip(alpha_small, 1e-6, 1.0)
    straight = [np.clip(plane / safe, 0.0, 255.0) for plane in planes]
    stacked = np.dstack([*straight, alpha_small * 255.0]).round().clip(0, 255).astype(np.uint8)
    return clean_speckles(Image.fromarray(stacked, "RGBA"))


def cut_edge_fill(image: Image.Image) -> float:
    """How far the rendered silhouette reaches towards its own right edge.

    Returns the rightmost column that still carries a solid part of the body,
    as a share of the image width. A frame that swallowed keying noise
    instead of the cut edge scores clearly lower here, which is what turns
    "the companion floated off the screen edge" into a build failure.
    """
    alpha = np.asarray(image.getchannel("A"), dtype=np.float32) / 255.0
    covered = np.nonzero((alpha > 0.35).mean(axis=0) >= 0.05)[0]
    if not len(covered):
        return 0.0
    return float(covered.max() + 1) / image.width


def encode(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, "WEBP", quality=WEBP_QUALITY, method=6)
    return buffer.getvalue()


def write_module(
    payloads: dict[str, str],
    frames: dict[str, tuple[int, int, int, int]],
    fills: dict[str, float],
    height: int,
) -> None:
    lines = [
        '"""Generated by scripts/build_companion_art.py. Do not edit by hand.',
        "",
        "Runtime companion artwork, inlined as data URIs so the overlay does not",
        "depend on files that live outside the deployed scripts directory.",
        "",
        "Every companion is cropped flush against its own cut edge and scaled to",
        "a shared height, so the overlay can pin the image straight to the edge",
        "it docks to. Widths differ because the cut edge sits at a different",
        "offset in each source render.",
        "",
        "SOURCE_FRAMES records what this build cropped to, so a future rebuild",
        "that silently reframes the artwork shows up as a reviewable diff.",
        "CUT_EDGE_FILL records how far each rendered body reaches towards the",
        "right edge of its own image; anything below CUT_EDGE_FILL_MIN in the",
        "build script means the companion would float off the docked edge.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        f"RUNTIME_HEIGHT = {height}",
        f"WEBP_QUALITY = {WEBP_QUALITY}",
        "",
        "SOURCE_FRAMES: dict[str, tuple[int, int, int, int]] = {",
    ]
    for skin in sorted(frames):
        lines.append(f'    "{skin}": {frames[skin]},')
    lines += [
        "}",
        "",
        "CUT_EDGE_FILL: dict[str, float] = {",
    ]
    for skin in sorted(fills):
        lines.append(f'    "{skin}": {fills[skin]:.4f},')
    lines += [
        "}",
        "",
        "COMPANION_ART: dict[str, str] = {",
    ]
    for skin in sorted(payloads):
        chunk = payloads[skin]
        lines.append(f'    "{skin}": (')
        # Keep every line inside a comfortable review width.
        for index in range(0, len(chunk), 96):
            lines.append(f'        "{chunk[index:index + 96]}"')
        lines.append("    ),")
    lines.append("}")
    lines.append("")
    (SCRIPT_DIR / GENERATED_MODULE).write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--list", action="store_true", help="report which sources resolve, then stop")
    parser.add_argument("--height", type=int, default=RUNTIME_HEIGHT, help="runtime height in pixels")
    args = parser.parse_args()

    available: dict[str, Path] = {}
    missing: list[str] = []
    for skin in SOURCES:
        path = resolve_source(skin)
        if path is None:
            missing.append(skin)
        else:
            available[skin] = path

    print(f"sources: {len(available)} resolved, {len(missing)} missing")
    for skin, path in sorted(available.items()):
        print(f"  {skin:6s} <- {path.name}")
    for skin in missing:
        print(f"  {skin:6s} <- MISSING (expected one of {', '.join(SOURCES[skin])})")

    if args.list:
        return 0
    if not available:
        print("nothing to build", file=sys.stderr)
        return 1

    print("frames:")
    frames = resolve_frames(verbose=True)
    recorded = previous_frames()
    for skin, frame in sorted(frames.items()):
        if skin in recorded and recorded[skin] != frame:
            print(f"note: {skin} reframed {recorded[skin]} -> {frame}")

    WEB_DIR.mkdir(parents=True, exist_ok=True)
    payloads: dict[str, str] = {}
    fills: dict[str, float] = {}
    print(f"height: {args.height}px, webp q{WEBP_QUALITY}")
    for skin, path in sorted(available.items()):
        image = render(path, skin, frames[skin], args.height)
        fill = cut_edge_fill(image)
        fills[skin] = fill
        data = encode(image)
        (WEB_DIR / f"{skin}.webp").write_bytes(data)
        payloads[skin] = "data:image/webp;base64," + base64.b64encode(data).decode("ascii")
        print(
            f"  {skin:6s} {image.width}x{image.height} {len(data) / 1024:6.1f} KB"
            f"  贴边率 {fill:.3f} -> assets/companions/web/{skin}.webp"
        )

    proud = {skin: fill for skin, fill in fills.items() if fill < CUT_EDGE_FILL_MIN}
    if proud:
        for skin, fill in sorted(proud.items()):
            print(
                f"error: {skin} reaches only {fill:.3f} of its own right edge"
                f" (need {CUT_EDGE_FILL_MIN}); the frame is picking up keying noise"
                " instead of the cut edge, so it would float off the docked edge",
                file=sys.stderr,
            )
        return 1

    write_module(payloads, frames, fills, args.height)
    total = sum(len(value) for value in payloads.values())
    print(f"wrote scripts/{GENERATED_MODULE} ({total / 1024:.1f} KB of data URIs)")
    if missing:
        print("skipped: " + ", ".join(sorted(missing)) + " (overlay falls back to the vector mascot)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
