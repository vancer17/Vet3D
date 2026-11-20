import importlib.util
import unittest
from pathlib import Path

import numpy as np


spec = importlib.util.spec_from_file_location(
    "quad_template", Path(__file__).with_name("hi3d-quad-template.py")
)
quad_template = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quad_template)


def planar_grid(scale=1.0, translation=(0.0, 0.0, 0.0)):
    return {
        (horizontal, vertical): np.array((horizontal, vertical, 0.0)) * scale + translation
        for horizontal in range(5) for vertical in range(5)
    }


def area(coordinates, face):
    corners = coordinates[list(face)]
    return sum(np.linalg.norm(np.cross(corners[index] - corners[0],
                                      corners[index + 1] - corners[0])) / 2
               for index in range(1, len(corners) - 1))


class TemplateTests(unittest.TestCase):
    def setUp(self):
        self.grid = planar_grid()
        self.result = quad_template.build_template(self.grid, (0, 0, 1))
        self.assertIsNotNone(self.result)

    def test_plane_counts_and_closed_loops(self):
        self.assertEqual(self.result["coordinates"].shape, (24, 3))
        self.assertEqual(len(self.result["quads"]), 15)
        self.assertTrue(all(len(face) == 4 for face in self.result["quads"]))
        self.assertEqual(self.result["topology"]["closed_loop_lengths"], [4, 16])
        np.testing.assert_array_equal(self.result["coordinates"][:, 2], np.zeros(24))

    def test_outer_chain_is_unchanged(self):
        expected = [(horizontal, 0) for horizontal in range(5)]
        expected += [(4, vertical) for vertical in range(1, 5)]
        expected += [(horizontal, 4) for horizontal in range(3, -1, -1)]
        expected += [(0, vertical) for vertical in range(3, 0, -1)]
        np.testing.assert_array_equal(self.result["coordinates"][:16],
                                      [self.grid[key] for key in expected])
        expected_edges = {tuple(sorted((index, (index + 1) % 16))) for index in range(16)}
        self.assertEqual(quad_template.boundary_edges(self.result["quads"]), expected_edges)

    def test_center_and_total_area(self):
        areas = [area(self.result["coordinates"], face) for face in self.result["quads"]]
        self.assertTrue(all(value > 0 for value in areas))
        self.assertAlmostEqual(areas[0], 4.0)
        self.assertAlmostEqual(sum(areas), 16.0)

    def test_scale_and_translation(self):
        translation = np.array((2.0, -3.0, 5.0))
        for scale in (1e-5, 1e5):
            with self.subTest(scale=scale):
                transformed = quad_template.build_template(planar_grid(scale, translation), (0, 0, 1))
                self.assertIsNotNone(transformed)
                self.assertEqual(transformed["topology"], self.result["topology"])
                np.testing.assert_allclose(transformed["coordinates"],
                                           self.result["coordinates"] * scale + translation)

    def test_missing_grid_point_is_rejected(self):
        del self.grid[(2, 2)]
        with self.assertRaises(ValueError):
            quad_template.build_template(self.grid, (0, 0, 1))

    def test_nonfinite_input_is_rejected(self):
        self.grid[(2, 2)] = (np.nan, 2, 0)
        with self.assertRaises(ValueError):
            quad_template.build_template(self.grid, (0, 0, 1))

    def test_zero_step_is_rejected(self):
        self.grid[(1, 0)] = self.grid[(0, 0)].copy()
        with self.assertRaises(ValueError):
            quad_template.build_template(self.grid, (0, 0, 1))

    def test_broken_ring_is_rejected(self):
        broken = list(self.result["quads"])
        broken[1] = (0, 1, 2, 3)
        with self.assertRaises(ValueError):
            quad_template.validate_topology(broken)


if __name__ == "__main__":
    unittest.main()
