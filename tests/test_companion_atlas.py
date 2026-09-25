import tempfile
import unittest
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


if __name__ == '__main__':
    unittest.main()
