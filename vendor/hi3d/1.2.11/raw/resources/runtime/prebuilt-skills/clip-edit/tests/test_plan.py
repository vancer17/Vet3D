import json
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import plan_edit


class ClipPlanTests(unittest.TestCase):
    def test_preview_halves_even_size(self):
        spec = {
            'schemaVersion': 1,
            'preset': 'portrait',
            'clips': [{'path': 'a.mp4', 'start': 0, 'end': 2}],
        }
        plan = plan_edit.plan(spec, preview=True)
        self.assertEqual(plan['mediaEdit']['width'], 540)
        self.assertEqual(plan['mediaEdit']['height'], 960)

    def test_rejects_inverted_clip(self):
        spec = {
            'schemaVersion': 1,
            'clips': [{'path': 'a.mp4', 'start': 2, 'end': 1}],
        }
        with self.assertRaises(ValueError):
            plan_edit.validate_timeline(spec)

    def test_mix_offsets_source_audio(self):
        spec = {
            'schemaVersion': 1,
            'keepSourceAudio': True,
            'clips': [
                {'path': 'a.mp4', 'start': 0, 'end': 1},
                {'path': 'b.mp4', 'start': 0, 'end': 2},
            ],
        }
        mix = plan_edit.mix_spec('cut.mp4', spec, 3)
        self.assertEqual(mix['tracks'][0]['offset'], 0)
        self.assertEqual(mix['tracks'][1]['offset'], 1)


if __name__ == '__main__':
    unittest.main()
