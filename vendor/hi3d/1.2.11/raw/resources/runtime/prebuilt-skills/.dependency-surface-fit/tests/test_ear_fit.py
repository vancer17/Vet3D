"""Behavioral tests for volume boundary continuity and input protection."""

import sys
import unittest
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ear_fit import grid_matrix, grid_lap, validate_inputs


class EarFitTests(unittest.TestCase):
    def test_shared_field_is_continuous_and_fixed_outside_boundary(self):
        shape = (5, 5, 5)
        _, boundary = grid_lap(shape)
        field = np.zeros((125, 3))
        field[~boundary, 0] = 0.1
        points = np.array(
            [[2, 2, 2], [2, 2, 2.00001], [0, 2, 2], [-0.1, 2, 2], [4, 2, 2]]
        )
        step = grid_matrix(points, np.zeros(3), 1.0, shape) @ field
        np.testing.assert_allclose(step[:2], [[0.1, 0, 0], [0.1, 0, 0]])
        np.testing.assert_array_equal(step[2:], np.zeros((3, 3)))

    def test_invalid_inputs_fail_before_solving(self):
        v = np.array([[0.0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]])
        original = dict(vertices=v, rest=v.copy(), quads=np.array([[0, 1, 2, 3]]))
        target = np.tile(v, (6, 1))
        normals = np.tile([0.0, -1, 0], (24, 1))
        regions = dict(
            ear_regions=[
                dict(name="right", core_indices=[0]),
                dict(name="left", core_indices=[3]),
            ]
        )
        record = dict(
            id=220,
            ear="left",
            triangle=[0, 1, 2],
            barycentric=[0.2, 0.3, 0.5],
            target=[0.0, 0, 1],
        )
        validate_inputs(original, v, [record], regions, target, normals, [2])
        for broken in [
            dict(record, barycentric=[-0.1, 0.3, 0.8]),
            dict(record, triangle=[0, 1, 99]),
            dict(record, weight=0),
            dict(record, target=[np.nan, 0, 0]),
        ]:
            with self.subTest(record=broken), self.assertRaises(ValueError):
                validate_inputs(original, v, [broken], regions, target, normals, [2])
        with self.assertRaises(ValueError):
            validate_inputs(
                original, v, [record, record], regions, target, normals, [2]
            )


if __name__ == "__main__":
    unittest.main()
