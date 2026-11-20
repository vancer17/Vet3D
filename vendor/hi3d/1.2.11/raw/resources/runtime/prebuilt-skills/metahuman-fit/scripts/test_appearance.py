"""Validate neck constraints and multiscale Poisson alignment with synthetic data."""

import unittest
import numpy as np
from neck import fair_neck, validate_neck_mask
from skin_tone import multiscale_poisson


class AppearanceTests(unittest.TestCase):
    def test_neck_extends_displacement_and_keeps_boundary_fixed(self):
        rest = np.array([[x, y, 0.0] for y in range(4) for x in range(4)])
        q = np.array(
            [
                [y * 4 + x, y * 4 + x + 1, (y + 1) * 4 + x + 1, (y + 1) * 4 + x]
                for y in range(3)
                for x in range(3)
            ]
        )
        free = np.array([5, 6, 9, 10])
        fitted = rest + [0.1, 0.2, 0.3]
        fitted[free, 2] += 0.4
        fixed = np.setdiff1d(np.arange(len(rest)), free)
        result, report = fair_neck(rest, fitted, q, free, fixed)
        np.testing.assert_allclose(result, rest + [0.1, 0.2, 0.3], atol=1e-10)
        np.testing.assert_array_equal(result[fixed], fitted[fixed])
        self.assertEqual(report["protected_maximum_displacement"], 0)
        self.assertLess(report["bending_energy_after"], report["bending_energy_before"])

    def test_neck_rejects_facial_overlap_and_missing_protection(self):
        with self.assertRaisesRegex(ValueError, "overlaps"):
            validate_neck_mask([1, 2, 3], [3, 4, 5])
        with self.assertRaisesRegex(ValueError, "explicit"):
            validate_neck_mask([1, 2, 3], [])

    def test_poisson_keeps_uv_features_aligned_and_background_unchanged(self):
        template = np.full((256, 256, 3), [120, 90, 75], np.uint8)
        source = np.full_like(template, [185, 135, 110])
        mask = np.zeros((256, 256), np.uint8)
        mask[30:225, 45:220] = 255
        source[100:108, 120:128] = [25, 20, 15]
        result = multiscale_poisson(source, template, mask, 64)
        np.testing.assert_array_equal(result[mask == 0], template[mask == 0])
        self.assertLess(result[104, 124].mean(), result[104, 145].mean() - 70)
        self.assertLess(
            abs(result[31, 100].astype(float) - template[31, 100]).max(), 20
        )

    def test_poisson_identity(self):
        image = np.full((128, 128, 3), [160, 110, 95], np.uint8)
        mask = np.zeros((128, 128), np.uint8)
        mask[25:100, 25:100] = 255
        result = multiscale_poisson(image, image, mask, 64)
        self.assertLessEqual(abs(result.astype(float) - image).max(), 2)


if __name__ == "__main__":
    unittest.main()
