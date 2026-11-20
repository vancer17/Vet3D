"""Template ear geometry, eye parameter locality and cache partition invariants."""

import unittest
import numpy as np
from scipy.spatial.transform import Rotation
from ears import restore_ears
from eyes import adjust_eye
from run import brush_settings
from expression_smoke import world_matrices, skin_points
from skin_tone import template_color_mask


class PartsTests(unittest.TestCase):
    def test_quaternion_hierarchy_and_weighted_skinning(self):
        neutral = np.zeros((2, 10))
        neutral[:, 6] = 1
        neutral[:, 7:] = 1
        neutral[0, 3:7] = Rotation.from_euler("z", 90, degrees=True).as_quat()
        neutral[1, 0] = 1
        delta = np.zeros_like(neutral)
        delta[:, 6] = 1
        world = world_matrices(neutral, delta, [0, 0])
        np.testing.assert_allclose(world[1, :3, 3], [0, 1, 0], atol=1e-12)
        transforms = np.tile(np.eye(4), (2, 1, 1))
        transforms[1, 0, 3] = 2
        result = skin_points(
            np.array([[1.0, 2.0, 3.0]]),
            transforms,
            np.array([[0, 1]]),
            np.array([[0.25, 0.75]]),
        )
        np.testing.assert_allclose(result, [[2.5, 2, 3]])
        with self.assertRaises(ValueError):
            skin_points(np.ones((1, 3)), transforms, np.array([[0]]), np.array([[0.5]]))

    def test_oral_mask_uses_native_uv_and_preserves_other_islands(self):
        data = dict(
            vertices=np.zeros((8, 3)),
            quads=np.arange(8).reshape(2, 4),
            quad_uvs=np.array(
                [
                    [[0.1, 0.7], [0.3, 0.7], [0.3, 0.9], [0.1, 0.9]],
                    [[0.6, 0.1], [0.8, 0.1], [0.8, 0.3], [0.6, 0.3]],
                ]
            ),
        )
        mask = template_color_mask(data, [0, 1, 2, 3], (100, 100))
        self.assertEqual(mask[20, 20], 255)
        self.assertEqual(mask[80, 70], 0)
        self.assertEqual(mask[80, 20], 0)

    def test_ear_core_is_rigid_and_other_face_vertices_are_unchanged(self):
        rest = np.array(
            [[x, y, 0.05 * x * y] for y in range(7) for x in range(7)], float
        )
        q = np.array(
            [
                [y * 7 + x, y * 7 + x + 1, (y + 1) * 7 + x + 1, (y + 1) * 7 + x]
                for y in range(6)
                for x in range(6)
            ]
        )
        rot = Rotation.from_euler("z", 0.1).as_matrix()
        ideal = rest @ rot.T + [0.1, 0.2, 0.3]
        core = np.array([16, 17, 18, 23, 24, 25, 30, 31, 32])
        band = np.setdiff1d([y * 7 + x for y in range(1, 6) for x in range(1, 6)], core)
        anchors = np.setdiff1d(np.arange(49), np.r_[core, band])
        fitted = ideal.copy()
        fitted[core, 2] += 0.1
        result, report = restore_ears(
            rest,
            fitted,
            q,
            [dict(core_indices=core, blend_indices=band, anchor_indices=anchors)],
            0.2,
        )
        np.testing.assert_allclose(result[core], ideal[core], atol=1e-12)
        np.testing.assert_array_equal(result[anchors], fitted[anchors])
        self.assertEqual(report[0]["rigid_core_error"], 0)

    def test_eye_controls_keep_sclera_and_grow_the_pupil(self):
        n = 256
        yy, xx = np.mgrid[:n, :n]
        r = np.hypot((xx + 0.5) / n - 0.5, (yy + 0.5) / n - 0.5)
        im = np.full((n, n, 3), 220, np.uint8)
        im[r < 0.25] = [100, 60, 30]
        im[r < 0.08] = [3, 3, 3]
        result = adjust_eye(im, [0.5, 0.5], 0.25, 0.08, 1.5, [0.1, 0.3, 0.5])
        np.testing.assert_array_equal(result[r >= 0.25], im[r >= 0.25])
        self.assertLess(result[128, 154].mean(), 10)
        self.assertGreater(result[128, 174, 2], result[128, 174, 0] * 2)
        with self.assertRaises(ValueError):
            adjust_eye(im, [0.5, 0.5], 0.25, 0.15, 2)

    def test_local_refinement_settings_do_not_invalidate_brush_registration(self):
        settings = dict(
            fit_indices=[0, 1],
            target_fit_indices=[0, 1, 2],
            landmarks=[dict(vertex_index=0, target=[0, 0, 0])],
        )
        revised = dict(
            settings,
            neck_fairing_indices=[3],
            identity_protected_indices=[0, 1],
            ear_regions=[{}],
            bake_indices=[0],
        )
        self.assertEqual(brush_settings(settings), brush_settings(revised))
        revised["target_fit_indices"] = [0, 1]
        self.assertNotEqual(brush_settings(settings), brush_settings(revised))


if __name__ == "__main__":
    unittest.main()
