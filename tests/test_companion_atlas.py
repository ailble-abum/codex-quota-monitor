import tempfile
import unittest
import subprocess
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None

@unittest.skipUnless(Image, 'Pillow is an asset build dependency')
class AtlasTests(unittest.TestCase):
    def test_current_atlas_and_invalid_backgrounds(self):
        from tools.validate_companion_atlas import validate
        root = Path(__file__).parents[1]
        for skin in ('candy', 'corgi', 'frost', 'mint', 'tea'):
            validate(root / f'assets/companions/sources/{skin}-atlas.png')
            for name in ('idle', 'happy', 'concerned', 'notice', 'waiting', 'pet'):
                with Image.open(root / f'assets/companions/expressions/{skin}-{name}.webp') as frame:
                    self.assertEqual(frame.size, (320, 320))
                    self.assertEqual(frame.mode, 'RGBA')
        validate(root / 'assets/companions/sources/nova-atlas.png')
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'atlas.png'
            Image.new('RGB', (1536, 1024), 'black').save(target)
            with self.assertRaisesRegex(ValueError, 'RGBA'):
                validate(target)
            Image.new('RGBA', (1536, 1024), 'white').save(target)
            with self.assertRaisesRegex(ValueError, 'transparent'):
                validate(target)
            atlas = Image.new('RGBA', (1536, 1024))
            for index in range(6):
                atlas.putpixel(((index % 3) * 512 + 20, (index // 3) * 512 + 20), (index, 0, 0, 255))
            atlas.save(target)
            validate(target)
            atlas.putpixel((2 * 512 + 20, 512 + 20), (4, 0, 0, 255))
            atlas.save(target)
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                validate(target)

    def test_matte_cleanup_outputs_transparent_frames(self):
        from tools.validate_companion_atlas import validate
        root = Path(__file__).parents[1]
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / 'source.png', Path(directory) / 'clean.png'
            atlas = Image.new('RGB', (1536, 1024), 'black')
            for index in range(6):
                frame = Image.new('RGB', (120, 120), (index + 70, 80, 90))
                atlas.paste(frame, ((index % 3) * 512 + 200, (index // 3) * 512 + 170))
            atlas.save(source)
            subprocess.run([sys.executable, str(root / 'tools/prepare_companion_atlas.py'),
                            str(source), str(target)], check=True, cwd=root)
            validate(target)
            self.assertEqual(Image.open(target).getpixel((0, 0))[3], 0)
            atlas.putpixel((0, 0), (180, 180, 180))
            atlas.save(source)
            failed = subprocess.run([sys.executable, str(root / 'tools/prepare_companion_atlas.py'),
                                     str(source), str(target)], capture_output=True, text=True, cwd=root)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn('non-black background', failed.stderr)


if __name__ == '__main__':
    unittest.main()
