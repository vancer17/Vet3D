"""Offline CLI and orchestration checks; no bpy, geometry build or 3D files."""

from contextlib import ExitStack, contextmanager
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


SKILL = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("parts_pipeline_test", SKILL / "scripts" / "parts_pipeline.py")
pipeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pipeline)


class Object:
    def __init__(self, name, parent=None):
        self.name, self.parent = name, parent


class Collection(dict):
    def __init__(self, part_id, objects):
        super().__init__(part_id=part_id)
        self.all_objects = list(objects)


class Window:
    def __init__(self, scene):
        self.scene = scene

    @property
    def scene(self):
        return self._scene

    @scene.setter
    def scene(self, scene):
        self._scene = scene
        self.view_layer = scene.view_layer


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.task = self.root / "task"
        self.task.mkdir()
        self.job_path = self.task / "job.json"
        self.model_path = self.task / "model.py"
        # Parsing is allowed; importing this module would prove an unsafe check.
        self.model_path.write_text("raise RuntimeError('A check must never execute this module')\n")
        self.job = dict(
            name="mock-parts", modules=["model.py"],
            parts=[{"id": "left", "label": "Left"}, {"id": "right", "label": "Right"}],
            palette={"main": "#445566"}, output_dir="results",
            exports={"parts": True, "whole": True},
        )
        self.job_path.write_text(json.dumps(self.job))

    @staticmethod
    def snapshot(path):
        return {str(p.relative_to(path)): p.read_bytes() for p in path.rglob("*") if p.is_file()}

    def cli(self, script, *arguments):
        # This guard also detects a bpy import if the environment happens to
        # provide bpy. runpy executes the real CLI, in a fresh ordinary Python.
        bootstrap = """import importlib.abc, runpy, sys
class RejectBlender(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {'bpy', 'mathutils'}:
            raise AssertionError('Blender import attempted in a read-only CLI command')
sys.meta_path.insert(0, RejectBlender())
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name='__main__')
"""
        return subprocess.run(
            [sys.executable, "-B", "-c", bootstrap, str(script), *map(str, arguments)],
            cwd=self.root, capture_output=True, text=True, check=False,
        )

    def test_copied_skill_supports_positional_named_and_legacy_checks_without_writes(self):
        installed = self.root / "standalone-skill"
        shutil.copytree(SKILL, installed)
        before = self.snapshot(self.root)
        cases = [
            ("run.py", [self.job_path, "--check"]),
            ("run.py", ["--job", self.job_path, "--check"]),
            ("parts_pipeline.py", ["--job", self.job_path, "--check"]),
        ]
        for script, arguments in cases:
            with self.subTest(script=script, arguments=arguments):
                result = self.cli(installed / "scripts" / script, *arguments)
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual(report["status"], "config_valid")
                self.assertFalse(report["blender_run"])
                self.assertEqual(report["job"]["modules"], [str(self.model_path)])
                self.assertEqual(report["job"]["output_dir"], str(self.task / "results"))
        self.assertEqual(self.snapshot(self.root), before)

    def test_describe_needs_no_job_and_conflicting_config_arguments_fail(self):
        before = self.snapshot(self.root)
        result = self.cli(SKILL / "scripts" / "run.py", "--describe")
        self.assertEqual(result.returncode, 0, result.stderr)
        interface = json.loads(result.stdout)
        self.assertEqual(interface["skill"], "multiview-parts")
        self.assertIn("run_job", {item["name"] for item in interface["functions"]})
        self.assertEqual(interface["entrypoint"], "scripts/run.py")
        conflict = self.cli(SKILL / "scripts" / "run.py", self.job_path, "--job", self.job_path, "--check")
        self.assertNotEqual(conflict.returncode, 0)
        self.assertEqual(self.snapshot(self.root), before)

    def test_invalid_configuration_fails_as_json_without_creating_a_run(self):
        self.job["axis"] = "Z"
        self.job_path.write_text(json.dumps(self.job))
        result = self.cli(SKILL / "scripts" / "run.py", self.job_path, "--check")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["execution_status"], "failed")
        self.assertFalse((self.task / "results").exists())

    def test_part_ownership_checks_observable_relationships_without_bpy(self):
        parent = Object("left-root")
        child = Object("left-child", parent)
        other = Object("right")
        left, right = Collection("left", [parent, child]), Collection("right", [other])
        scene = SimpleNamespace(objects=[parent, child, other])
        self.assertEqual(pipeline.validate_part_ownership(scene, [left, right], ["right", "left"]), {"left": left, "right": right})
        with self.assertRaises(ValueError):
            pipeline.validate_part_ownership(scene, [left, right], ["left"])
        with self.assertRaises(ValueError):
            pipeline.validate_part_ownership(scene, [left, Collection("left", [other])], ["left", "right"])
        with self.assertRaises(ValueError):
            pipeline.validate_part_ownership(scene, [left, Collection("right", [other, child])], ["left", "right"])
        child.parent = other
        with self.assertRaises(ValueError):
            pipeline.validate_part_ownership(scene, [left, right], ["left", "right"])
        child.parent = parent
        scene.objects.append(Object("undeclared"))
        with self.assertRaises(ValueError):
            pipeline.validate_part_ownership(scene, [left, right], ["left", "right"])

    @contextmanager
    def mocked_runtime(self, build_error=None, export_error=None, journal_error_stage=None):
        original_scene = SimpleNamespace(objects=[], view_layer=object())
        window = Window(original_scene)
        task_scene = SimpleNamespace(objects=[], view_layer=object())
        bpy = SimpleNamespace(
            context=SimpleNamespace(window=window, mode="OBJECT"),
            data=SimpleNamespace(scenes=SimpleNamespace(new=Mock(return_value=task_scene))),
            app=SimpleNamespace(version_string="mock-only"),
        )
        real_import = pipeline.import_file
        imports = []

        def build(ctx):
            for part in self.job["parts"]:
                obj = Object(part["id"])
                ctx.parts.append(Collection(part["id"], [obj]))
                ctx.scene.objects.append(obj)
            if build_error is not None:
                raise build_error

        def import_adapter(path):
            path = Path(path)
            imports.append(path.name)
            if path.name == "timing.py":
                module = real_import(path)
                if journal_error_stage is not None:
                    append = module._append_event

                    def append_adapter(directory, event):
                        if event["stage"] == journal_error_stage:
                            raise OSError("Simulated timing journal failure")
                        return append(directory, event)

                    module._append_event = append_adapter
                return module
            if path.name == "geometry.py":
                return SimpleNamespace(Context=lambda scene, palette: SimpleNamespace(scene=scene, parts=[]))
            if path == self.model_path:
                return SimpleNamespace(build=build)
            raise AssertionError("Unexpected module import: " + str(path))

        def artifact(path):
            return {"path": str(path), "bytes": 0, "status": "mock_only_no_file"}

        def exports(bpy_arg, directory, parts, entries):
            yield artifact(Path(directory) / (parts[0]["id"] + ".glb"))
            if export_error is not None:
                raise export_error
            for part in parts[1:]:
                yield artifact(Path(directory) / (part["id"] + ".glb"))

        with ExitStack() as stack:
            stack.enter_context(patch.dict(sys.modules, {"bpy": bpy}))
            stack.enter_context(patch.object(pipeline, "import_file", side_effect=import_adapter))
            stack.enter_context(patch.object(pipeline, "create_part_roots", side_effect=lambda b, c, parts: [(c[p["id"]], Object(p["id"])) for p in parts]))
            layout = stack.enter_context(patch.object(pipeline, "apply_layout", return_value=[{"id": p["id"], "mock_only": True} for p in self.job["parts"]]))
            save = stack.enter_context(patch.object(pipeline, "save_scene", side_effect=lambda b, s, path: artifact(path)))
            part_export = stack.enter_context(patch.object(pipeline, "export_part_files", side_effect=exports))
            row_export = stack.enter_context(patch.object(pipeline, "export_glb", side_effect=lambda b, path, entries: artifact(path)))
            yield SimpleNamespace(bpy=bpy, window=window, original_scene=original_scene, task_scene=task_scene,
                                  imports=imports, save=save, layout=layout, part_export=part_export, row_export=row_export)

    def stored_report(self):
        paths = list((self.task / "results").glob("*/report.json"))
        self.assertEqual(len(paths), 1)
        return json.loads(paths[0].read_text())

    def assert_restored(self, runtime):
        self.assertIs(runtime.window.scene, runtime.original_scene)
        self.assertIs(runtime.window.view_layer, runtime.original_scene.view_layer)
        self.assertEqual(list(self.task.rglob("*.blend")), [])
        self.assertEqual(list(self.task.rglob("*.glb")), [])

    def test_preview_skips_requested_exports_and_restores_user_context(self):
        with self.mocked_runtime() as runtime:
            report = pipeline.run_job(self.job_path, "preview", task_id="task", previous_attempt_id="prior")
            self.assert_restored(runtime)
            runtime.save.assert_called_once()
            runtime.part_export.assert_not_called()
            runtime.row_export.assert_not_called()
        self.assertEqual(report, self.stored_report())
        self.assertEqual(report["status"], "preview_ready")
        self.assertEqual(report["execution_status"], "completed")
        self.assertEqual(report["exports"]["status"], "skipped")
        self.assertEqual(report["checks"]["visual"], "not_performed")
        phases = {r["stage"]: r for r in report["timing"]["stages"]}
        for name in ("export_parts", "export_row"):
            self.assertEqual(phases[name]["status"], "skipped")
            self.assertIsNone(phases[name]["elapsed_seconds"])
        self.assertEqual(phases["restore_context"]["status"], "completed")
        self.assertEqual(report["timing"]["previous_attempt_id"], "prior")

    def test_build_failure_retains_report_and_skips_every_downstream_stage(self):
        with self.mocked_runtime(build_error=ValueError("Synthetic module failure")) as runtime:
            report = pipeline.run_job(self.job_path, "deliver")
            self.assert_restored(runtime)
            runtime.layout.assert_not_called()
            runtime.save.assert_not_called()
        self.assertEqual(report, self.stored_report())
        self.assertEqual(report["execution_status"], "failed")
        self.assertEqual(report["modules"][0]["status"], "failed")
        self.assertEqual(report["exports"]["status"], "skipped")
        phases = {r["stage"]: r for r in report["timing"]["stages"]}
        self.assertEqual(phases["build"]["status"], "failed")
        for name in ("structure", "layout", "save", "export_parts", "export_row"):
            self.assertEqual(phases[name]["status"], "skipped")

    def test_keyboard_interrupt_preserves_identity_report_and_original_scene(self):
        interrupted = KeyboardInterrupt("Synthetic interruption")
        with self.mocked_runtime(build_error=interrupted) as runtime:
            with self.assertRaises(KeyboardInterrupt) as captured:
                pipeline.run_job(self.job_path, "deliver")
            self.assertIs(captured.exception, interrupted)
            self.assert_restored(runtime)
            runtime.save.assert_not_called()
        report = self.stored_report()
        self.assertEqual(report["execution_status"], "interrupted")
        self.assertEqual(report["modules"][0]["status"], "interrupted")
        phases = {r["stage"]: r for r in report["timing"]["stages"]}
        self.assertEqual(phases["build"]["status"], "interrupted")
        self.assertEqual(phases["save"]["status"], "skipped")
        self.assertEqual(phases["restore_context"]["status"], "completed")

    def test_partial_export_failure_retains_earlier_artifact_and_skips_row(self):
        with self.mocked_runtime(export_error=ValueError("Synthetic second-part failure")) as runtime:
            report = pipeline.run_job(self.job_path, "deliver")
            self.assert_restored(runtime)
            runtime.row_export.assert_not_called()
        self.assertEqual(report["execution_status"], "failed")
        self.assertEqual(report["exports"]["status"], "failed")
        self.assertEqual(len(report["artifacts"]), 2)
        self.assertTrue(report["artifacts"][1]["path"].endswith("left.glb"))
        self.assertEqual(report["checks"]["file_signatures"], "partial")
        phases = {r["stage"]: r for r in report["timing"]["stages"]}
        self.assertEqual(phases["export_parts"]["status"], "failed")
        self.assertEqual(phases["export_row"]["status"], "skipped")

    def test_user_context_restores_even_when_skipped_stage_logging_fails(self):
        interrupted = KeyboardInterrupt("Synthetic interruption")
        with self.mocked_runtime(build_error=interrupted, journal_error_stage="structure") as runtime:
            with self.assertRaises(KeyboardInterrupt) as captured:
                pipeline.run_job(self.job_path, "deliver")
            self.assertIs(captured.exception, interrupted)
            self.assert_restored(runtime)
        report = self.stored_report()
        self.assertEqual(report["execution_status"], "interrupted")
        self.assertIn("timing_error", report)

    def test_user_context_restores_even_when_restoration_start_logging_fails(self):
        with self.mocked_runtime(journal_error_stage="restore_context") as runtime:
            report = pipeline.run_job(self.job_path, "preview")
            self.assert_restored(runtime)
        self.assertEqual(report["execution_status"], "failed")
        self.assertIn("timing_error", report)


if __name__ == "__main__":
    unittest.main()
