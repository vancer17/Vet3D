import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import dcc_preset
from catalog import PRESETS, lookup
from unreal_project import apply_enable


def project(version="5.7", plugins=None):
    data = {"FileVersion": 3, "EngineAssociation": version, "Plugins": plugins or []}
    return data


class CatalogTest(unittest.TestCase):
    def test_ids_are_unique_and_water_topic_covers_three_apps(self):
        ids = [item["id"] for item in PRESETS]
        self.assertEqual(len(ids), len(set(ids)))
        apps = {row["app"] for row in lookup(topic="water")}
        self.assertEqual(apps, {"unreal", "houdini", "blender"})

    def test_unreal_57_includes_core_water_and_excludes_older(self):
        current = lookup(app="unreal", topic="water", version="5.7")
        self.assertTrue(all(row["applicable"] for row in current))
        core = next(row for row in current if row["id"] == "unreal.water")
        self.assertEqual(core["plugins"], ["Water", "Landmass"])
        older = lookup(app="unreal", topic="water", version="5.6.1")
        self.assertTrue(all(row["applicable"] is False for row in older))


class UnrealApplyTest(unittest.TestCase):
    def write_project(self, directory, data):
        path = Path(directory) / "Demo.uproject"
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return path

    def test_dry_run_keeps_bytes_and_lists_missing_plugins(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_project(directory, project(plugins=[{"Name": "ModelingToolsEditorMode", "Enabled": True}]))
            before = path.read_bytes()
            result = apply_enable(path, "unreal.water", write=False)
            self.assertEqual(result["status"], "dry_run")
            self.assertEqual(result["changed"], ["Water", "Landmass"])
            self.assertEqual(path.read_bytes(), before)

    def test_write_enables_plugins_once_and_keeps_other_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_project(
                directory,
                project(plugins=[{"Name": "Water", "Enabled": False}, {"Name": "Cargo", "Enabled": False}]),
            )
            first = apply_enable(path, "unreal.water-samples", write=True)
            saved = json.loads(path.read_text(encoding="utf-8"))
            names = [(item["Name"], item["Enabled"]) for item in saved["Plugins"]]
            self.assertEqual(first["status"], "applied")
            self.assertEqual(
                names,
                [("Water", True), ("Cargo", False), ("Landmass", True), ("WaterExtras", True)],
            )
            before = path.read_bytes()
            second = apply_enable(path, "unreal.water-samples", write=True)
            self.assertEqual(second["status"], "already_enabled")
            self.assertEqual(path.read_bytes(), before)

    def test_old_engine_and_version_conflict_do_not_write(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_project(directory, project("5.6"))
            before = path.read_bytes()
            rejected = apply_enable(path, "unreal.water", write=True)
            conflict = apply_enable(path, "unreal.water", engine_version="5.8", write=True)
            self.assertEqual(rejected["status"], "rejected")
            self.assertEqual(conflict["status"], "rejected")
            self.assertEqual(path.read_bytes(), before)

    def test_guid_association_uses_caller_version_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_project(directory, project("{1234-ABCD}"))
            missing = apply_enable(path, "unreal.water", write=True)
            self.assertEqual(missing["status"], "rejected")
            allowed = apply_enable(path, "unreal.water", engine_version="5.7.1", write=True)
            self.assertEqual(allowed["status"], "applied")
            self.assertEqual(allowed["version_source"], "caller")


class CommandTest(unittest.TestCase):
    def test_host_apply_without_binary_is_blocked_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            code = dcc_preset.main(
                ["--output", directory, "apply", "--preset", "blender.fluid-domain", "--version", "4.2", "--write"],
                runner=lambda command: subprocess.CompletedProcess(command, 0),
            )
            self.assertEqual(code, 3)
            self.assertFalse(any(Path(directory).glob("*.blend")))
            saved = json.loads((Path(directory) / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["status"], "blocked")

    def test_houdini_dry_run_does_not_call_hython(self):
        called = []

        def runner(command):
            called.append(command)
            return subprocess.CompletedProcess(command, 0)

        with tempfile.TemporaryDirectory() as directory:
            code = dcc_preset.main(
                ["--output", directory, "apply", "--preset", "houdini.ocean-spectrum", "--version", "20.5", "--hython", "hython"],
                runner=runner,
            )
            self.assertEqual(code, 0)
            self.assertEqual(called, [])

    def test_lookup_unknown_version_is_rejected(self):
        code = dcc_preset.main(["lookup", "--app", "unreal", "--version", "latest"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
