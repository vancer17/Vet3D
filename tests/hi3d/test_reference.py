"""Portable reference-bundle contract tests using inert synthetic originals."""

import hashlib
import json
import os
import stat
import struct
import sys
import unittest
import warnings
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from vet3d.infrastructure.hi3d_reference.bundle import (
    export_reference, materialize_reference, verify_reference,
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf8"))


def fingerprint(path, data):
    return {"path": path, "size": len(data), "sha256": digest(data)}


def source_fixture(root):
    resources, release = root / "source", root / "release"
    resources.mkdir()
    member = b'{"name":"inert-fixture"}\r\n'
    header_tree = json.dumps({"files": {"package.json": {"size": len(member), "offset": "0"}}}).encode("utf8")
    padded = header_tree + b"\0" * (-len(header_tree) % 4)
    asar = struct.pack("<4I", 4, len(padded) + 8, len(padded) + 4, len(header_tree)) + padded + member
    originals = {
        "app.asar": asar,
        "runtime/manifest.json": b'{"runtimeVersion":"fixture"}\r\n',
        "runtime/prebuilt-skills/example/SKILL.md": "# 示例\r\nKeep original bytes.\r\n".encode("utf8"),
        "runtime/blob.bin": bytes(range(256)) * 8,
    }
    rows = []
    for path, data in originals.items():
        target = resources / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        rows.append({**fingerprint(path, data), "scope": "resources" if path == "app.asar" else "runtime"})
    rows.append({
        **fingerprint("app.asar/package.json", member),
        "scope": "asar-member", "member_path": "package.json",
        "offset": len(asar) - len(member),
    })
    inventory = b"".join((json.dumps(row, sort_keys=True) + "\n").encode("utf8") for row in rows)
    directory = release / "inventory"
    directory.mkdir(parents=True)
    (directory / "inventory.jsonl").write_bytes(inventory)
    write_json(directory / "inventory.lock.json", {
        "inventory_sha256": digest(inventory), "records": len(rows),
        "anchors_sha256": {"app.asar": digest(asar)},
        "disk": {"runtime_version": "fixture", "platform": "win32", "arch": "x64"},
    })
    excluded = resources / "runtime/prebuilt-skills/example/__pycache__/generated.pyc"
    excluded.parent.mkdir()
    excluded.write_bytes(b"locally generated")
    installer = root / "inert-installer.exe"
    installer.write_bytes(b"MZ-INERT-FIXTURE")
    return release, resources, installer, originals, member


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        working = TemporaryDirectory()
        self.addCleanup(working.cleanup)
        self.root = Path(working.name)
        self.release, self.resources, self.installer, self.originals, self.member = source_fixture(self.root)
        self.reference = self.root / "reference"

    def export(self):
        return export_reference(self.release, self.resources, self.installer, self.reference)

    def manifest(self):
        return json.loads((self.reference / "reference.lock.json").read_text(encoding="utf8"))

    def rewrite_archive(self, modify):
        manifest = self.manifest()
        path = self.reference / manifest["archive"]["path"]
        with zipfile.ZipFile(path) as incoming:
            entries = [(info, incoming.read(info)) for info in incoming.infolist()]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(path, "w") as outgoing:
                modify(entries, outgoing)
        value = fingerprint(manifest["archive"]["path"], path.read_bytes())
        manifest["archive"].update(value)
        for record in manifest["artifacts"]:
            if record["path"] == value["path"]:
                record.update(value)
        write_json(self.reference / "reference.lock.json", manifest)

    def test_export_preserves_originals_and_excludes_generated_cache(self):
        result = self.export()
        self.assertEqual(result["resources"], len(self.originals))
        self.assertEqual(result["excluded"], 1)
        skill = "runtime/prebuilt-skills/example/SKILL.md"
        self.assertEqual((self.reference / "raw/resources" / skill).read_bytes(), self.originals[skill])
        self.assertEqual((self.reference / "raw/app-members/package.json").read_bytes(), self.member)
        self.assertFalse((self.reference / "raw/resources/runtime/blob.bin").exists())
        self.assertTrue(verify_reference(self.reference)["verified"])
        manifest = self.manifest()
        self.assertIn("not inferred from filename", manifest["boundaries"]["installer_release_equivalence"])
        self.assertNotIn(b"\xef\xbb\xbf", (self.reference / "reference.lock.json").read_bytes())

    def test_materialize_matches_exact_allowlist_and_reuses(self):
        self.export()
        output = self.root / "materialized"
        first = materialize_reference(self.reference, output)
        self.assertFalse(first["reused"])
        for path, data in self.originals.items():
            self.assertEqual((output / "resources" / path).read_bytes(), data)
        self.assertTrue(verify_reference(self.reference, output / "resources")["materialized_resources_verified"])
        self.assertTrue(materialize_reference(self.reference, output)["reused"])

    def test_export_rejects_changed_source_and_publishes_nothing(self):
        (self.resources / "runtime/blob.bin").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "bytes do not match"):
            self.export()
        self.assertFalse(self.reference.exists())

    def test_export_will_not_overwrite_existing_directory(self):
        self.reference.mkdir()
        sentinel = self.reference / "keep.txt"
        sentinel.write_bytes(b"keep")
        with self.assertRaisesRegex(ValueError, "must not already exist"):
            self.export()
        self.assertEqual(sentinel.read_bytes(), b"keep")

    def test_export_rejects_overlap_with_locked_inputs(self):
        for relative in ("inventory/new-export", "extraction/new-export"):
            with self.subTest(relative=relative):
                with self.assertRaisesRegex(ValueError, "locked release input"):
                    export_reference(
                        self.release, self.resources, self.installer, self.release / relative
                    )
                self.assertFalse((self.release / relative).exists())

    def test_materialize_rejects_symlink_target_without_touching_target(self):
        self.export()
        target = self.root / "keep"
        target.mkdir()
        (target / "sentinel").write_bytes(b"keep")
        link = self.root / "linked-output"
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError:
            self.skipTest("symbolic links unavailable in this environment")
        with self.assertRaisesRegex(ValueError, "unlinked directory"):
            materialize_reference(self.reference, link)
        self.assertEqual((target / "sentinel").read_bytes(), b"keep")

    def test_verify_rejects_lfs_pointer_instead_of_package(self):
        self.export()
        installer = self.reference / "packages" / self.installer.name
        installer.write_bytes(b"version https://git-lfs.github.com/spec/v1\noid sha256:" + b"0" * 64 + b"\nsize 12\n")
        with self.assertRaisesRegex(ValueError, "LFS pointer"):
            verify_reference(self.reference)

    def test_verify_rejects_tampered_readable_original(self):
        self.export()
        (self.reference / "raw/app-members/package.json").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "bytes do not match"):
            verify_reference(self.reference)

    def test_materialize_rejects_existing_partial_directory(self):
        self.export()
        output = self.root / "partial"
        output.mkdir()
        sentinel = output / "keep.txt"
        sentinel.write_bytes(b"keep")
        with self.assertRaisesRegex(ValueError, "unexpected entries"):
            materialize_reference(self.reference, output)
        self.assertEqual(sentinel.read_bytes(), b"keep")

    def test_materialize_rejects_path_traversal_before_writing(self):
        self.export()
        self.rewrite_archive(lambda entries, archive: [
            archive.writestr(info if index else "../escaped.txt", data)
            for index, (info, data) in enumerate(entries)
        ])
        with self.assertRaisesRegex(ValueError, "unsafe relative path"):
            materialize_reference(self.reference, self.root / "output")
        self.assertFalse((self.root / "escaped.txt").exists())
        self.assertFalse((self.root / "output").exists())

    def test_materialize_rejects_duplicate_zip_member(self):
        self.export()
        def duplicate(entries, archive):
            for info, data in entries:
                archive.writestr(info, data)
            archive.writestr(entries[0][0], entries[0][1])
        self.rewrite_archive(duplicate)
        with self.assertRaisesRegex(ValueError, "duplicate ZIP"):
            materialize_reference(self.reference, self.root / "output")
        self.assertFalse((self.root / "output").exists())

    def test_materialize_rejects_symlink_zip_member(self):
        self.export()
        def link(entries, archive):
            for index, (info, data) in enumerate(entries):
                if index == 0:
                    info.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(info, data)
        self.rewrite_archive(link)
        with self.assertRaisesRegex(ValueError, "non-regular ZIP"):
            materialize_reference(self.reference, self.root / "output")
        self.assertFalse((self.root / "output").exists())

    def test_materialize_rejects_wrong_member_size(self):
        self.export()
        self.rewrite_archive(lambda entries, archive: [
            archive.writestr(info, data + b"x" if index == 0 else data)
            for index, (info, data) in enumerate(entries)
        ])
        with self.assertRaisesRegex(ValueError, "unexpected ZIP member or size"):
            materialize_reference(self.reference, self.root / "output")
        self.assertFalse((self.root / "output").exists())

    def test_materialize_rejects_same_size_wrong_member_bytes(self):
        self.export()
        self.rewrite_archive(lambda entries, archive: [
            archive.writestr(info, b"x" * len(data) if index == 0 else data)
            for index, (info, data) in enumerate(entries)
        ])
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            materialize_reference(self.reference, self.root / "output")
        self.assertFalse((self.root / "output").exists())

    def test_verify_rejects_changed_inventory_allowlist(self):
        self.export()
        manifest = self.manifest()
        manifest["resources"].pop()
        write_json(self.reference / "reference.lock.json", manifest)
        with self.assertRaisesRegex(ValueError, "differs from fixed inventory"):
            verify_reference(self.reference)

    def test_materialize_rejects_extra_file_on_reuse(self):
        self.export()
        output = self.root / "materialized"
        materialize_reference(self.reference, output)
        (output / "resources/extra.txt").write_bytes(b"not part of release")
        with self.assertRaisesRegex(ValueError, "file set differs"):
            materialize_reference(self.reference, output)


if __name__ == "__main__":
    unittest.main()
