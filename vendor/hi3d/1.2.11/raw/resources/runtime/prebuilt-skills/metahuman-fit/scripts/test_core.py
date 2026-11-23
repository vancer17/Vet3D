"""Meaningful geometry and resume invariants; run with the fitting Python."""

import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from scipy.spatial.transform import Rotation
from brush import similarity, gaussian_brush, landmark_weights
from transport import local_jacobians, joint_world, joint_local
from fit import read_inputs, digest
from run import Journal, signature


class SharedCodeCacheTests(unittest.TestCase):
    def test_sheet_and_glb_sources_invalidate_only_their_adapters(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            names = ['contact_sheet.py', 'image_sheet.py', 'preview_export.py',
                     'glb_clips.py', 'fit.py', 'texture_bake.py']
            for name in names: (root/name).write_text('fixture')
            stages = {'overview': [root/'contact_sheet.py'],
                      'expression_review': [root/'contact_sheet.py'],
                      'review': [root/'preview_export.py'],
                      'fit': [root/'fit.py'], 'bake': [root/'texture_bake.py']}
            def hashes(): return {name: signature({}, files) for name, files in stages.items()}
            before = hashes()
            (root/'image_sheet.py').write_text('changed sheet')
            sheet = hashes()
            self.assertEqual({n for n in stages if before[n] != sheet[n]},
                             {'overview', 'expression_review'})
            (root/'glb_clips.py').write_text('changed container reader')
            glb = hashes()
            self.assertEqual({n for n in stages if sheet[n] != glb[n]}, {'review'})

    def test_preview_change_preserves_io_only_signature(self):
        import run
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ['review.py', 'render_expressions.py', 'head_preview.py',
                         'preview_scene.py', 'material_nodes.py', 'scene_io.py', 'blender_io.py', 'render_engine.py']:
                (root/name).write_text('fixture')
            with patch.object(run, 'SCRIPTS', root):
                paths = [[root/'review.py'], [root/'render_expressions.py'], [root/'blender_io.py']]
                before = [signature({}, p) for p in paths]
                (root/'render_engine.py').write_text('changed render compatibility')
                after = [signature({}, p) for p in paths]
                self.assertNotEqual(before[0], after[0])
                self.assertNotEqual(before[1], after[1])
                self.assertEqual(before[2], after[2])

    def test_triangle_change_invalidates_geometry_signature(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);collision=root/'collision.py';triangle=root/'triangle_arrays.py';unrelated=root/'other.py'
            collision.write_text('same collision adapter');triangle.write_text('first core');unrelated.write_text('same unrelated stage')
            geometry=signature({},[collision]);other=signature({},[unrelated])
            triangle.write_text('changed core')
            self.assertNotEqual(geometry,signature({},[collision]))
            self.assertEqual(other,signature({},[unrelated]))


class GeometryTests(unittest.TestCase):
    def test_dense_landmark_sampling_does_not_change_group_pull(self):
        sparse = [{"group": "eye", "weight": 1}, {"group": "lip", "weight": 1}]
        dense = [sparse[0]] * 18 + [sparse[1]] * 32
        w = landmark_weights(dense, {"eye": 6, "lip": 6})
        np.testing.assert_allclose(
            [w[:18].sum(), w[18:].sum()], landmark_weights(sparse, {"eye": 6, "lip": 6})
        )
        np.testing.assert_array_equal(landmark_weights(sparse), [1, 1])
        with self.assertRaisesRegex(ValueError, "budget"):
            landmark_weights(dense, {"eye": 6})

    def test_similarity_recovers_orientation_scale_and_translation(self):
        rng = np.random.default_rng(4)
        source = rng.normal(size=(12, 3))
        linear = 2.3 * Rotation.from_euler("xyz", [0.2, -0.5, 0.7]).as_matrix()
        offset = np.array([3.0, -2.0, 1.0])
        got, shift = similarity(source, source @ linear.T + offset)
        np.testing.assert_allclose(got, linear, atol=1e-10)
        np.testing.assert_allclose(shift, offset, atol=1e-10)
        self.assertGreater(np.linalg.det(got), 0)

    def test_brush_preserves_constant_velocity_on_thin_sheets(self):
        grid = np.mgrid[-1:1:8j, -1:1:8j].reshape(2, -1).T
        points = np.r_[
            np.c_[grid, np.zeros(len(grid))], np.c_[grid, np.ones(len(grid)) * 0.001]
        ]
        weights = gaussian_brush(points, 0.4)
        velocity = weights @ np.tile([0.12, -0.3, 0.04], (weights.shape[1], 1))
        np.testing.assert_allclose(
            velocity, np.tile([0.12, -0.3, 0.04], (len(points), 1)), atol=1e-12
        )
        np.testing.assert_allclose(velocity[:64], velocity[64:], atol=1e-12)

    def test_jacobian_transports_rotated_tangent_and_normal(self):
        rest = np.array([[0.0, 0, 0], [1.0, 0, 0], [1.0, 1, 0], [0.0, 1, 0]])
        rotation = Rotation.from_euler("xyz", [0.4, 0.1, -0.6]).as_matrix()
        jac = local_jacobians(rest, rest @ rotation.T + 2, np.array([[0, 1, 2, 3]]))
        np.testing.assert_allclose(jac, np.tile(rotation, (4, 1, 1)), atol=3e-6)

    def test_joint_hierarchy_roundtrip(self):
        trans = np.array([[0.0, 1, 0], [2.0, 0, 0], [0.0, 0, 3]])
        rot = np.array([[20.0, 30, 40], [0.0, 90, 0], [0.0, 0, 45]])
        parent = np.array([0, 0, 1])
        world, matrix = joint_world(trans, rot, parent)
        np.testing.assert_allclose(
            joint_local(world, matrix, parent), trans, atol=1e-10
        )

    def test_preflight_binds_annotations_and_rejects_hair(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            v = np.array([[0.0, 0, 0], [1.0, 0, 0], [1.0, 1, 0], [0.0, 1, 0]])
            np.savez(
                root / "template.npz",
                vertices=v,
                quads=[[0, 1, 2, 3]],
                quad_uvs=np.zeros((1, 4, 2)),
            )
            np.savez(root / "target.npz", vertices=v, quads=[[0, 1, 2, 3]])
            settings = dict(
                template_sha256=digest(root / "template.npz"),
                target_sha256=digest(root / "target.npz"),
                landmarks=[
                    dict(vertex_index=i, target=p.tolist()) for i, p in enumerate(v)
                ],
                fit_indices=[0, 1, 2, 3],
            )
            (root / "settings.json").write_text(json.dumps(settings))
            config = dict(
                template=root / "template.npz",
                target=root / "target.npz",
                settings=root / "settings.json",
                hair_state="bald",
                target_parts="skin",
            )
            read_inputs(config)
            with self.assertRaisesRegex(ValueError, "bald"):
                read_inputs(dict(config, hair_state="hair"))
            np.savez(root / "target.npz", vertices=v + 1, quads=[[0, 1, 2, 3]])
            with self.assertRaisesRegex(ValueError, "hash"):
                read_inputs(config)


class ResumeTests(unittest.TestCase):
    def test_cache_detects_artifact_corruption_and_records_failures(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            output = root / "artifact.txt"
            calls = []

            def action():
                calls.append(1)
                output.write_text("correct")

            journal = Journal(root)
            journal.stage("fit", "same", [output], action)
            retry = Journal(root)
            retry.stage("fit", "same", [output], action)
            self.assertEqual(len(calls), 1)
            self.assertEqual(retry.records[-1]["status"], "skipped")
            output.write_text("corrupt")
            retry.stage("fit", "same", [output], action)
            self.assertEqual(len(calls), 2)

            def fail():
                raise ValueError("intentional")

            with self.assertRaises(ValueError):
                retry.stage("review", "changed", [], fail)
            events = [
                json.loads(x) for x in (root / "timings.jsonl").read_text().splitlines()
            ]
            self.assertEqual(events[-1]["status"], "failed")
            self.assertGreaterEqual(events[-1]["seconds"], 0)
            self.assertEqual(journal.state["task_id"], retry.state["task_id"])

    def test_orphan_start_is_recovered_without_fabricated_time(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            journal = Journal(root)
            journal.append(
                dict(
                    task_id=journal.state["task_id"],
                    attempt_id="previous",
                    stage="fit",
                    status="running",
                    started_at="2026-01-01T00:00:00+00:00",
                )
            )
            Journal(root)
            event = json.loads((root / "timings.jsonl").read_text().splitlines()[-1])
            self.assertEqual(event["status"], "interrupted")
            self.assertIsNone(event["seconds"])


if __name__ == "__main__":
    unittest.main()
