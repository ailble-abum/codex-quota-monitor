"""Export six 320px WebP expressions per non-cat companion atlas."""
import argparse
from pathlib import Path

from PIL import Image

from validate_companion_atlas import validate


ROOT = Path(__file__).parents[1] / 'assets/companions'
SKINS = ('candy', 'corgi', 'frost', 'mint', 'tea')
NAMES = ('idle', 'happy', 'concerned', 'notice', 'waiting', 'pet')


def export(skin):
    source = ROOT / 'sources' / f'{skin}-atlas.png'
    validate(source)
    with Image.open(source) as atlas:
        for index, name in enumerate(NAMES):
            x, y = (index % 3) * 512, (index // 3) * 512
            atlas.crop((x, y, x + 512, y + 512)).resize(
                (320, 320), Image.Resampling.LANCZOS).save(
                    ROOT / 'expressions' / f'{skin}-{name}.webp', 'WEBP', quality=90, method=6)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('skins', nargs='*', choices=SKINS, default=SKINS)
    for skin in parser.parse_args().skins:
        export(skin)
