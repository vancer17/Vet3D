"""Offline reference export and safe materialization. No upstream code executes.

The fixed inventory owns the source file allowlist. Ordinary copied files retain
their exact bytes; only the new manifest and ZIP container are generated here.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import zipfile
from pathlib import Path

from ..hi3d_inventory.disk import _relative_path


LOCK = "reference.lock.json"
ARCHIVE = "packages/resources-win-x64.zip"
CHUNK = 1024 * 1024
SHA256 = re.compile(r"[0-9a-f]{64}")
TEXT_SUFFIXES = {
    ".py", ".md", ".json", ".jsonl", ".yaml", ".yml", ".toml", ".ini",
    ".mjs", ".cjs", ".js", ".ts", ".txt", ".rst", ".html", ".css", ".glsl",
    ".csv", ".ps1", ".sh", ".bat", ".cmd", ".xml", ".cfg", ".conf",
}
LFS_PREFIX = b"version https://git-lfs.github.com/spec/v1"


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _json(path):
    return json.loads(path.read_bytes().decode("utf-8"), object_pairs_hook=_unique_object)


def _regular(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or (
        getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    ):
        raise ValueError(f"not a regular, unlinked file: {path}")
    return info


def _directory(path):
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or (
        getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    ):
        raise ValueError(f"not an ordinary, unlinked directory: {path}")
    return info


def _cleanup_staging(path, parent, prefix):
    if path.exists() or path.is_symlink():
        _directory(path)
        resolved = path.resolve(strict=True)
        if resolved.parent != parent.resolve(strict=True) or not path.name.startswith(prefix):
            raise ValueError(f"refusing cleanup outside expected staging parent: {path}")
        shutil.rmtree(resolved)


def _require_disjoint(output, protected, label):
    target, source = output.resolve(), protected.resolve()
    if target.is_relative_to(source) or source.is_relative_to(target):
        raise ValueError(f"output overlaps {label}: {source}")


def _within(root, relative):
    relative = _relative_path(relative, "reference path")
    path = root / relative
    # Do not silently follow directory links while copying or checking originals.
    current = root
    for part in Path(relative).parts:
        current = current / part
        if current.exists() or current.is_symlink():
            info = current.lstat()
            if stat.S_ISLNK(info.st_mode) or (
                getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            ):
                raise ValueError(f"linked path component: {current}")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"reference path escapes root: {relative}")
    return path


def _fingerprint(path, relative):
    before = _regular(path)
    with path.open("rb") as stream:
        if stream.read(len(LFS_PREFIX)) == LFS_PREFIX:
            raise ValueError(f"LFS pointer is not materialized: {relative}")
        stream.seek(0)
        sha = hashlib.file_digest(stream, "sha256").hexdigest()
        opened = os.fstat(stream.fileno())
    after = path.stat()
    identity = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
    if identity(before) != identity(opened) or identity(opened) != identity(after):
        raise ValueError(f"file changed while reading: {relative}")
    return {"path": relative, "size": after.st_size, "sha256": sha}


def _record(record):
    if not isinstance(record, dict):
        raise ValueError("invalid file record")
    relative = _relative_path(record.get("path"), "file record")
    size, sha = record.get("size"), record.get("sha256")
    if type(size) is not int or size < 0 or not isinstance(sha, str) or not SHA256.fullmatch(sha):
        raise ValueError(f"invalid size or SHA-256: {relative}")
    return {"path": relative, "size": size, "sha256": sha}


def _records(records, label):
    if not isinstance(records, list) or not records:
        raise ValueError(f"empty or invalid {label}")
    result, seen = [], set()
    for original in records:
        record = _record(original)
        key = record["path"].casefold()
        if key in seen:
            raise ValueError(f"duplicate or case-colliding {label}: {record['path']}")
        seen.add(key)
        result.append(record)
    # A file cannot also be a parent directory of another listed file.
    paths = {item["path"].casefold() for item in result}
    for item in result:
        for parent in Path(item["path"]).parents:
            if parent.as_posix().casefold() in paths:
                raise ValueError(f"file/directory conflict: {item['path']}")
    return sorted(result, key=lambda item: item["path"])


def _require_fingerprint(path, expected):
    actual = _fingerprint(path, expected["path"])
    if actual != _record(expected):
        raise ValueError(f"file bytes do not match manifest: {expected['path']}")
    return actual


def _copy_verified(source, target, expected):
    before = _fingerprint(source, expected["path"])
    if before != _record(expected):
        raise ValueError(f"source bytes do not match release: {expected['path']}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as incoming, target.open("xb") as outgoing:
        shutil.copyfileobj(incoming, outgoing, CHUNK)
    _require_fingerprint(target, expected)


def _load_source(release):
    inventory = release / "inventory" / "inventory.jsonl"
    lock_path = release / "inventory" / "inventory.lock.json"
    raw = inventory.read_bytes()
    lock = _json(lock_path)
    if hashlib.sha256(raw).hexdigest() != lock.get("inventory_sha256"):
        raise ValueError("inventory bytes do not match the release lock")
    rows = [
        json.loads(line, object_pairs_hook=_unique_object)
        for line in raw.decode("utf-8").splitlines() if line
    ]
    if len(rows) != lock.get("records"):
        raise ValueError("inventory record count does not match the release lock")
    disk = _records([row for row in rows if row.get("scope") != "asar-member"], "source files")
    members = []
    for row in rows:
        if row.get("scope") == "asar-member":
            expected = _record({"path": row.get("member_path"), "size": row.get("size"), "sha256": row.get("sha256")})
            if type(row.get("offset")) is not int or row["offset"] < 0:
                raise ValueError(f"invalid ASAR member offset: {expected['path']}")
            members.append({**expected, "offset": row["offset"]})
    _records(members, "ASAR members")
    anchors = lock.get("anchors_sha256")
    by_path = {item["path"]: item for item in disk}
    if not isinstance(anchors, dict) or not anchors:
        raise ValueError("release lock has no anchors")
    for name, sha in anchors.items():
        if name not in by_path or by_path[name]["sha256"] != sha:
            raise ValueError(f"release anchor does not match inventory: {name}")
    return inventory, lock_path, lock, disk, members


def _readable(relative):
    if relative == "app.asar" or relative == "runtime/manifest.json":
        return True
    if relative.startswith(("runtime/dist/", "runtime/templates/", "runtime/support/")):
        return True
    if relative.startswith("runtime/prebuilt-skills/"):
        name = Path(relative).name.casefold()
        return Path(relative).suffix.casefold() in TEXT_SUFFIXES or name.startswith(("license", "copying", "notice"))
    return relative.endswith(("codex-package.json", "/LICENSE", "/LICENSE.txt", "/NOTICE", "/NOTICE.txt"))


def _artifact(path, reference_root, role, source_path=None):
    relative = path.relative_to(reference_root).as_posix()
    result = {**_fingerprint(path, relative), "role": role}
    if source_path is not None:
        result["source_path"] = source_path
    return result


def export_reference(release_dir, resources_root, installer, output_dir):
    release = Path(release_dir).absolute()
    source = Path(resources_root).absolute()
    installer = Path(installer).absolute()
    _directory(release)
    _directory(source)
    _regular(installer)
    release, source = release.resolve(strict=True), source.resolve(strict=True)
    output = Path(output_dir).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError("export output must not already exist")
    _require_disjoint(output, source, "source resources")
    for directory in ("inventory", "extraction"):
        _require_disjoint(output, release / directory, "locked release input")
    inventory, lock_path, source_lock, records, members = _load_source(release)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".hi3d-reference-", dir=output.parent))
    try:
        artifacts = []
        for name, original in (("inventory.jsonl", inventory), ("inventory.lock.json", lock_path)):
            target = staging / "raw" / "metadata" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(original.read_bytes())
            artifacts.append(_artifact(target, staging, "release-inventory"))
        archive = staging / ARCHIVE
        archive.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as packed:
            for expected in records:
                original = _within(source, expected["path"])
                _require_fingerprint(original, expected)
                info = zipfile.ZipInfo("resources/" + expected["path"], date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                digest = hashlib.sha256()
                size = 0
                with original.open("rb") as incoming, packed.open(info, "w", force_zip64=True) as outgoing:
                    while chunk := incoming.read(CHUNK):
                        size += len(chunk)
                        digest.update(chunk)
                        outgoing.write(chunk)
                if size != expected["size"] or digest.hexdigest() != expected["sha256"]:
                    raise ValueError(f"source changed while archiving: {expected['path']}")
                if _readable(expected["path"]):
                    target = staging / "raw" / "resources" / expected["path"]
                    _copy_verified(original, target, expected)
                    artifacts.append(_artifact(target, staging, "resource-original", expected["path"]))
        archive_record = _artifact(archive, staging, "complete-resources-archive")
        artifacts.append(archive_record)
        app = staging / "raw" / "resources" / "app.asar"
        with app.open("rb") as stream:
            for member in members:
                stream.seek(member["offset"])
                data = stream.read(member["size"])
                if len(data) != member["size"] or hashlib.sha256(data).hexdigest() != member["sha256"]:
                    raise ValueError(f"ASAR member bytes mismatch: {member['path']}")
                target = _within(staging, "raw/app-members/" + member["path"])
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                artifacts.append(_artifact(target, staging, "asar-member-original", "app.asar/" + member["path"]))
        install_record = _fingerprint(installer, installer.name)
        install_target = _within(staging, "packages/" + installer.name)
        _copy_verified(installer, install_target, install_record)
        artifacts.append(_artifact(install_target, staging, "captured-installer"))
        expected_names = {item["path"] for item in records}
        exclusions = []
        for path in sorted(source.rglob("*")):
            if path.is_file() and path.relative_to(source).as_posix() not in expected_names:
                exclusions.append({"path": path.relative_to(source).as_posix(), "reason": "not in fixed release inventory"})
        manifest = {
            "schema_version": 1,
            "reference_version": source_lock.get("disk", {}).get("runtime_version"),
            "platform": source_lock.get("disk", {}).get("platform"),
            "arch": source_lock.get("disk", {}).get("arch"),
            "source_inventory": {
                "path": "raw/metadata/inventory.jsonl",
                "sha256": hashlib.sha256(inventory.read_bytes()).hexdigest(),
                "lock_path": "raw/metadata/inventory.lock.json",
                "lock_sha256": hashlib.sha256(lock_path.read_bytes()).hexdigest(),
            },
            "archive": {**_record(archive_record), "root": "resources/"},
            "resources": records,
            "artifacts": sorted(artifacts, key=lambda item: item["path"]),
            "exclusions": exclusions,
            "boundaries": {
                "installer_release_equivalence": "captured installer identity only; not inferred from filename",
                "execution": "reference evidence, not a Debian runtime",
                "cache": "cache deltas and fixtures are tracked by separate manifests",
                "cloud": "no cloud model implementation is included",
            },
        }
        (staging / LOCK).write_bytes(_json_bytes(manifest))
        verify_reference(staging)
        if output.exists():
            raise ValueError("export output appeared during publication")
        staging.rename(output)
        return {"reference_dir": str(output), "resources": len(records), "artifacts": len(artifacts), "excluded": len(exclusions)}
    finally:
        _cleanup_staging(staging, output.parent, ".hi3d-reference-")


def _load_manifest(reference):
    manifest = _json(_within(reference, LOCK))
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("unsupported reference manifest schema")
    resources = _records(manifest.get("resources"), "resource records")
    artifacts = _records(manifest.get("artifacts"), "artifact records")
    archive = _record(manifest.get("archive"))
    if manifest["archive"].get("root") != "resources/" or archive["path"] != ARCHIVE:
        raise ValueError("unexpected resources archive layout")
    artifacts_by_path = {item["path"]: item for item in artifacts}
    if artifacts_by_path.get(archive["path"]) != archive:
        raise ValueError("archive does not match artifact record")
    return manifest, resources, artifacts


def _verify_inventory(reference, manifest, resources):
    source = manifest.get("source_inventory")
    if not isinstance(source, dict):
        raise ValueError("missing source inventory")
    raw_path = _within(reference, source.get("path"))
    lock_path = _within(reference, source.get("lock_path"))
    raw = raw_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != source.get("sha256"):
        raise ValueError("reference inventory digest mismatch")
    if _fingerprint(lock_path, source["lock_path"])["sha256"] != source.get("lock_sha256"):
        raise ValueError("reference source lock digest mismatch")
    lock = _json(lock_path)
    if lock.get("inventory_sha256") != source.get("sha256"):
        raise ValueError("reference inventory does not match source lock")
    rows = [json.loads(line, object_pairs_hook=_unique_object) for line in raw.decode("utf8").splitlines() if line]
    if lock.get("records") != len(rows):
        raise ValueError("reference source inventory record count mismatch")
    disk = _records([row for row in rows if row.get("scope") != "asar-member"], "inventory files")
    if resources != disk:
        raise ValueError("resource list differs from fixed inventory")


def _verify_resource_tree(root, records):
    _directory(root)
    expected = {item["path"] for item in records}
    actual = set()
    for path in root.rglob("*"):
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            _directory(path)
        else:
            _regular(path)
            actual.add(path.relative_to(root).as_posix())
    if actual != expected:
        raise ValueError("materialized resources file set differs from manifest")
    for record in records:
        _require_fingerprint(_within(root, record["path"]), record)


def verify_reference(reference_dir, resources_root=None):
    reference = Path(reference_dir).absolute()
    _directory(reference)
    reference = reference.resolve(strict=True)
    manifest, resources, artifacts = _load_manifest(reference)
    for record in artifacts:
        _require_fingerprint(_within(reference, record["path"]), record)
    _verify_inventory(reference, manifest, resources)
    if resources_root is not None:
        _verify_resource_tree(Path(resources_root).absolute(), resources)
    return {"verified": True, "reference_version": manifest.get("reference_version"),
            "resources": len(resources), "artifacts": len(artifacts),
            "materialized_resources_verified": resources_root is not None}


def materialize_reference(reference_dir, output_dir):
    reference = Path(reference_dir).absolute()
    _directory(reference)
    reference = reference.resolve(strict=True)
    verify_reference(reference)
    manifest, resources, _ = _load_manifest(reference)
    output = Path(output_dir).absolute()
    if output.exists() or output.is_symlink():
        _directory(output)
        if {path.name for path in output.iterdir()} != {"resources"}:
            raise ValueError("existing materialization target has unexpected entries")
        _verify_resource_tree(output / "resources", resources)
        return {"resources_root": str(output / "resources"), "reused": True}
    _require_disjoint(output, reference, "reference directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".hi3d-materialize-", dir=output.parent))
    try:
        expected = {"resources/" + item["path"]: item for item in resources}
        with zipfile.ZipFile(_within(reference, manifest["archive"]["path"])) as archive:
            infos = archive.infolist()
            seen = set()
            for info in infos:
                relative = _relative_path(info.filename, "ZIP member")
                folded = relative.casefold()
                if folded in seen:
                    raise ValueError(f"duplicate ZIP member: {relative}")
                seen.add(folded)
                mode = info.external_attr >> 16
                if info.is_dir() or (mode and stat.S_IFMT(mode) not in (0, stat.S_IFREG)):
                    raise ValueError(f"non-regular ZIP member: {relative}")
                record = expected.get(relative)
                if record is None or info.file_size != record["size"]:
                    raise ValueError(f"unexpected ZIP member or size: {relative}")
                if info.flag_bits & 1:
                    raise ValueError(f"encrypted ZIP member: {relative}")
            if {info.filename for info in infos} != set(expected):
                raise ValueError("ZIP file set differs from manifest")
            for info in infos:
                target = _within(staging, info.filename)
                target.parent.mkdir(parents=True, exist_ok=True)
                size, digest = 0, hashlib.sha256()
                with archive.open(info) as incoming, target.open("xb") as outgoing:
                    while chunk := incoming.read(CHUNK):
                        size += len(chunk)
                        if size > expected[info.filename]["size"]:
                            raise ValueError(f"ZIP member exceeds expected size: {info.filename}")
                        digest.update(chunk)
                        outgoing.write(chunk)
                if size != expected[info.filename]["size"] or digest.hexdigest() != expected[info.filename]["sha256"]:
                    raise ValueError(f"ZIP member SHA-256 mismatch: {info.filename}")
        _verify_resource_tree(staging / "resources", resources)
        if output.exists():
            raise ValueError("materialization target appeared during publication")
        staging.rename(output)
        return {"resources_root": str(output / "resources"), "reused": False}
    finally:
        _cleanup_staging(staging, output.parent, ".hi3d-materialize-")


def main_export(argv=None):
    parser = argparse.ArgumentParser(description="Export fixed Hi3D bytes and a portable reference manifest.")
    parser.add_argument("--release-dir", required=True, type=Path)
    parser.add_argument("--resources-root", required=True, type=Path)
    parser.add_argument("--installer", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    return _run(export_reference, args.release_dir, args.resources_root, args.installer, args.output_dir)


def main_materialize(argv=None):
    parser = argparse.ArgumentParser(description="Verify and safely materialize the fixed resources ZIP.")
    parser.add_argument("--reference-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    return _run(materialize_reference, args.reference_dir, args.output_dir)


def main_verify(argv=None):
    parser = argparse.ArgumentParser(description="Verify reference artifacts and optionally materialized resources.")
    parser.add_argument("--reference-dir", required=True, type=Path)
    parser.add_argument("--resources-root", type=Path)
    args = parser.parse_args(argv)
    return _run(verify_reference, args.reference_dir, args.resources_root)


def _run(function, *args):
    try:
        result = function(*args)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0
