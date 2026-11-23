import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from replace_brief import (
    SCHEMA,
    build_output,
    image_size,
    main,
    request_gaps,
    validate_brief,
)


def write_png(path, size=(40, 30), color=(10, 20, 30)):
    Image.new('RGB', size, color).save(path, format='PNG')
    return path


def sample_brief(screenshot_id='main', provided=None):
    return {
        'schema': SCHEMA,
        'intent': '把左侧雕像换成用户的手办',
        'screenshots': [{'id': screenshot_id}],
        'targets': [
            {
                'id': 'statue',
                'label': '左侧雕像',
                'role': 'replace',
                'screenshot_id': screenshot_id,
                'bbox_px_xyxy': [2, 4, 18, 28],
                'bbox_norm_xyxy': [2 / 40, 4 / 30, 18 / 40, 28 / 30],
                'evidence': '整身可见，脚踩平台',
                'inferred': ['背面'],
                'material_needed': {
                    'minimum': ['single_photo'],
                    'preferred': ['single_photo', 'existing_glb'],
                    'notes': '背景尽量干净',
                },
                'provided': provided or [],
            },
            {
                'id': 'hall',
                'label': '背景殿宇',
                'role': 'keep',
                'screenshot_id': screenshot_id,
                'bbox_px_xyxy': [20, 1, 39, 16],
                'evidence': '屋脊与柱列',
                'inferred': [],
            },
        ],
    }


class ReplaceBriefTests(unittest.TestCase):
    def test_valid_brief_crops_and_asks_for_missing_photo(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            shot = write_png(root / 'shot.png')
            output = root / 'out'
            result = build_output(sample_brief(), {'main': shot}, output)
            self.assertTrue((output / 'brief.json').is_file())
            self.assertEqual(result['awaiting'], ['statue'])
            self.assertEqual(result['ready'], [])
            with Image.open(output / 'crops' / 'statue.png') as crop:
                self.assertEqual(crop.size, (16, 24))
            with Image.open(output / 'overlay.png') as overlay:
                self.assertEqual(overlay.size, (40, 30))
                self.assertNotEqual(list(overlay.getpixel((2, 4))), [10, 20, 30])
            with Image.open(shot) as source:
                self.assertEqual(source.getpixel((2, 4)), (10, 20, 30))
            requests = json.loads((output / 'requests.json').read_text())
            self.assertIn('单张清晰照片', requests[0]['ask'])
            self.assertIn('左侧雕像', requests[0]['ask'])
            self.assertEqual(requests[0]['missing'], ['single_photo'])

    def test_provided_minimum_clears_the_request(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            shot = write_png(root / 'shot.png')
            photo = write_png(root / 'object.png', size=(8, 8), color=(200, 10, 10))
            brief = sample_brief(provided=[{'path': str(photo), 'kind': 'single_photo'}])
            result = build_output(brief, {'main': shot}, root / 'out')
            self.assertEqual(result['awaiting'], [])
            self.assertEqual(result['ready'], ['statue'])
            self.assertEqual(json.loads((root / 'out' / 'requests.json').read_text()), [])

    def test_rejects_out_of_bounds_and_mismatched_normalized_boxes(self):
        with tempfile.TemporaryDirectory() as folder:
            shot = write_png(Path(folder) / 'shot.png')
            sizes = {'main': image_size(shot)}
            bad = sample_brief()
            bad['targets'][0]['bbox_px_xyxy'] = [0, 0, 80, 10]
            with self.assertRaises(ValueError):
                validate_brief(bad, sizes=sizes)
            mismatch = sample_brief()
            mismatch['targets'][0]['bbox_norm_xyxy'] = [0, 0, 1, 1]
            with self.assertRaises(ValueError):
                validate_brief(mismatch, sizes=sizes)

    def test_refuses_to_overwrite_output_or_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            shot = write_png(root / 'shot.png')
            output = root / 'out'
            build_output(sample_brief(), {'main': shot}, output)
            before = shot.read_bytes()
            with self.assertRaises(FileExistsError):
                build_output(sample_brief(), {'main': shot}, output)
            self.assertEqual(shot.read_bytes(), before)

    def test_request_gaps_ignore_keep_targets(self):
        requests, targets = request_gaps(sample_brief()['targets'])
        self.assertEqual([item['target_id'] for item in requests], ['statue'])
        status = {item['id']: item['status'] for item in targets}
        self.assertEqual(status['hall'], 'skipped_keep')
        self.assertEqual(status['statue'], 'awaiting_material')

    def test_cli_check_and_build(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            shot = write_png(root / 'shot.png')
            brief_path = root / 'brief.json'
            brief_path.write_text(json.dumps(sample_brief(), ensure_ascii=False))
            self.assertEqual(main([
                '--check', '--brief', str(brief_path),
                '--screenshot', 'main', str(shot),
            ]), 0)
            output = root / 'out'
            self.assertEqual(main([
                '--brief', str(brief_path),
                '--screenshot', 'main', str(shot),
                '--output', str(output),
            ]), 0)
            self.assertTrue((output / 'requests.json').is_file())


if __name__ == '__main__':
    unittest.main()
