"""Export the project-generated Nova sprites as the six runtime WebP frames.

Run with a Python environment containing Pillow; Pillow is not a runtime dependency.
"""
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).parents[1] / 'assets' / 'companions'
NAMES = ('idle', 'happy', 'concerned', 'notice', 'waiting', 'pet')


def main():
    atlas = Image.open(ROOT / 'sources' / 'nova-atlas.png').convert('RGBA')
    notice = Image.open(ROOT / 'sources' / 'nova-notice.png').convert('RGBA')
    if atlas.size != (1536, 1024) or notice.size != (1254, 1254):
        raise ValueError('unexpected Nova source dimensions')
    if atlas.getchannel('A').getpixel((0, 0)) or notice.getchannel('A').getpixel((0, 0)):
        raise ValueError('Nova sources require transparent backgrounds')

    frames = [atlas.crop(((index % 3) * 512, (index // 3) * 512,
                          (index % 3 + 1) * 512, (index // 3 + 1) * 512))
              for index in range(6)]
    # The replacement notice has one paw. This crop keeps its body at the
    # same right-side anchor as the five atlas frames.
    frames[3] = notice.crop((62, 0, 1086, 1024)).resize((512, 512), Image.Resampling.LANCZOS)
    for name, frame in zip(NAMES, frames):
        target = ROOT / 'expressions' / ('cat-' + name + '.webp')
        frame.resize((320, 320), Image.Resampling.LANCZOS).save(target, 'WEBP', quality=90, method=6)
    frames[0].resize((320, 320), Image.Resampling.LANCZOS).save(
        ROOT / 'web' / 'cat.webp', 'WEBP', quality=90, method=6)


if __name__ == '__main__':
    main()
