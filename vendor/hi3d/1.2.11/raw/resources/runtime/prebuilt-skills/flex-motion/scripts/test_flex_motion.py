"""Behavior tests for the flexible-part spring and weight blend."""

from __future__ import annotations

import unittest

import numpy as np

from flex_motion import (
    SpringParams,
    blend_auxiliary,
    limit_flexible_rows,
    project_length,
    push_capsules,
    restore_rows,
    should_reset,
    step_tip,
)


def _angle(vector):
    return float(np.arctan2(vector[0], -vector[1]))


def _yaw(rest, angle):
    c, s = float(np.cos(angle)), float(np.sin(angle))
    return np.array([c * rest[0] - s * rest[1], s * rest[0] + c * rest[1], rest[2]])


class FlexMotionTests(unittest.TestCase):
    def test_rest_without_gravity_stays_put(self):
        rest = np.array([0.0, -0.4, 0.0])
        params = SpringParams(gravity_scale=0.0)
        tip, velocity, report = step_tip(rest, np.zeros(3), rest, np.zeros(3), 0.4, 1 / 60, params)
        self.assertLess(np.linalg.norm(tip - rest), 1e-8)
        self.assertLess(np.linalg.norm(velocity), 1e-6)
        self.assertGreater(report["substeps"], 0)
        self.assertAlmostEqual(np.linalg.norm(tip), 0.4, places=6)

    def test_zero_dt_and_reset(self):
        rest = np.array([0.0, -0.4, 0.0])
        tip, velocity, report = step_tip(rest, np.array([1.0, 0.0, 0.0]), rest, np.zeros(3), 0.4, 0.0, SpringParams())
        np.testing.assert_allclose(tip, rest)
        np.testing.assert_allclose(velocity, [1.0, 0.0, 0.0])
        self.assertEqual(report["substeps"], 0)
        self.assertFalse(should_reset(np.zeros(3), np.array([0.01, 0.0, 0.0]), 0.05))
        self.assertTrue(should_reset(np.zeros(3), np.array([0.2, 0.0, 0.0]), 0.05))

    def test_fast_turn_lags_then_settles_across_frame_rates(self):
        rest = np.array([0.0, -0.4, 0.0])
        params = SpringParams(gravity_scale=0.0)

        def run(dt):
            tip = rest.copy()
            velocity = np.zeros(3)
            lag = 0.0
            t = 0.0
            while t < 1.5 - 1e-12:
                angle = (np.pi / 2) * min(1.0, t / 0.35)
                target = _yaw(rest, angle)
                tip, velocity, _ = step_tip(tip, velocity, target, np.zeros(3), 0.4, dt, params)
                if t < 0.12:
                    lag = max(lag, angle - _angle(tip))
                t += dt
            return tip, lag

        tip30, lag30 = run(1 / 30)
        tip60, lag60 = run(1 / 60)
        self.assertGreater(lag30, np.deg2rad(3))
        self.assertGreater(lag60, np.deg2rad(3))
        self.assertLess(abs(_angle(tip30) - _angle(tip60)), np.deg2rad(8))
        self.assertLess(abs(_angle(tip60) - np.pi / 2), np.deg2rad(8))

    def test_stop_decays_and_length_holds(self):
        rest = np.array([0.0, -0.4, 0.0])
        held = _yaw(rest, np.deg2rad(40))
        tip = rest.copy()
        velocity = np.zeros(3)
        params = SpringParams(gravity_scale=0.0)
        for _ in range(8):
            tip, velocity, _ = step_tip(tip, velocity, held, np.zeros(3), 0.4, 1 / 60, params)
        early = abs(_angle(held) - _angle(tip))
        for _ in range(90):
            tip, velocity, _ = step_tip(tip, velocity, held, np.zeros(3), 0.4, 1 / 60, params)
        self.assertLess(abs(_angle(held) - _angle(tip)), early)
        self.assertAlmostEqual(np.linalg.norm(tip), 0.4, places=6)

    def test_gravity_sags_without_leaving_the_sphere(self):
        rest = np.array([0.0, -0.4, 0.0])
        tip = rest.copy()
        velocity = np.zeros(3)
        for _ in range(180):
            tip, velocity, _ = step_tip(tip, velocity, rest, np.zeros(3), 0.4, 1 / 60, SpringParams())
        drop = rest[2] - tip[2]
        self.assertGreater(drop, 0.005)
        self.assertLess(drop, 0.25)
        self.assertAlmostEqual(np.linalg.norm(tip - np.zeros(3)), 0.4, places=5)

    def test_capsule_pushes_and_axis_hit_is_reported(self):
        moved, misses = push_capsules(
            np.array([0.02, 0.0, 0.0]),
            [{"start": [0.0, -0.2, 0.0], "end": [0.0, 0.2, 0.0], "radius": 0.05}],
        )
        self.assertEqual(misses, 0)
        self.assertAlmostEqual(np.linalg.norm(moved[:1]), 0.05, places=6)
        outside, _ = push_capsules(
            np.array([0.2, 0.0, 0.0]),
            [{"start": [0.0, -0.2, 0.0], "end": [0.0, 0.2, 0.0], "radius": 0.05}],
        )
        np.testing.assert_allclose(outside, [0.2, 0.0, 0.0])
        _, degenerate = push_capsules(
            np.zeros(3),
            [{"start": [0.0, -0.2, 0.0], "end": [0.0, 0.2, 0.0], "radius": 0.05}],
        )
        self.assertEqual(degenerate, 1)
        projected = project_length(np.zeros(3), np.array([0.2, 0.1, 0.0]), 0.4)
        self.assertAlmostEqual(np.linalg.norm(projected), 0.4, places=6)

    def test_weight_blend_protects_and_limits_only_flexible_rows(self):
        base = np.array([[1.0, 0.0], [0.7, 0.3], [0.2, 0.8]], dtype=float)
        auxiliary = np.array([[1.0, 0.0, 0.0], [0.2, 0.5, 0.3], [0.1, 0.2, 0.7]], dtype=float)
        mask = np.array([0.0, 0.4, 1.0])
        blended = blend_auxiliary(base, mask, auxiliary)
        np.testing.assert_allclose(blended[0, :2], base[0])
        np.testing.assert_allclose(blended[0, 2:], 0)
        self.assertAlmostEqual(blended[1, :2].sum(), 0.6, places=6)
        np.testing.assert_allclose(blended[2, :2], 0)
        limited = limit_flexible_rows(blended, mask, 2)
        np.testing.assert_array_equal(limited[0], blended[0])
        self.assertEqual(np.count_nonzero(limited[2] > 1e-8), 2)
        self.assertAlmostEqual(limited[2].sum(), 1.0, places=6)
        restored = restore_rows(blended, np.pad(base, ((0, 0), (0, 3))), np.array([True, False, False]))
        np.testing.assert_allclose(restored[0], np.pad(base[0], (0, 3)))
        np.testing.assert_allclose(restored[1], blended[1])

    def test_bad_inputs_fail(self):
        with self.assertRaises(ValueError):
            step_tip(np.zeros(3), np.zeros(3), np.zeros(3), np.zeros(3), 0.0, 0.1, SpringParams())
        with self.assertRaises(ValueError):
            blend_auxiliary(np.ones((1, 1)), np.array([1.5]), np.ones((1, 1)))


if __name__ == "__main__":
    unittest.main()
