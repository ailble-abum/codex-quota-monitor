"""Remove a generated atlas's near-black matte before exporting companion frames."""
import argparse
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from validate_companion_atlas import validate


def fill_small_holes(alpha, region):
    left, top, right, bottom = region
    pixels = alpha.load()
    seen = bytearray(512 * 512)
    for sy in range(top, bottom + 1):
        for sx in range(left, right + 1):
            start = sy * 512 + sx
            if seen[start] or pixels[sx, sy] > 5:
                continue
            seen[start] = 1
            queue = deque([(sx, sy)])
            group = []
            bounds = [sx, sy, sx, sy]
            touches_edge = False
            while queue:
                x, y = queue.popleft()
                group.append((x, y))
                bounds = [min(bounds[0], x), min(bounds[1], y), max(bounds[2], x), max(bounds[3], y)]
                touches_edge |= x in (0, 511) or y in (0, 511)
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if 0 <= nx < 512 and 0 <= ny < 512 and pixels[nx, ny] <= 5:
                        position = ny * 512 + nx
                        if not seen[position]:
                            seen[position] = 1
                            queue.append((nx, ny))
            if (not touches_edge and len(group) <= 1000 and
                    left <= bounds[0] <= bounds[2] <= right and top <= bounds[1] <= bounds[3] <= bottom):
                ImageDraw.Draw(alpha).point(group, fill=255)


def prepare(source: Path, target: Path, clear=(), threshold=20, alpha_range=24, fill_holes=None):
    with Image.open(source) as input_image:
        if input_image.size != (1536, 1024) or input_image.mode != 'RGB':
            raise ValueError('expected a 1536x1024 RGB atlas')
        atlas = input_image.copy()
    result = Image.new('RGBA', atlas.size)
    for index in range(6):
        x, y = (index % 3) * 512, (index // 3) * 512
        frame = atlas.crop((x, y, x + 512, y + 512))
        if any(max(frame.getpixel(point)) > 10 for point in ((0, 0), (511, 0), (0, 511), (511, 511))):
            raise ValueError(f'frame {index + 1} has a non-black background')
        red, green, blue = frame.split()
        brightness = ImageChops.lighter(ImageChops.lighter(red, green), blue)
        mask = brightness.point(lambda value: 255 if value > threshold else 0)
        seed = next(((px, py) for py in range(150, 350) for px in range(150, 350)
                     if mask.getpixel((px, py)) == 255), None)
        if seed is None:
            raise ValueError(f'frame {index + 1} has no subject')
        ImageDraw.floodfill(mask, seed, 128, thresh=0)
        subject = mask.point(lambda value: 255 if value == 128 else 0)
        alpha = brightness.point(lambda value: max(0, min(255, int((value - 2) * 255 / alpha_range))))
        alpha = ImageChops.multiply(alpha, subject.filter(ImageFilter.MaxFilter(3)))
        alpha = alpha.filter(ImageFilter.GaussianBlur(.45))
        if fill_holes:
            fill_small_holes(alpha, fill_holes)
        for cell, box in clear:
            if cell == index:
                ImageDraw.Draw(alpha).rectangle(box, fill=0)
        frame.putalpha(alpha)
        result.paste(frame, (x, y))
    result.save(target)
    validate(target)


def clear_box(value):
    parts = tuple(map(int, value.split(':')))
    if len(parts) != 5 or not 0 <= parts[0] < 6 or not (0 <= parts[1] < parts[3] < 512
                                                       and 0 <= parts[2] < parts[4] < 512):
        raise argparse.ArgumentTypeError('use cell:left:top:right:bottom')
    return parts[0], parts[1:]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('target', type=Path)
    parser.add_argument('--clear', action='append', type=clear_box, default=[])
    parser.add_argument('--threshold', type=int, default=20)
    parser.add_argument('--alpha-range', type=int, default=24)
    parser.add_argument('--fill-dark-holes', type=lambda value: tuple(map(int, value.split(':'))))
    args = parser.parse_args()
    if not 2 < args.threshold < 255 or not 0 < args.alpha_range < 255:
        parser.error('invalid matte parameters')
    if args.fill_dark_holes and (len(args.fill_dark_holes) != 4 or
                                 not (0 <= args.fill_dark_holes[0] < args.fill_dark_holes[2] < 512 and
                                      0 <= args.fill_dark_holes[1] < args.fill_dark_holes[3] < 512)):
        parser.error('invalid hole region')
    prepare(args.source, args.target, args.clear, args.threshold, args.alpha_range, args.fill_dark_holes)
