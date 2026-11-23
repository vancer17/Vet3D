"""Portable evidence coverage, provenance and path-boundary tests."""

from importlib.util import module_from_spec, spec_from_file_location
import ast
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/hi3d/export-evidence.py"
SPEC = spec_from_file_location("hi3d_export_evidence", SCRIPT)
evidence = module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)


class EvidenceTests(unittest.TestCase):
    def test_links_preserve_nested_path_line_and_fragment(self):
        with TemporaryDirectory() as working:
            root = Path(working)
            document = root / "docs/hi3d/example.md"
            document.parent.mkdir(parents=True)
            document.write_text(
                "[one](<D:/sample/file (copy).py:12>)\n"
                "[two](/D:/sample/file%20name.md:20#example)\n",
                encoding="utf8",
            )
            found = evidence.collect_links(root)
            self.assertEqual(len(found), 2)
            self.assertEqual(found["D:/sample/file (copy).py"][0]["source_line"], "12")
            self.assertEqual(found["D:/sample/file%20name.md"][0]["fragment"], "example")

    def test_json_derivative_keeps_distinct_source_and_derived_hashes(self):
        source = b'{"output":"C:/Users/test/AppData/Local/Temp/probe/result.glb","value":1}\r\n'
        result, mode, reason = evidence.portable_probe(Path("report.json"), source)
        self.assertEqual(mode, "sanitized")
        self.assertNotEqual(evidence.digest(result), evidence.digest(source))
        self.assertIn("{PROBE_ROOT}", result.decode("utf8"))
        self.assertNotIn(b"\r", result)
        self.assertTrue(reason)
        self.assertEqual(json.loads(result)["value"], 1)

    def test_probe_code_uses_explicit_environment_and_relative_sibling(self):
        source = (
            "from pathlib import Path\n"
            "skill=Path('D:/install/Hi3DAgent.__hi3d-transaction/resources/skill')\n"
            "input=Path('C:/Users/test/AppData/Local/Temp/hi3d-test/source.blend')\n"
        ).encode("utf8")
        result, mode, _ = evidence.portable_probe(Path("probe.py"), source)
        ast.parse(result.decode("utf8"))
        self.assertEqual(mode, "sanitized")
        self.assertIn(b"HI3D_RESOURCES_ROOT", result)
        self.assertIn(b"parents[1]", result)
        self.assertNotIn(b"C:/Users", result)

    def test_portable_code_adds_path_import_after_future_statement(self):
        result, mode, _ = evidence.portable_probe(
            Path("probe.py"),
            b"from __future__ import annotations\nsource='D:/install/Hi3DAgent.__hi3d-transaction/resources/test.py'\n",
        )
        tree = ast.parse(result.decode("utf8"))
        self.assertEqual(tree.body[0].module, "__future__")
        self.assertIn(b"from pathlib import Path", result)
        self.assertEqual(mode, "sanitized")

    def test_credential_shaped_probe_is_rejected(self):
        with self.assertRaises(ValueError):
            evidence.portable_probe(Path("report.json"), b'{"access_token":"not-a-real-secret"}')
        with self.assertRaises(ValueError):
            evidence.clean_json({"url": "https://example.invalid/data?token=sample"})

    def test_relative_targets_cannot_escape(self):
        for path in ("../outside", "/absolute", "C:/absolute", "folder\\file", "a/./file", ""):
            with self.subTest(path=path), self.assertRaises(ValueError):
                evidence.relative_path(path)

    def test_cache_unknown_and_managed_files_are_not_opened(self):
        with TemporaryDirectory() as working:
            root = Path(working)
            built = root / "codex-home/skills/buildin"
            built.mkdir(parents=True)
            (built / ".sparc3d-skills.json").write_bytes(b"not JSON; must not parse")
            (built / "auth.json").write_bytes(b"not JSON; unknown file must not read")
            source = built / "known.py"
            source.write_bytes(b"print('sample')\n")
            expected = {"runtime/prebuilt-skills/known.py": {
                "size": source.stat().st_size, "sha256": evidence.file_digest(source)
            }}
            report = evidence.cache_audit(root, expected)
            counts = report["roots"][0]["counts"]
            self.assertEqual(counts["identical_to_release"], 1)
            self.assertEqual(counts["deployment_metadata_excluded_without_reading"], 1)
            self.assertEqual(counts["unreviewed_not_read_or_archived"], 1)
            self.assertEqual(report["exported_cache_implementation_files"], [])

    def test_tampered_or_relabelled_fixture_fails_verification(self):
        with TemporaryDirectory() as working:
            root = Path(working)
            (root / "docs/hi3d").mkdir(parents=True)
            reference = root / "reference"
            reference.mkdir()
            (reference / "fixture.json").write_bytes(b"{}\n")
            row = evidence.artifact_record("fixture.json", b"{}\n", b"source\n",
                                           "sanitized", "example conversion", "probe")
            manifest = {"schema_version": 1, "entries": [], "unique_sources": 0, "fixtures": [row]}
            (reference / "evidence-map.json").write_bytes(evidence.json_bytes(manifest))
            (reference / "reference.lock.json").write_bytes(
                evidence.json_bytes({"resources": [], "artifacts": []})
            )
            (reference / "cache-audit.json").write_bytes(
                evidence.json_bytes({"schema_version": 1, "roots": [],
                                     "exported_cache_implementation_files": []})
            )
            self.assertEqual(evidence.verify_evidence(root, reference)["fixtures"], 1)
            row["evidence_mode"] = "original"
            (reference / "evidence-map.json").write_bytes(evidence.json_bytes(manifest))
            with self.assertRaisesRegex(ValueError, "original fixture"):
                evidence.verify_evidence(root, reference)
            row["evidence_mode"] = "sanitized"
            (reference / "evidence-map.json").write_bytes(evidence.json_bytes(manifest))
            (reference / "fixture.json").write_bytes(b"tampered\n")
            with self.assertRaisesRegex(ValueError, "fixture bytes"):
                evidence.verify_evidence(root, reference)

    def test_wrong_archive_or_evidence_mode_is_rejected(self):
        with TemporaryDirectory() as working:
            root = Path(working)
            docs = root / "docs/hi3d"
            docs.mkdir(parents=True)
            source = "D:/install/Hi3DAgent.__hi3d-transaction/resources/example.py"
            (docs / "example.md").write_text(f"[source](<{source}>)\n", encoding="utf8")
            reference = root / "reference"
            (reference / "packages").mkdir(parents=True)
            package = b"sample archive bytes"
            package_row = {"path": "packages/resources-win-x64.zip", "size": len(package),
                           "sha256": evidence.digest(package)}
            (reference / package_row["path"]).write_bytes(package)
            resource = {"path": "example.py", "size": 4, "sha256": evidence.digest(b"pass")}
            lock = {"resources": [resource], "artifacts": [package_row], "archive": package_row}
            (reference / "reference.lock.json").write_bytes(evidence.json_bytes(lock))
            audit = {"schema_version": 1, "roots": [], "exported_cache_implementation_files": []}
            (reference / "cache-audit.json").write_bytes(evidence.json_bytes(audit))
            entry = {
                "source_path": source, "occurrences": [{"document": "docs/hi3d/example.md"}],
                "evidence_mode": "original", "status": "archived",
                "source_sha256": resource["sha256"], "reason": None,
                "target": {"kind": "archive_member", "archive": package_row["path"],
                           "member": "resources/example.py", **resource},
            }
            manifest = {"schema_version": 1, "entries": [entry], "unique_sources": 1, "fixtures": []}
            (reference / "evidence-map.json").write_bytes(evidence.json_bytes(manifest))
            self.assertEqual(evidence.verify_evidence(root, reference)["sources"], 1)
            entry["target"]["archive"] = "packages/other.zip"
            (reference / "evidence-map.json").write_bytes(evidence.json_bytes(manifest))
            with self.assertRaisesRegex(ValueError, "archive differs"):
                evidence.verify_evidence(root, reference)
            entry["target"]["archive"] = package_row["path"]
            entry["evidence_mode"] = "not_archived"
            (reference / "evidence-map.json").write_bytes(evidence.json_bytes(manifest))
            with self.assertRaisesRegex(ValueError, "mode/status/target"):
                evidence.verify_evidence(root, reference)
            entry["evidence_mode"] = "invented"
            (reference / "evidence-map.json").write_bytes(evidence.json_bytes(manifest))
            with self.assertRaisesRegex(ValueError, "unknown evidence mode"):
                evidence.verify_evidence(root, reference)


if __name__ == "__main__":
    unittest.main()
