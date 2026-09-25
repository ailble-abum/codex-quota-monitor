"""Check a six-frame companion atlas before any WebP export (Pillow required)."""
import argparse
from pathlib import Path

from PIL import Image


def validate(path: Path):
    with Image.open(path) as atlas:
        if atlas.size != (1536, 1024) or atlas.mode != 'RGBA':
            raise ValueError('atlas must be 1536x1024 RGBA')
        seen = set()
        for index in range(6):
            x, y = (index % 3) * 512, (index // 3) * 512
            frame = atlas.crop((x, y, x + 512, y + 512))
            alpha = frame.getchannel('A')
            if not alpha.getbbox() or any(alpha.getpixel(point) > 5 for point in ((0, 0), (0, 511))):
                raise ValueError(f'frame {index + 1} lacks transparent left corners or character')
            seen.add(frame.tobytes())
    if len(seen) != 6:
        raise ValueError('atlas contains duplicate frames')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('atlas', type=Path)
    validate(parser.parse_args().atlas)
