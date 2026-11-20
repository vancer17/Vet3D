import tempfile
import unittest
from pathlib import Path
import cv2
import numpy as np
from fill_projection import fill_unobserved, run


class ProjectionFillTests(unittest.TestCase):
    def test_observed_pixels_preserved_and_gaps_use_observations(self):
        color = np.zeros((5, 7, 3), np.uint8)
        color[:, 0] = [20, 40, 80]
        color[:, -1] = [90, 60, 30]
        mask = np.zeros((5, 7), np.uint8)
        mask[:, [0, -1]] = 255
        filled, valid = fill_unobserved(color, mask, 0)
        np.testing.assert_array_equal(filled[valid], color[valid])
        self.assertTrue(np.all(np.any(filled != 0, axis=2)))
        self.assertEqual(set(map(tuple, filled.reshape(-1, 3))),
                         {(20, 40, 80), (90, 60, 30)})

    def test_missing_observations_are_rejected(self):
        with self.assertRaises(ValueError):
            fill_unobserved(np.zeros((3, 3, 3), np.uint8), np.zeros((3, 3), np.uint8))

    def test_cli_atom_preserves_source_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            color = np.full((5, 5, 3), 120, np.uint8)
            mask = np.full((5, 5), 255, np.uint8)
            cv2.imwrite(str(root/'source.png'), color)
            cv2.imwrite(str(root/'mask.png'), mask)
            before = (root/'source.png').read_bytes()
            report = run(root/'source.png', root/'mask.png', root/'filled.png')
            self.assertEqual((root/'source.png').read_bytes(), before)
            self.assertEqual(report['status'], 'completed')
            with self.assertRaises(ValueError):
                run(root/'source.png', root/'mask.png', root/'filled.png')


if __name__ == '__main__':
    unittest.main()
