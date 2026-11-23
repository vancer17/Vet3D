"""Surface and image-workflow boundaries; no credentials or network requests."""

import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
from surface import sample_surface, smooth_samples
from image_pipeline import generation_tick, bind_annotations, deliver
from fit import digest, read_inputs


class SurfaceTests(unittest.TestCase):
    def test_samples_follow_area_and_reconstruct_barycentric_positions(self):
        v = np.array(
            [[0.0, 0, 0], [1, 0, 0], [0, 1, 0], [2, 0, 0], [4, 0, 0], [2, 2, 0]]
        )
        q = np.array([[0, 1, 2], [3, 4, 5]])
        n = np.tile([0.0, 0, 1], (6, 1))
        a = sample_surface(v, q, n, 20000, 3)
        b = sample_surface(v, q, n, 20000, 3)
        for x, y in zip(a, b):
            np.testing.assert_array_equal(x, y)
        self.assertAlmostEqual(float((a[2] == 1).mean()), 0.8, delta=0.015)
        np.testing.assert_allclose(a[0], (v[q[a[2]]] * a[3][:, :, None]).sum(1))
        self.assertTrue((a[3] >= 0).all())
        np.testing.assert_allclose(a[3].sum(1), 1)

    def test_smoothing_preserves_planes_and_does_not_merge_opposite_sheets(self):
        grid = np.mgrid[-1:1:30j, -1:1:30j].reshape(2, -1).T
        p = np.r_[
            np.c_[grid, np.zeros(len(grid))], np.c_[grid, np.full(len(grid), 0.001)]
        ]
        n = np.r_[
            np.tile([0.0, 0, 1], (len(grid), 1)), np.tile([0.0, 0, -1], (len(grid), 1))
        ]
        out, on = smooth_samples(p, n, 0.03)
        np.testing.assert_allclose(out, p, atol=1e-12)
        np.testing.assert_allclose(on, n, atol=1e-12)


