"""Offline regression for local repairs and scale-aware stretch screening."""

import unittest
import numpy as np
from .skin_weights import repair_regions, stretch_metrics


class Tests(unittest.TestCase):
    def setUp(self):
        self.v = np.array([[1.0, 0, 0], [1.0, 0, 0], [1.1, 0, 0], [-1.0, 0, 0]])
        self.w = np.array(
            [[0.7, 0.2, 0.1], [0.8, 0.15, 0.05], [1, 0, 0], [0.05, 0, 0.95]], np.float32
        )
        self.names = ["palm.left", "thumb.left", "thumb.right"]
        self.rules = [
            dict(bounds=[[0.9, -1, -1], [1.2, 1, 1]], forbidden_bones=["thumb.right"])
        ]

    def test_local_repair_keeps_finger_blends_and_shared_positions(self):
        before = self.w.copy()
        out, report = repair_regions(self.v, self.w, self.names, self.rules)
        np.testing.assert_array_equal(self.w, before)
        np.testing.assert_array_equal(out[0], out[1])
        np.testing.assert_array_equal(out[2:], before[2:])
        self.assertTrue(np.all(out[:2, :2] > 0))
        self.assertTrue(np.all(out[:3, 2] == 0))
        np.testing.assert_allclose(out.sum(1), 1)
        self.assertEqual(report["changed_vertices"], 2)

    def test_repair_is_idempotent(self):
        out, _ = repair_regions(self.v, self.w, self.names, self.rules)
        again, report = repair_regions(self.v, out, self.names, self.rules)
        np.testing.assert_array_equal(out, again)
        self.assertEqual(report["changed_vertices"], 0)

    def test_refuses_unbound_or_unmatched_regions(self):
        for rule in [
            dict(self.rules[0], forbidden_bones=self.names),
            dict(self.rules[0], forbidden_bones=["missing"]),
            dict(self.rules[0], bounds=[[2, 2, 2], [3, 3, 3]]),
        ]:
            with self.assertRaises(ValueError):
                repair_regions(self.v, self.w, self.names, [rule])

    def test_refuses_invalid_weights(self):
        for value in [np.nan, -1.0, 2.0]:
            w = self.w.copy()
            w[0, 0] = value
            with self.assertRaises(ValueError):
                repair_regions(self.v, w, self.names, self.rules)

    def test_growth_threshold_is_scale_aware_and_not_ratio_only(self):
        v = np.array([[0.0, 0, 0], [0.001, 0, 0], [0, 0.001, 0]])
        f = np.array([[0, 1, 2]])
        tiny = stretch_metrics(v, v * 4, f, 1.8)
        self.assertEqual(tiny["significant_faces"], 0)
        p = v.copy()
        p[0, 0] = 0.06
        bad = stretch_metrics(v, p, f, 1.8)
        scaled = stretch_metrics(v * 100, p * 100, f, 180)
        self.assertEqual(bad["significant_faces"], 1)
        self.assertEqual(bad["significant_faces"], scaled["significant_faces"])
        self.assertEqual(bad["worst_faces"], [0])


def main(argv=None):
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(Tests)
    )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
