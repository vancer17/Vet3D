"""FreeCAD opener. Importing this module does not import FreeCAD."""
from __future__ import annotations

import json
from pathlib import Path


def assert_workspace_write(dest, workspace, source_realpath):
    """Refuse writes through the original path or any path outside the workspace."""
    dest = Path(dest).resolve()
    workspace = Path(workspace).resolve()
    source = Path(source_realpath).resolve()
    if dest == source:
        raise ValueError("refusing write to source")
    if dest != workspace and workspace not in dest.parents:
        raise ValueError("refusing write outside workspace")
    if dest.is_symlink():
        raise ValueError("refusing symlink write")


def _snapshot_document(doc):
    objects = []
    for obj in doc.Objects:
        item = {"name": obj.Name, "type": obj.TypeId, "label": getattr(obj, "Label", obj.Name)}
        shape = getattr(obj, "Shape", None)
        if shape is not None and getattr(shape, "isValid", lambda: False)():
            item["volume"] = float(shape.Volume)
            item["solids"] = len(getattr(shape, "Solids", []) or [])
            base = obj.Placement.Base
            item["placement"] = [float(base.x), float(base.y), float(base.z)]
        objects.append(item)
    return objects


def run(spec, out):
    import FreeCAD as App

    spec = dict(spec)
    out = Path(out)
    source = spec["source_realpath"]
    workspace = spec["workspace"]
    target = Path(spec["path"]).resolve()
    if spec["op"] == "save_copy":
        assert_workspace_write(spec["dest"], workspace, source)
    version = App.Version()
    doc = App.openDocument(str(target))
    try:
        payload = {
            "software": "FreeCAD",
            "version": ".".join(str(part) for part in version[:3]),
            "build": str(version[3] if len(version) > 3 else ""),
            "recovered": False,
            "opener_invoked_repair": False,
            "recovery_observed": None,
            "objects": _snapshot_document(doc),
            "warnings": [],
        }
        if spec["op"] == "save_copy":
            dest = Path(spec["dest"])
            if dest.exists():
                raise ValueError("refusing to overwrite roundtrip copy")
            doc.saveAs(str(dest))
            payload["saved"] = str(dest)
        (out / "native.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    finally:
        App.closeDocument(doc.Name)


def main():
    spec = json.loads(Path(SPEC).read_text(encoding="utf-8"))
    run(spec, OUT)


if "SPEC" in globals() and "OUT" in globals():
    main()
