#!/usr/bin/env python3
"""Build the runtime companion artwork used by the injected overlay.

The source renders in ``assets/companions`` are square images whose
"transparency" was baked in as a checkerboard instead of a real alpha
channel. This script

1. keys that checkerboard out into a real alpha channel,
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
FRAME_COVERAGE = 0.005

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


def key_alpha(rgb: np.ndarray) -> np.ndarray:
    """Foreground coverage in 0..1, slightly blurred to keep the silhouette smooth."""
    mask = background_mask(rgb)
    image = Image.fromarray((mask * 255).astype(np.uint8), "L")
    blurred = image.filter(ImageFilter.GaussianBlur(KEY_BLUR))
    return 1.0 - np.asarray(blurred, dtype=np.float32) / 255.0


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

    So the frames share one vertical extent -- keeping the vertical scale
    identical across the set -- while the horizontal extent is trimmed to
    each companion's own cut edge. The overlay then only has to pin the
    image to the docked edge, with no per-skin offset table.
    """
    boxes: dict[str, tuple[int, int, int, int]] = {}
    for skin in SOURCES:
        path = resolve_source(skin)
        if path is None:
            continue
        rgb = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32)
        boxes[skin] = content_box(key_alpha(rgb))
    if not boxes:
        raise SystemExit("no companion sources found in " + str(SOURCE_DIR))

    top = min(box[1] for box in boxes.values())
    bottom = max(box[3] for box in boxes.values())
    frames: dict[str, tuple[int, int, int, int]] = {}
    for skin, (left, _, right, _) in sorted(boxes.items()):
        frames[skin] = (
            max(0, left - SOURCE_MARGIN),
            top,
            right + SOURCE_MARGIN,
            bottom,
        )
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


def render(path: Path, frame: tuple[int, int, int, int], height: int) -> Image.Image:
    """Key, crop and resize one render into straight-alpha RGBA.

    The crop is scaled to a fixed height and a proportional width, so every
    companion shares one vertical scale and stays flush on its cut edge.
    """
    rgb = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32)
    alpha = key_alpha(rgb)
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


def encode(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, "WEBP", quality=WEBP_QUALITY, method=6)
    return buffer.getvalue()


def write_module(
    payloads: dict[str, str],
    frames: dict[str, tuple[int, int, int, int]],
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
    print(f"height: {args.height}px, webp q{WEBP_QUALITY}")
    for skin, path in sorted(available.items()):
        image = render(path, frames[skin], args.height)
        data = encode(image)
        (WEB_DIR / f"{skin}.webp").write_bytes(data)
        payloads[skin] = "data:image/webp;base64," + base64.b64encode(data).decode("ascii")
        print(f"  {skin:6s} {image.width}x{image.height} {len(data) / 1024:6.1f} KB -> assets/companions/web/{skin}.webp")

    write_module(payloads, frames, args.height)
    total = sum(len(value) for value in payloads.values())
    print(f"wrote scripts/{GENERATED_MODULE} ({total / 1024:.1f} KB of data URIs)")
    if missing:
        print("skipped: " + ", ".join(sorted(missing)) + " (overlay falls back to the vector mascot)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
