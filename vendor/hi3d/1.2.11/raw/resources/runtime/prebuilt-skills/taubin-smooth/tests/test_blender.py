"""Behavioral tests; run with Blender execute.py and an explicit --scripts path."""
import argparse
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

import bmesh
import bpy
import numpy as np

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--scripts", required=True, type=Path)
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
sys.path.insert(0, str(args.scripts.resolve()))
from taubin_smooth import (  # noqa: E402
    main, mesh_positions, mesh_topology, run_asset, select_meshes, smooth_object,
    taubin_positions, validate_parameters,
)
from architecture_ir import select_purge
from pcg_handoff import bind_report, project_session, result_from_report, write_state
from pcg_yaml import load as load_yaml
from session_schema import new_session
from tool_result import validate_tool_result


def make_object(vertices, faces, name="Surface", edges=()):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, edges, faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def volume(mesh):
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        return abs(bm.calc_volume(signed=True))
    finally:
        bm.free()


class TaubinTests(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def triangle(self):
        return make_object([(0, 0, 0), (2, 0, 0), (0, 2, 0)], [(0, 1, 2)])

    def test_analytical_triangle_response(self):
        obj = self.triangle()
        original = mesh_positions(obj.data)
        centroid = original.mean(axis=0)
        # A three-vertex complete graph has nonconstant Laplacian frequency 3/2.
        for iterations in (1, 3):
            result, report = taubin_positions(obj.data, iterations=iterations)
            gain = ((1 - 1.5 * 0.5) * (1 + 1.5 * 0.53)) ** iterations
            np.testing.assert_allclose(result, centroid + gain * (original - centroid), atol=2e-7)
            self.assertEqual(report["iterations"], iterations)
            np.testing.assert_array_equal(mesh_positions(obj.data), original)

    def test_zero_iterations_and_fixed_vertices(self):
        obj = self.triangle()
        before = mesh_positions(obj.data)
        unchanged, _ = taubin_positions(obj.data, iterations=0)
        np.testing.assert_array_equal(unchanged, before)
        after, report = taubin_positions(obj.data, fixed_vertices=[0], iterations=3)
        np.testing.assert_array_equal(after[0], before[0])
        self.assertGreater(report["displacement_max_local"], 0)
        unchanged, _ = taubin_positions(obj.data, fixed_vertices=range(3))
        np.testing.assert_array_equal(unchanged, before)

    def test_pinned_open_boundary(self):
        obj = make_object([(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0), (0, 0, 2)],
                          [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)])
        before = mesh_positions(obj.data)
        after, report = taubin_positions(obj.data, iterations=1, pin_boundary=True)
        np.testing.assert_array_equal(after[:4], before[:4])
        self.assertAlmostEqual(float(after[4, 2]), 1.53, places=6)
        self.assertEqual(report["boundary_vertices"], 4)
        free, _ = taubin_positions(obj.data, iterations=1)
        self.assertFalse(np.array_equal(free[:4], before[:4]))

    def test_disconnected_isolated_and_nonmanifold(self):
        obj = make_object(
            [(0, 0, 0), (2, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1),
             (10, 0, 0), (12, 0, 0), (10, 2, 0), (99, 98, 97)],
            [(0, 1, 2), (1, 0, 3), (0, 1, 4), (5, 6, 7)],
        )
        before = mesh_positions(obj.data)
        after, report = taubin_positions(obj.data, iterations=2)
        self.assertEqual(report["nonmanifold_edges"], 1)
        self.assertEqual(report["isolated_vertices"], 1)
        np.testing.assert_array_equal(after[8], before[8])
        self.assertTrue(np.isfinite(after).all())
        single = make_object(before[5:8], [(0, 1, 2)], name="OnlySecondComponent")
        expected, _ = taubin_positions(single.data, iterations=2)
        np.testing.assert_allclose(after[5:8], expected, atol=1e-6)

    def test_loose_edges_and_degenerate_geometry(self):
        obj = make_object([(0, 0, 0), (1, 0, 0), (2, 0, 0), (10, 0, 0), (12, 0, 0)],
                          [(0, 1, 2)], edges=[(3, 4)])
        after, _ = taubin_positions(obj.data, iterations=1)
        self.assertTrue(np.isfinite(after).all())
        np.testing.assert_allclose(after[3:5, 0], [11, 11], atol=1e-6)

    def test_noisy_sphere_denoising_and_reduced_shrinkage(self):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, radius=1)
        obj = bpy.context.object
        coords = mesh_positions(obj.data)
        noise = np.random.default_rng(42).normal(0, 0.025, len(coords))
        coords *= (1 + noise[:, None])
        obj.data.vertices.foreach_set("co", coords.ravel())
        original_volume = volume(obj.data)
        result, _ = taubin_positions(obj.data, iterations=10)
        self.assertLess(np.std(np.linalg.norm(result, axis=1)), np.std(np.linalg.norm(coords, axis=1)) * 0.6)
        smooth_object(obj, iterations=10)
        taubin_error = abs(volume(obj.data) / original_volume - 1)
        laplacian = bmesh.new()
        try:
            laplacian.from_mesh(obj.data)
            for vertex, co in zip(laplacian.verts, coords):
                vertex.co = co
            for _ in range(10):
                bmesh.ops.smooth_vert(laplacian, verts=list(laplacian.verts), factor=0.5,
                                      use_axis_x=True, use_axis_y=True, use_axis_z=True)
            laplacian_error = abs(abs(laplacian.calc_volume(signed=True)) / original_volume - 1)
        finally:
            laplacian.free()
        self.assertLess(taubin_error, laplacian_error * 0.5)

    def test_topology_attributes_transform_and_shared_instance(self):
        obj = self.triangle()
        source = obj.data
        before = mesh_positions(source)
        topology = mesh_topology(source)
        uv = source.uv_layers.new(name="UVMap")
        uv.data[1].uv = (0.2, 0.7)
        uv_values = [tuple(item.uv) for item in uv.data]
        attr = source.attributes.new("marker", "INT", "POINT")
        attr.data[1].value = 42
        material = bpy.data.materials.new("SurfaceMaterial")
        source.materials.append(material)
        group = obj.vertex_groups.new(name="Weights")
        group.add([0, 2], 0.8, "REPLACE")
        sibling = bpy.data.objects.new("UntouchedInstance", source)
        bpy.context.scene.collection.objects.link(sibling)
        obj.location = (3, 4, 5)
        obj.scale = (2, 1, 0.5)
        modifier = obj.modifiers.new("Retained", "SMOOTH")
        modifier.factor = 0.1
        bpy.context.view_layer.update()
        transform = np.array(obj.matrix_world)
        smooth_object(obj, iterations=2)
        self.assertIs(sibling.data, source)
        self.assertIsNot(obj.data, source)
        np.testing.assert_array_equal(mesh_positions(source), before)
        self.assertEqual(mesh_topology(obj.data), topology)
        self.assertEqual([tuple(item.uv) for item in obj.data.uv_layers[0].data], uv_values)
        self.assertEqual(obj.data.attributes["marker"].data[1].value, 42)
        self.assertEqual(obj.data.materials[0], material)
        # Reacquire RNA handles after replacing the object's Mesh datablock.
        self.assertAlmostEqual(obj.vertex_groups["Weights"].weight(0), 0.8, places=6)
        np.testing.assert_array_equal(np.array(obj.matrix_world), transform)
        self.assertEqual(len(obj.modifiers), 1)

    def test_invalid_parameters_mesh_and_selection(self):
        obj = self.triangle()
        for parameters in [(-1, 0.5, -0.53), (True, 0.5, -0.53), (1.2, 0.5, -0.53),
                           (1, 0.5, 0.53), (1, 0.5, -0.4), (1, 0.9, -0.99),
                           (1, float("nan"), -0.53)]:
            with self.assertRaises(ValueError):
                validate_parameters(*parameters)
        for ids in [[-1], [3], [False], [0.5]]:
            with self.assertRaises(ValueError):
                taubin_positions(obj.data, fixed_vertices=ids)
        quad = make_object([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [(0, 1, 2, 3)], "Quad")
        with self.assertRaises(ValueError):
            taubin_positions(quad.data)
        with self.assertRaises(ValueError):
            select_meshes([obj, quad])
        self.assertEqual(select_meshes([obj, quad], object_names=[obj.name]), [obj])
        obj.shape_key_add(name="Basis")
        with self.assertRaises(ValueError):
            smooth_object(obj)
        obj.data.vertices[0].co.x = float("nan")
        with self.assertRaises(ValueError):
            taubin_positions(obj.data)

    def test_saved_readback_source_and_collision(self):
        obj = self.triangle()
        other = make_object([(5, 0, 0), (7, 0, 0), (5, 2, 0)], [(0, 1, 2)], "Other")
        other_before = mesh_positions(other.data)
        with tempfile.TemporaryDirectory(prefix="taubin-test-") as directory:
            root = Path(directory)
            source = root / "original.blend"
            bpy.ops.wm.save_as_mainfile(filepath=str(source))
            original_bytes = source.read_bytes()
            report = run_asset(source, root / "result", object_names=[obj.name], iterations=2)
            self.assertTrue(report["saved_mesh_readback"])
            self.assertEqual(source.read_bytes(), original_bytes)
            np.testing.assert_array_equal(mesh_positions(bpy.data.objects["Other"].data), other_before)
            saved = json.loads((root / "result/report.json").read_text())
            self.assertEqual(saved["source_sha256"], hashlib.sha256(original_bytes).hexdigest())
            output_before = (root / "result/smoothed.blend").read_bytes()
            with self.assertRaises(FileExistsError):
                run_asset(source, root / "result", all_meshes=True)
            self.assertEqual((root / "result/smoothed.blend").read_bytes(), output_before)
            with self.assertRaises(ValueError):
                run_asset(source, root, all_meshes=True)

    def test_obj_ply_glb_imports(self):
        with tempfile.TemporaryDirectory(prefix="taubin-formats-") as directory:
            root = Path(directory)
            obj_path = root / "input.obj"
            obj_path.write_text("v 0 0 0\nv 2 0 0\nv 0 2 0\nf 1 2 3\n")
            ply = root / "input.ply"
            ply.write_text("ply\nformat ascii 1.0\nelement vertex 3\nproperty float x\nproperty float y\nproperty float z\nelement face 1\nproperty list uchar int vertex_indices\nend_header\n0 0 0\n2 0 0\n0 2 0\n3 0 1 2\n")
            for path in (obj_path, ply):
                report = run_asset(path, root / path.suffix[1:], iterations=1)
                self.assertEqual(report["objects"][0]["triangles"], 1)
            glb = root / "input.glb"
            bpy.ops.export_scene.gltf(filepath=str(glb), export_format="GLB")
            self.assertTrue(run_asset(glb, root / "glb", iterations=1)["saved_mesh_readback"])

    def test_pcg_handoff_revisions_replay_rollback_and_missing(self):
        self.triangle()
        with tempfile.TemporaryDirectory(prefix="taubin-pcg-") as directory:
            root = Path(directory)
            source = root / "source.blend"
            bpy.ops.wm.save_as_mainfile(filepath=str(source))
            task = root / "task"
            session = new_session("taubin-smooth", task_id="pcg-test", checkpoint="input")
            write_state(session, task_root=task)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                main(["--input", str(source), "--output-dir", str(task / "v1"), "--iterations", "2"])
            result = json.loads(stdout.getvalue().strip().splitlines()[-1])
            validate_tool_result(result)
            self.assertEqual(result, json.loads((task / "v1/tool_result.json").read_text()))
            self.assertEqual(result["next_checkpoint"], "review")
            self.assertEqual(result["irreversible"], ["blender.write"])
            session = bind_report(session, task / "v1/report.json", task_root=task)
            self.assertEqual(session["status"], "running")  # Not a visual acceptance.
            board, view = write_state(session, task_root=task)
            smooth_stage = next(item for item in view["rail"] if item["id"] == "smooth")
            self.assertTrue(smooth_stage["confirm_required"])
            self.assertEqual(smooth_stage["irreversible"], ["blender.write"])
            self.assertEqual({item["status"] for item in board["catalog"]["artifacts"]}, {"ready"})
            self.assertEqual({item["retain"] for item in board["catalog"]["artifacts"]}, {"keep"})
            architecture = load_yaml((args.scripts.parent / "pcg/architecture.yaml").read_text())
            self.assertEqual(select_purge(architecture, session), [])
            session["status"] = "completed"
            session["route"] = "review_only"
            unchanged = bind_report(session, task / "v1/report.json", task_root=task)
            self.assertEqual(unchanged, session)
            write_state(session, task_root=task)
            # Simulate compact: use only the persisted session and the package.
            restored = json.loads((task / "session.json").read_text())
            for _ in range(2):
                write_state(restored, task_root=task)
            self.assertEqual(json.loads((task / "session.json").read_text()), session)
            restored.update(checkpoint="input", status="waiting_choice", route="main")
            _, view = write_state(restored, task_root=task)
            self.assertTrue(view["option_popup"]["visible"])
            self.assertEqual(len(view["option_popup"]["choices"]), 3)
            self.assertEqual(len(restored["artifacts"][0]["traces"]), 1)
            self.assertTrue((task / "v1/smoothed.blend").is_file())
            run_asset(source, task / "v2", iterations=3)
            revised = bind_report(restored, task / "v2/report.json", task_root=task)
            self.assertEqual(revised["checkpoint"], "review")
            for artifact in revised["artifacts"]:
                self.assertEqual([trace["op"] for trace in artifact["traces"]], ["add", "sync"])
                self.assertIn("v1", artifact["traces"][0]["path"])
                self.assertIn("v2", artifact["path"])
            write_state(revised, task_root=task)
            (task / "v2/smoothed.blend").unlink()
            missing, _ = project_session(revised, task_root=task)
            self.assertEqual(missing["catalog"]["artifacts"][0]["status"], "missing")
            self.assertEqual(len(revised["artifacts"][0]["traces"]), 2)
            with self.assertRaises(ValueError):
                bind_report(revised, task / "v2/report.json", task_root=task)

    def test_pcg_rejects_changed_files_and_unsafe_state(self):
        self.triangle()
        with tempfile.TemporaryDirectory(prefix="taubin-pcg-guards-") as directory:
            root = Path(directory)
            source = root / "source.blend"
            bpy.ops.wm.save_as_mainfile(filepath=str(source))
            task = root / "task"
            run_asset(source, task / "v1", iterations=1)
            report = task / "v1/report.json"
            session = new_session("taubin-smooth", task_id="guards", checkpoint="input")
            with self.assertRaises(ValueError):
                bind_report(session, report, task_root=root / "elsewhere")
            with self.assertRaises(ValueError):
                bind_report(new_session("other", task_id="guards"), report, task_root=task)
            with self.assertRaises(ValueError):
                write_state(session, task_root=args.scripts.parent)
            write_state(session, task_root=task)
            with self.assertRaises(ValueError):
                write_state(new_session("taubin-smooth", task_id="another"), task_root=task)
            (task / "board.json").unlink()
            (task / "board.json").symlink_to(source)
            source_bytes = source.read_bytes()
            with self.assertRaises(ValueError):
                write_state(session, task_root=task)
            self.assertEqual(source.read_bytes(), source_bytes)
            (task / "v1/smoothed.blend").write_bytes(b"changed")
            with self.assertRaises(ValueError):
                result_from_report(report)
            payload = json.loads(report.read_text())
            payload["saved_mesh_readback"] = False
            report.write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                result_from_report(report)

    def test_failed_cli_preserves_old_receipt_and_reports_no_success(self):
        self.triangle()
        with tempfile.TemporaryDirectory(prefix="taubin-pcg-failed-") as directory:
            root = Path(directory)
            source = root / "source.blend"
            bpy.ops.wm.save_as_mainfile(filepath=str(source))
            run_asset(source, root / "v1", iterations=1)
            receipt = root / "v1/tool_result.json"
            old = receipt.read_bytes()
            stdout = io.StringIO()
            with redirect_stdout(stdout), self.assertRaises(FileExistsError):
                main(["--input", str(source), "--output-dir", str(root / "v1")])
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["artifacts"], [])
            self.assertEqual(receipt.read_bytes(), old)
            scene = bpy.context.scene
            with self.assertRaises(ValueError):
                run_asset(source, root / "invalid", iterations=-1)
            self.assertIs(bpy.context.scene, scene)
            self.assertFalse((root / "invalid").exists())


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TaubinTests))
    if not result.wasSuccessful():
        raise RuntimeError("Taubin tests failed")
