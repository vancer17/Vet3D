"""Run in a materialized landmark-project package; no Blender or services needed."""

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ear_projection import orthographic_ray, fuse_observations, validate_mapping


class EarProjectionTests(unittest.TestCase):
    def setUp(self):
        self.camera = dict(
            width=100,
            height=100,
            ortho_scale=2,
            camera_matrix_world=np.eye(4).tolist(),
            projection="orthographic",
        )

    def test_pixel_orientation_and_world_translation(self):
        self.camera["camera_matrix_world"][0][3] = 4
        origin, direction = orthographic_ray(self.camera, [75, 25])
        np.testing.assert_allclose(origin, [4.5, 0.5, 0])
        np.testing.assert_allclose(direction, [0, 0, -1])

    def test_unsupported_cameras_and_pixels_rejected(self):
        for key, value in [
            ("projection", "perspective"),
            ("width", 200),
            ("shift_x", 0.1),
            ("ortho_scale", 0),
        ]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                orthographic_ray(dict(self.camera, **{key: value}), [50, 50])
        with self.assertRaises(ValueError):
            orthographic_ray(self.camera, [100, 50])
        c = copy.deepcopy(self.camera)
        c["camera_matrix_world"][0][0] = 2
        with self.assertRaises(ValueError):
            orthographic_ray(c, [50, 50])

    def test_incompatible_surfaces_are_not_averaged_and_units_scale(self):
        obs = [
            dict(view="front", facing=0.2, point=[0, 0, 0]),
            dict(view="left_oblique", facing=0.9, point=[0.1, 0, 0]),
        ]
        point, confidence, _, _ = fuse_observations(obs, 1)
        np.testing.assert_array_equal(point, obs[1]["point"])
        self.assertEqual(confidence, 0.2)
        scaled = [dict(o, point=(np.array(o["point"]) * 1000).tolist()) for o in obs]
        p2, c2, _, _ = fuse_observations(scaled, 1000)
        np.testing.assert_allclose(p2, point * 1000)
        self.assertEqual(c2, confidence)
        self.assertEqual(fuse_observations(obs[:1], 1)[1], 0.45)

    def test_frozen_map_is_bound_to_packaged_template(self):
        assets = Path(__file__).resolve().parents[1] / "assets/taro"
        mapping = json.loads((assets / "sapiens2_ear_mapping.json").read_text())
        sha = hashlib.sha256((assets / "template.npz").read_bytes()).hexdigest()
        validate_mapping(mapping, sha)
        self.assertEqual(len(mapping["records"]), 49)
        with self.assertRaises(ValueError):
            validate_mapping(mapping, "another template")
        with self.assertRaises(ValueError):
            validate_mapping(dict(mapping, records=mapping["records"] * 2), sha)
        template = np.load(assets / "template.npz", allow_pickle=False)
        q = template["quads"]
        triangles = {
            tuple(t) for t in np.concatenate((q[:, [0, 1, 2]], q[:, [0, 2, 3]]))
        }
        for row in mapping["records"]:
            self.assertIn(tuple(row["triangle"]), triangles)
            self.assertTrue(0 <= row["vertex_index"] < len(template["vertices"]))


if __name__ == "__main__":
    unittest.main()