class PipelineTests(unittest.TestCase):
    def test_delivery_rejects_changed_uv_and_omits_disabled_optional_assets(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            registration = root / "registration"
            registration.mkdir()
            vertices = np.array([[0.0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]])
            arrays = dict(
                vertices=vertices, quads=[[0, 1, 2, 3]], quad_uvs=np.zeros((1, 4, 2))
            )
            template = root / "template.npz"
            np.savez(template, **arrays)
            np.savez(registration / "registered.npz", **arrays)
            (registration / "run_config.json").write_text(
                json.dumps(dict(target=str(template)))
            )
            for name in [
                "MetaHuman_Registered.obj",
                "MetaHuman_Review.glb",
                "MetaHuman_Review.blend",
                "overview.jpg",
                "summary.json",
                "MetaHuman_Review.dna",
                "expressions.jpg",
            ]:
                (registration / name).touch()
            (registration / "textures").mkdir()
            for name in ["Albedo", "Normal", "Eyes", "Albedo_Fused"]:
                (registration / "textures" / f"MetaHuman_{name}.png").touch()
            deliver(registration, root / "delivery", template)
            manifest = json.loads((root / "delivery/manifest.json").read_text())
            self.assertEqual(set(manifest["textures"]), {"albedo", "normal"})
            self.assertFalse(
                any(x["relative_path"].endswith(".dna") for x in manifest["files"])
            )
            arrays["quad_uvs"][:] = 0.5
            np.savez(registration / "registered.npz", **arrays)
            with self.assertRaisesRegex(ValueError, "topology/UV"):
                deliver(registration, root / "delivery", template)

    def test_pending_then_download_uses_original_job_and_requested_profile(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            script = root / "explicit-tool.py"
            script.touch()
            model = root / "high.glb"
            model.write_bytes(b"fake artifact")
            config = dict(image=str(root / "input.png"), hi3d_api_script=str(script))
            calls = []
            completed = False

            def fake(command):
                calls.append(command)
                if "--dry-run" in command:
                    return {"dry_run": True}
                if "submit" in command:
                    return {"job": {"task_id": "task.with.dots", "state": "submitted"}}
                if "wait" in command:
                    return {"result": "success" if completed else "pending"}
                if "download" in command:
                    return {"artifact": {"files": [{"path": str(model)}]}}
                self.fail("unexpected operation")

            self.assertEqual(
                generation_tick(config, root, fake)["status"], "waiting_generation"
            )
            self.assertFalse(any("download" in cmd for cmd in calls))
            completed = True
            result = generation_tick(config, root, fake)
            self.assertEqual(result["high_glb"], str(model.resolve()))
            submissions = [
                cmd for cmd in calls if "submit" in cmd and "--dry-run" not in cmd
            ]
            self.assertEqual(submissions[0], submissions[1])
            for field in [
                "resolution=2048quality",
                "face=5000000",
                "request_type=3",
                "format=2",
            ]:
                self.assertIn(field, submissions[0])

    def test_annotations_map_polygon_masks_and_reject_stale_asset(self):
        with tempfile.TemporaryDirectory() as folder:
            r = Path(folder)
            source = r / "high.glb"
            source.write_bytes(b"high")
            template = r / "template.npz"
            template.write_bytes(b"template")
            target = r / "surface.npz"
            np.savez(target, source_polygon_indices=np.arange(200))
            annotation = r / "annotation.json"
            output = r / "settings.json"
            data = dict(
                source_sha256=digest(source),
                template_sha256=digest(template),
                coordinate_space="blender_world_z_up",
                settings={},
                source_exclude_polygon_indices=[0, 5, 9],
            )
            annotation.write_text(json.dumps(data))
            bind_annotations(annotation, source, template, target, output)
            result = json.loads(output.read_text())
            self.assertEqual(len(result["target_fit_indices"]), 197)
            self.assertNotIn(5, result["target_fit_indices"])
            with self.assertRaisesRegex(ValueError, "source object"):
                bind_annotations(
                    annotation,
                    source,
                    template,
                    target,
                    output,
                    source_object="Different skin",
                )
            with self.assertRaisesRegex(ValueError, "polygon"):
                bind_annotations(
                    annotation, source, template, target, output, polygon_count=5
                )
            data["settings"]["target_fit_indices"] = [0]
            annotation.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "stale"):
                bind_annotations(annotation, source, template, target, output)
            source.write_bytes(b"different asset")
            with self.assertRaisesRegex(ValueError, "hashes"):
                bind_annotations(annotation, source, template, target, output)

    def test_oriented_target_accepts_no_quads_but_rejects_invalid_data(self):
        with tempfile.TemporaryDirectory() as folder:
            r = Path(folder)
            v = np.array([[0.0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]])
            np.savez(
                r / "template.npz",
                vertices=v,
                quads=[[0, 1, 2, 3]],
                quad_uvs=np.zeros((1, 4, 2)),
            )
            config = dict(
                template=r / "template.npz",
                target=r / "target.npz",
                settings=r / "settings.json",
                hair_state="bald",
                target_parts="skin",
            )
            for vertices, normals, valid in [
                (v, np.tile([0.0, 0, 1], (4, 1)), True),
                (v, np.zeros((4, 3)), False),
                (v + np.nan, np.tile([0.0, 0, 1], (4, 1)), False),
            ]:
                np.savez(config["target"], vertices=vertices, normals=normals)
                settings = dict(
                    template_sha256=digest(config["template"]),
                    target_sha256=digest(config["target"]),
                    landmarks=[
                        dict(vertex_index=i, target=p.tolist()) for i, p in enumerate(v)
                    ],
                    fit_indices=[0, 1, 2, 3],
                )
                config["settings"].write_text(json.dumps(settings))
                if valid:
                    read_inputs(config)
                else:
                    with self.assertRaises(ValueError):
                        read_inputs(config)


if __name__ == "__main__":
    unittest.main()
