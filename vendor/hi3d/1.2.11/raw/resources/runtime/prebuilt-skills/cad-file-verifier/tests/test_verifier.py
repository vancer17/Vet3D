import hashlib
import json
import sys
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
REPO = SKILL.parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
sys.path.insert(0, str(REPO / "tools" / "run-tools" / "scripts"))

import readers
import registry
import snapshot
import verify
from adapter import FreecadAdapter
from freecad_kernel import assert_workspace_write


def _dxf(layers, entities, units="4", dimensions=()):
    layer_rows = []
    for name, color in layers:
        layer_rows.append(f"0\nLAYER\n2\n{name}\n70\n0\n62\n{color}\n6\nCONTINUOUS\n")
    entity_rows = []
    for handle, kind, layer, extra in entities:
        entity_rows.append(f"0\n{kind}\n5\n{handle}\n8\n{layer}\n{extra}")
    for handle, layer, value in dimensions:
        entity_rows.append(f"0\nDIMENSION\n5\n{handle}\n8\n{layer}\n42\n{value}\n")
    return (
        "0\nSECTION\n2\nHEADER\n9\n$INSUNITS\n70\n" + units + "\n0\nENDSEC\n"
        "0\nSECTION\n2\nTABLES\n0\nTABLE\n2\nLAYER\n70\n" + str(len(layers)) + "\n"
        + "".join(layer_rows) + "0\nENDTAB\n0\nENDSEC\n"
        "0\nSECTION\n2\nENTITIES\n" + "".join(entity_rows) + "0\nENDSEC\n0\nEOF\n"
    )


def _step(entities, units=False):
    body = "\n".join("#%d=%s('x');" % (index, name) for index, name in enumerate(entities, 1))
    unit = "#90=SI_UNIT(.MILLI.,.METRE.);\n" if units else ""
    return (
        "ISO-10303-21;\nHEADER;\nFILE_SCHEMA(('AUTOMOTIVE_DESIGN'));\nENDSEC;\nDATA;\n"
        + unit + body + "\nENDSEC;\nEND-ISO-10303-21;\n"
    )


def _fcstd(path, objects):
    xml = "<Document>" + "".join('<Object name="%s" type="%s" />' % item for item in objects) + "</Document>"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Document.xml", xml)


