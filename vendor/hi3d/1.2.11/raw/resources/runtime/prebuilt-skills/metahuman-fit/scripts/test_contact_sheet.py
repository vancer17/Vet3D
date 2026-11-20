"""Recipe layout remains independent of the shared image-cell compositor."""
import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from contact_sheet import make_sheet, make_expression_sheet


class ContactSheetTests(unittest.TestCase):
    def test_modes_are_columns_and_views_are_rows_below_recipe_header(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root/'renders').mkdir()
            colors = {}
            for row, angle in enumerate(['front', 'side', 'threequarter']):
                for col, mode in enumerate(['highpoly', 'lowpoly', 'geometry', 'detail']):
                    color = (40+col*40, 40+row*60, 100)
                    colors[row, col] = color
                    Image.new('RGB', (180, 100), color).save(root/'renders'/f'{mode}_{angle}.png')
            make_sheet(root, tile=120, source_geometry=True)
            with Image.open(root/'overview.jpg') as image:
                self.assertEqual(image.size, (480, 520))
                for (row, col), color in colors.items():
                    pixel = image.getpixel((col*120+60, 70+row*150+60))
                    self.assertTrue(all(abs(a-b) <= 3 for a,b in zip(pixel, color)))

    def test_expression_order_partial_row_and_empty_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root/'expressions').mkdir()
            poses = [{'name': name} for name in ['neutral', 'smile', 'blink', 'open', 'look']]
            (root/'expression_report.json').write_text(json.dumps({'poses': poses}))
            for i in range(5):
                Image.new('RGB', (90, 150), (30*i, 80, 100)).save(root/'expressions'/f'pose_{i:02d}.png')
            make_expression_sheet(root, tile=120)
            with Image.open(root/'expressions.jpg') as image:
                self.assertEqual(image.size, (360, 370))
                for i in range(5):
                    self.assertLessEqual(abs(image.getpixel((i%3*120+60, 70+i//3*150+60))[0]-30*i), 3)
            (root/'expressions.jpg').unlink()
            (root/'expression_report.json').write_text('{"poses": []}')
            with self.assertRaises(ValueError): make_expression_sheet(root)
            self.assertFalse((root/'expressions.jpg').exists())


if __name__ == '__main__': unittest.main()
