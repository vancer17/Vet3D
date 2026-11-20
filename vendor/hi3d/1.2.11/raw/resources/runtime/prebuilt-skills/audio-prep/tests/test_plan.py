import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import plan_mix


class AudioPlanTests(unittest.TestCase):
    def test_mix_uses_trim(self):
        spec = plan_mix.mix_spec({
            'schemaVersion': 1,
            'path': 'take.wav',
            'duration': 10,
            'trimStart': 1,
            'trimEnd': 4,
            'fadeIn': 0.1,
            'fadeOut': 0.1,
        })
        self.assertEqual(spec['duration'], 3)
        self.assertEqual(spec['tracks'][0]['start'], 1)
        self.assertEqual(spec['tracks'][0]['end'], 4)

    def test_rejects_interior_trim(self):
        with self.assertRaises(ValueError):
            plan_mix.validate_brief({
                'schemaVersion': 1,
                'path': 'take.wav',
                'duration': 10,
                'trimInteriorPauses': True,
            })

    def test_rejects_denoise(self):
        with self.assertRaises(ValueError):
            plan_mix.validate_brief({
                'schemaVersion': 1,
                'path': 'take.wav',
                'duration': 10,
                'denoise': True,
            })


if __name__ == '__main__':
    unittest.main()