def _task(root, candidate, **overrides):
    payload = {
        "schema_version": 1,
        "mode": "inspect",
        "candidate": str(candidate),
        "document_type": "drawing",
        "required_preservation": ["layers", "objects"],
        "require_native": False,
        "allowed_operations": ["read", "copy"],
        "target": {"software": "FreeCAD", "version": "", "build": "", "platform": ""},
    }
    payload.update(overrides)
    path = Path(root) / "task.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _check(result, check_id):
    return next(item for item in result["checks"] if item["id"] == check_id)


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class VerifierTests(unittest.TestCase):
    def test_extension_is_not_format_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stepped = root / "notes.txt"
            stepped.write_text(_step(["CARTESIAN_POINT"]), encoding="utf-8")
            fake = root / "part.step"
            fake.write_text("hello", encoding="utf-8")
            self.assertEqual(readers.identify(stepped)["id"], "step")
            self.assertEqual(readers.identify(stepped)["confidence"], "high")
            self.assertEqual(readers.identify(fake)["confidence"], "low")

    def test_no_baseline_keeps_preservation_unverified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            drawing = root / "a.dxf"
            drawing.write_text(_dxf([("A", 7)], [("10", "LINE", "A", "")]), encoding="utf-8")
            result = verify.execute(_task(root, drawing), root / "out", registry=root / "registry")
            self.assertEqual(result["overall_status"], "partial")
            self.assertEqual(_check(result, "layers")["status"], "unknown")
            self.assertIn("没有可信基线", _check(result, "layers")["reason"])
            self.assertNotIn("完全兼容", Path(result["report_path"]).read_text(encoding="utf-8"))

    def test_same_count_layer_change_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "before.dxf"
            candidate = root / "after.dxf"
            source.write_text(_dxf([("A", 7), ("B", 1)], [("10", "LINE", "A", ""), ("11", "LINE", "A", "")]), encoding="utf-8")
            candidate.write_text(_dxf([("A", 7), ("B", 1)], [("10", "LINE", "A", ""), ("11", "LINE", "B", "")]), encoding="utf-8")
            result = verify.execute(_task(
                root, candidate, mode="compare", source=str(source), required_preservation=["objects"]
            ), root / "out")
            self.assertEqual(result["overall_status"], "fail")
            self.assertEqual(_check(result, "objects")["status"], "fail")
            self.assertIn("图层", _check(result, "objects")["reason"])

    def test_flattened_features_fail_while_file_stays_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "before.FCStd"
            candidate = root / "after.FCStd"
            _fcstd(source, [("Sketch", "Sketcher::SketchObject"), ("Pad", "PartDesign::Pad")])
            _fcstd(candidate, [("Solid", "Part::Feature")])
            result = verify.execute(_task(
                root, candidate, mode="compare", source=str(source), document_type="part",
                required_preservation=["features"],
            ), root / "out")
            self.assertEqual(_check(result, "file_readable")["status"], "pass")
            self.assertEqual(_check(result, "features")["status"], "fail")
            self.assertEqual(result["overall_status"], "fail")

    def test_expected_dimension_change_is_not_an_unexpected_loss(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "before.dxf"
            candidate = root / "after.dxf"
            source.write_text(_dxf([("A", 7)], [("10", "LINE", "A", "")], dimensions=[("D1", "A", "10.0")]), encoding="utf-8")
            candidate.write_text(_dxf([("A", 7)], [("10", "LINE", "A", "")], dimensions=[("D1", "A", "12.5")]), encoding="utf-8")
            result = verify.execute(_task(
                root, candidate, mode="compare", source=str(source),
                required_preservation=["objects", "dimensions"],
                expected_changes=[{"path": "dimensions.D1.value", "value": 12.5}],
            ), root / "out")
            self.assertEqual(_check(result, "dimensions")["status"], "pass")
            self.assertEqual(_check(result, "objects")["status"], "pass")
            self.assertEqual(result["expected_confirmed"][0]["path"], "dimensions.D1.value")
            self.assertEqual(result["overall_status"], "pass")
            self.assertIn("只覆盖本次要求", Path(result["report_path"]).read_text(encoding="utf-8"))

    def test_dependency_outside_workspace_is_not_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "original-font.ttf"
            outside.write_bytes(b"font")
            before = _digest(outside)
            drawing = root / "a.dxf"
            drawing.write_text(_dxf([("A", 7)], [("10", "LINE", "A", "")]), encoding="utf-8")
            result = verify.execute(_task(
                root, drawing, dependencies=[{"id": "font", "path": str(outside)}]
            ), root / "out")
            self.assertEqual(_check(result, "dependencies_closed")["status"], "fail")
            self.assertIn("未闭合", _check(result, "dependencies_closed")["reason"])
            self.assertEqual(_digest(outside), before)

    def test_missing_freecad_is_blocked_not_incompatible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            drawing = root / "a.dxf"
            drawing.write_text(_dxf([("A", 7)], [("10", "LINE", "A", "")]), encoding="utf-8")
            result = verify.execute(_task(root, drawing, require_native=True), root / "out")
            self.assertEqual(result["overall_status"], "blocked")
            self.assertEqual(_check(result, "native_open")["status"], "blocked")
            report = Path(result["report_path"]).read_text(encoding="utf-8")
            self.assertIn("不构成文件不兼容", report)

    def test_registry_keeps_conflict_and_old_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            passed = _measured("build-a", "pass")
            failed = _measured("build-a", "fail")
            registry.append_record(root, passed)
            registry.append_record(root, failed)
            view = json.loads((root / "view.json").read_text(encoding="utf-8"))
            row = next(item for item in view["rows"] if item["check_id"] == "layers" and item["target_environment"]["build"] == "build-a")
            self.assertTrue(row["conflict"])
            self.assertEqual(row["measured"]["pass"], 1)
            self.assertEqual(row["measured"]["fail"], 1)
            registry.append_record(root, _measured("build-b", "fail"))
            view = json.loads((root / "view.json").read_text(encoding="utf-8"))
            old = next(item for item in view["rows"] if item["target_environment"]["build"] == "build-a" and item["check_id"] == "layers")
            new = next(item for item in view["rows"] if item["target_environment"]["build"] == "build-b" and item["check_id"] == "layers")
            self.assertEqual(old["measured"]["pass"], 1)
            self.assertEqual(new["measured"]["pass"], 0)
            self.assertEqual(len((root / "records.jsonl").read_text(encoding="utf-8").splitlines()), 3)

    def test_mock_success_is_excluded_from_measured_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = root / "candidate.txt"
            source = root / "source.txt"
            candidate.write_text("candidate", encoding="utf-8")
            source.write_text("source", encoding="utf-8")
            snap = snapshot.blank_snapshot()
            snap["format"] = {"id": "dxf", "version": None, "confidence": "high", "evidence": "mock"}
            snap["read_error"] = ""
            snap["layers"] = snapshot.read_items({"A": {"color": snapshot.cell(7)}})
            result = verify.execute(_task(
                root, candidate, mode="compare", source=str(source), adapter="mock",
                required_preservation=["layers"], mock_snapshots={"candidate": snap, "source": snap},
            ), root / "out", registry=root / "registry")
            self.assertEqual(result["overall_status"], "pass")
            self.assertFalse(result["counts_as_measured_pass"])
            view = json.loads((root / "registry" / "view.json").read_text(encoding="utf-8"))
            self.assertGreaterEqual(view["mock_excluded"], 1)
            self.assertFalse(any(item["measured"]["pass"] for item in view["rows"]))

    def test_repair_without_authorization_does_not_modify(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            drawing = root / "a.dxf"
            drawing.write_text(_dxf([("A", 7)], [("10", "LINE", "A", "")]), encoding="utf-8")
            before = _digest(drawing)
            result = verify.execute(_task(root, drawing, repair=True), root / "out")
            self.assertFalse(result["repairs_performed"])
            self.assertIn("超出已有授权", result["needs_confirmation"]["effect"])
            self.assertEqual(_digest(drawing), before)

    def test_symlink_is_not_a_write_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "outside"
            outside.mkdir()
            target = outside / "real.dxf"
            target.write_text(_dxf([("A", 7)], [("10", "LINE", "A", "")]), encoding="utf-8")
            link = root / "link.dxf"
            link.symlink_to(target)
            before = _digest(target)
            result = verify.execute(_task(root, link), root / "out")
            copy = next((root / "out" / "workspace").rglob("link.dxf"))
            self.assertFalse(copy.is_symlink())
            self.assertEqual(_digest(target), before)
            self.assertTrue(result["source_unchanged"])
            with self.assertRaises(ValueError):
                assert_workspace_write(target, root / "out" / "workspace", target)

    def test_registry_failure_keeps_the_local_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            drawing = root / "a.dxf"
            drawing.write_text(_dxf([("A", 7)], [("10", "LINE", "A", "")]), encoding="utf-8")
            blocked = root / "registry-file"
            blocked.write_text("not a directory", encoding="utf-8")
            result = verify.execute(_task(root, drawing), root / "out", registry=blocked)
            self.assertFalse(result["registry_updated"])
            report = Path(result["report_path"]).read_text(encoding="utf-8")
            self.assertIn("兼容记录未更新", report)
            self.assertTrue((root / "out" / "result.json").is_file())

    def test_completed_result_is_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            drawing = root / "a.dxf"
            drawing.write_text(_dxf([("A", 7)], [("10", "LINE", "A", "")]), encoding="utf-8")
            checker = FreecadAdapter()
            first = verify.execute(_task(root, drawing), root / "out", adapter=checker)
            second = verify.execute(_task(root, drawing), root / "out", adapter=checker)
            self.assertEqual(checker.snapshots, 1)
            self.assertTrue(second["reused"])
            self.assertEqual(second["fingerprint"], first["fingerprint"])

    def test_step_type_histogram_is_not_a_full_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "before.step"
            same = root / "same.step"
            changed = root / "changed.step"
            source.write_text(_step(["CARTESIAN_POINT", "DIRECTION"], units=True), encoding="utf-8")
            same.write_text(_step(["CARTESIAN_POINT", "DIRECTION"], units=True), encoding="utf-8")
            changed.write_text(_step(["CARTESIAN_POINT", "CARTESIAN_POINT"], units=True), encoding="utf-8")
            partial = verify.execute(_task(
                root, same, mode="compare", source=str(source), document_type="exchange_solid",
                required_preservation=[],
            ), root / "partial")
            self.assertEqual(_check(partial, "entity_types")["status"], "pass")
            self.assertEqual(_check(partial, "geometry")["status"], "unknown")
            self.assertEqual(partial["overall_status"], "partial")
            failed = verify.execute(_task(
                root / "again" if False else root, changed, mode="compare", source=str(source),
                document_type="exchange_solid", required_preservation=["entity_types"],
            ), root / "failed")
            self.assertEqual(_check(failed, "entity_types")["status"], "fail")

    def test_budget_timeout_does_not_count_as_success(self):
        class BudgetTimeout(RuntimeError):
            pass

        def runner(*args, **kwargs):
            raise BudgetTimeout("stopped")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            drawing = root / "a.dxf"
            drawing.write_text(_dxf([("A", 7)], [("10", "LINE", "A", "")]), encoding="utf-8")
            freecad = root / "FreeCAD"
            freecad.write_text("#!/bin/sh\n", encoding="utf-8")
            freecad.chmod(0o755)
            result = verify.execute(_task(
                root, drawing, mode="roundtrip", require_native=True, freecad=str(freecad),
                allowed_operations=["read", "copy", "roundtrip"],
            ), root / "out", runner=runner)
            self.assertEqual(result["overall_status"], "blocked")
            self.assertTrue((root / "out" / "waiting.json").is_file())
            self.assertFalse(any((root / "out").rglob("native.json")))

    def test_concurrent_appends_keep_every_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def add(index):
                registry.append_record(root, _measured("build-" + str(index), "pass", record_id="rec-" + str(index)))
            threads = [threading.Thread(target=add, args=(index,)) for index in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(len((root / "records.jsonl").read_text(encoding="utf-8").splitlines()), 8)

    def test_unsafe_fcstd_is_not_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.FCStd"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("../evil.txt", "nope")
                archive.writestr("Document.xml", "<Document />")
            snap = readers.read_static(path)
            self.assertTrue(snap["read_error"])
            self.assertFalse((Path(tmp) / "evil.txt").exists())

    def test_superseded_failure_stays_in_the_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            failed = _measured("build-a", "fail", record_id="old")
            registry.append_record(root, failed)
            corrected = _measured("build-a", "pass", record_id="new")
            corrected["supersedes"] = "old"
            registry.append_record(root, corrected)
            view = json.loads((root / "view.json").read_text(encoding="utf-8"))
            row = next(item for item in view["rows"] if item["check_id"] == "layers")
            self.assertEqual(row["measured"]["fail"], 0)
            self.assertEqual(row["measured"]["pass"], 1)
            self.assertEqual(len((root / "records.jsonl").read_text(encoding="utf-8").splitlines()), 2)

    def test_classcad_upstream_does_not_satisfy_another_native_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            drawing = root / "a.dxf"
            drawing.write_text(_dxf([("A", 7)], [("10", "LINE", "A", "")]), encoding="utf-8")
            binary = root / "freecad"
            binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            binary.chmod(0o755)

            def runner(*_args, **_kwargs):
                raise AssertionError("source evidence must not start the target kernel")

            result = verify.execute(_task(
                root, drawing,
                require_native=True,
                freecad=str(binary),
                target={"software": "SolidWorks", "version": "2024", "build": "x", "platform": "test"},
                upstream_build={"tool": "classcad", "version": "0", "session_evidence_refs": ["session-a"]},
            ), root / "out", runner=runner)
            self.assertEqual(result["overall_status"], "blocked")
            self.assertEqual(_check(result, "native_open")["status"], "blocked")
            self.assertIn("不能代替", _check(result, "native_open")["reason"])
            self.assertFalse(result["counts_as_measured_pass"])
            self.assertEqual(result["upstream_build"]["tool"], "classcad")
            report = Path(result["report_path"]).read_text(encoding="utf-8")
            self.assertIn("ClassCAD", report)
            self.assertIn("session-a", report)
            self.assertFalse((root / "out" / "native.json").exists())

    def test_classcad_samples_stay_out_of_unspecified_native_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plain = _measured("build-a", "pass", record_id="plain")
            sourced = _measured("build-a", "pass", record_id="sourced")
            sourced["upstream_build"] = {"tool": "classcad", "version": "0", "session_evidence_refs": []}
            registry.append_record(root, plain)
            registry.append_record(root, sourced)
            view = json.loads((root / "view.json").read_text(encoding="utf-8"))
            rows = [item for item in view["rows"] if item["check_id"] == "layers"]
            self.assertEqual(len(rows), 2)
            classcad = next(item for item in rows if item["upstream_build"]["tool"] == "classcad")
            other = next(item for item in rows if item["upstream_build"]["tool"] == "not-specified")
            self.assertIn("不证明", classcad["limits"])
            self.assertEqual(other["measured"]["pass"], 1)
            self.assertEqual(classcad["measured"]["pass"], 1)

    def test_changed_upstream_does_not_reuse_the_previous_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            drawing = root / "a.dxf"
            drawing.write_text(_dxf([("A", 7)], [("10", "LINE", "A", "")]), encoding="utf-8")
            verify.execute(_task(root, drawing, require_native=False), root / "out")
            with self.assertRaises(ValueError):
                verify.execute(_task(
                    root, drawing, require_native=False,
                    upstream_build={"tool": "classcad", "version": "", "session_evidence_refs": []},
                ), root / "out")

    def test_overall_priority(self):
        self.assertEqual(snapshot.overall_status([
            {"required": True, "status": "pass"},
            {"required": True, "status": "unknown"},
            {"required": True, "status": "blocked"},
            {"required": True, "status": "fail"},
        ]), "fail")
        self.assertEqual(snapshot.overall_status([
            {"required": True, "status": "pass"},
            {"required": True, "status": "blocked"},
        ]), "blocked")
        self.assertEqual(snapshot.overall_status([
            {"required": True, "status": "unknown"},
        ]), "partial")
        self.assertEqual(snapshot.overall_status([]), "partial")


def _measured(build, status, record_id=None):
    return {
        "schema_version": 1,
        "record_id": record_id or build + "-" + status,
        "record_kind": "measured",
        "evidence_origin": "measured",
        "recorded_at": "2026-01-01T00:00:00Z",
        "source_environment": {"software": "FreeCAD", "version": "1", "build": build, "platform": "test"},
        "target_environment": {"software": "FreeCAD", "version": "1", "build": build, "platform": "test"},
        "document": {"type": "drawing", "format": "dxf", "format_version": None, "sample_id": record_id or status},
        "adapter": {"id": "freecad-native", "version": "1"},
        "check_profile": {"id": "drawing-preservation", "revision": "1"},
        "checks": [{"id": "layers", "required": True, "status": status, "reason": status, "evidence_refs": ["report.md"]}],
        "overall_status": status if status != "pass" else "pass",
        "evidence_index": ["report.md"],
        "supersedes": None,
    }


if __name__ == "__main__":
    unittest.main()
