"""Copy inputs into a workspace without writing back to the originals."""
from __future__ import annotations

import shutil
from pathlib import Path

from freecad_kernel import assert_workspace_write
from task import digest_file


def prepare_workspace(output, task):
    root = Path(output) / "workspace"
    root.mkdir(parents=True, exist_ok=True)
    copied = {"candidate": _isolate(task["candidate"], root / "candidate", root)}
    if task["source"]:
        copied["source"] = _isolate(task["source"], root / "source", root)
    outside = []
    for dep in task["dependencies"]:
        path = Path(dep["path"])
        if not dep["exists"]:
            outside.append({"id": dep["id"], "path": str(path), "missing": True})
            continue
        before = digest_file(path)
        _isolate(path, root / "dependencies" / dep["id"], root)
        if digest_file(path) != before:
            raise ValueError("dependency bytes changed while copying")
        if not _inside(path.resolve(), root):
            outside.append({"id": dep["id"], "path": str(path.resolve()), "missing": False})
    return {"root": root, "copied": copied, "outside_dependencies": outside}


def _isolate(src, dest_dir, workspace):
    src = Path(src)
    before = digest_file(src)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if dest.exists() or dest.is_symlink():
        raise ValueError("refusing to overwrite a workspace file")
    if workspace.resolve() not in dest_dir.resolve().parents and dest_dir.resolve() != workspace.resolve():
        raise ValueError("copy destination escaped workspace")
    shutil.copyfile(src, dest)
    if dest.is_symlink():
        dest.unlink()
        raise ValueError("refusing a symlink inside the workspace")
    if digest_file(src) != before:
        raise ValueError("source bytes changed while copying")
    return {
        "workspace_path": dest,
        "source_hash": before,
        "was_symlink": src.is_symlink(),
        "source_path": src,
    }


def unchanged(copies):
    for item in copies.values():
        if digest_file(item["source_path"]) != item["source_hash"]:
            return False
    return True


def _inside(path, root):
    path = Path(path).resolve()
    root = Path(root).resolve()
    return path == root or root in path.parents


def external_reference_paths(snapshot, candidate_dir, workspace):
    """Paths still stored in the document that resolve outside the workspace."""
    found = []
    field = snapshot.get("dependencies") or {}
    items = field.get("items") or {}
    if field.get("status") != "read":
        return found
    for item_id, attrs in items.items():
        path_cell = attrs.get("path") or {}
        if path_cell.get("status") != "read":
            continue
        raw = Path(str(path_cell.get("value")))
        resolved = raw if raw.is_absolute() else Path(candidate_dir) / raw
        try:
            resolved = resolved.resolve()
        except OSError:
            found.append({"id": item_id, "path": str(raw), "missing": True})
            continue
        if not _inside(resolved, workspace):
            found.append({"id": item_id, "path": str(resolved), "missing": not resolved.is_file()})
    return found
