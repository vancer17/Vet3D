"""Task schema for inspect, compare, and roundtrip verification."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

SCHEMA_VERSION = 1
MODES = {"inspect", "compare", "roundtrip"}
DOCUMENT_TYPES = {"drawing", "part", "assembly", "drawing_sheet", "exchange_solid"}
OPERATIONS = {"read", "copy", "roundtrip", "edit_probe", "repair", "convert"}
ADAPTERS = {"freecad", "mock"}
CREDENTIAL_NAMES = {".env", "id_rsa", "id_ed25519", "credentials.json"}


def _reject_credential(path):
    name = Path(path).name
    if name in CREDENTIAL_NAMES or name.endswith((".pem", ".key")):
        raise ValueError("refusing a credential-like input path")


def resolve_file(value, base):
    if not isinstance(value, str) or not value:
        raise ValueError("file path must be a non-empty string")
    _reject_credential(value)
    path = Path(value)
    if not path.is_absolute():
        path = Path(base) / path
    if not path.exists():
        raise ValueError("input file does not exist: " + path.name)
    if path.is_dir():
        raise ValueError("input path is a directory: " + path.name)
    return path


def _environment(value, label):
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ValueError(label + " must be an object")
    allowed = {"software", "version", "build", "platform"}
    if set(value) - allowed:
        raise ValueError(label + " has an unknown field")
    return {
        "software": str(value.get("software") or ""),
        "version": str(value.get("version") or ""),
        "build": str(value.get("build") or ""),
        "platform": str(value.get("platform") or ""),
    }


def _changes(value):
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("expected_changes must be a list")
    changes = []
    for item in value:
        if not isinstance(item, dict) or set(item) - {"path", "value"}:
            raise ValueError("expected change requires path and value")
        if not isinstance(item.get("path"), str) or not item["path"]:
            raise ValueError("expected change path is empty")
        changes.append({"path": item["path"], "value": item["value"]})
    return changes


def _dependencies(value, base):
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("dependencies must be a list")
    deps = []
    for item in value:
        if not isinstance(item, dict) or not item.get("id") or not item.get("path"):
            raise ValueError("dependency requires id and path")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", str(item["id"])):
            raise ValueError("invalid dependency id")
        _reject_credential(item["path"])
        path = Path(item["path"])
        if not path.is_absolute():
            path = Path(base) / path
        deps.append({"id": str(item["id"]), "path": str(path), "exists": path.is_file() and not path.is_dir()})
    return deps


def _upstream(value):
    if value is None:
        return {"tool": "not-specified", "version": "", "session_evidence_refs": []}
    if not isinstance(value, dict) or set(value) - {"tool", "version", "session_evidence_refs"}:
        raise ValueError("upstream_build must be an object with tool, version, session_evidence_refs")
    tool = str(value.get("tool") or "not-specified")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", tool):
        raise ValueError("invalid upstream tool")
    version = value.get("version")
    if version is None:
        version = ""
    if not isinstance(version, str):
        raise ValueError("upstream version must be a string")
    return {
        "tool": tool,
        "version": version,
        "session_evidence_refs": _string_list(value.get("session_evidence_refs"), "session_evidence_refs"),
    }


def _string_list(value, label):
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(label + " must be a list of strings")
    return list(value)


def validate_task(data, base):
    if not isinstance(data, dict):
        raise ValueError("task must be an object")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("schema_version must be 1")
    allowed = {
        "schema_version", "mode", "source", "candidate", "target", "document_type",
        "required_preservation", "expected_changes", "dependencies", "tolerances",
        "allowed_operations", "excluded_checks", "freecad", "budget_seconds",
        "adapter", "require_native", "repair", "registry", "mock_snapshots", "upstream_build",
    }
    if set(data) - allowed:
        raise ValueError("unknown task field")
    mode = data.get("mode")
    if mode not in MODES:
        raise ValueError("mode must be inspect, compare, or roundtrip")
    document_type = data.get("document_type")
    if document_type is not None and document_type not in DOCUMENT_TYPES:
        raise ValueError("unknown document_type")
    adapter = data.get("adapter") or "freecad"
    if adapter not in ADAPTERS:
        raise ValueError("unknown adapter")
    operations = _string_list(data.get("allowed_operations"), "allowed_operations") or ["read", "copy"]
    if any(item not in OPERATIONS for item in operations):
        raise ValueError("unknown allowed operation")
    if "read" not in operations:
        operations.insert(0, "read")
    tolerances = data.get("tolerances") or {}
    if not isinstance(tolerances, dict):
        raise ValueError("tolerances must be an object")
    for key, value in tolerances.items():
        if not isinstance(key, str) or isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("tolerance must be a named number")
    budget = data.get("budget_seconds", 120)
    if isinstance(budget, bool) or not isinstance(budget, (int, float)) or budget <= 0:
        raise ValueError("budget_seconds must be a positive number")
    candidate = resolve_file(data.get("candidate"), base)
    source = None
    if data.get("source"):
        source = resolve_file(data["source"], base)
    if mode == "compare" and source is None:
        raise ValueError("compare requires a source baseline")
    mock = data.get("mock_snapshots")
    if mock is not None and adapter != "mock":
        raise ValueError("mock snapshots are only valid for the mock adapter")
    if adapter == "mock" and not isinstance(mock, dict):
        raise ValueError("mock adapter requires mock_snapshots")
    target = _environment(data.get("target"), "target")
    if adapter == "freecad" and not target["software"]:
        target["software"] = "FreeCAD"
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "candidate": candidate,
        "source": source,
        "target": target,
        "document_type": document_type,
        "required_preservation": _string_list(data.get("required_preservation"), "required_preservation"),
        "expected_changes": _changes(data.get("expected_changes")),
        "dependencies": _dependencies(data.get("dependencies"), base),
        "tolerances": tolerances,
        "allowed_operations": operations,
        "excluded_checks": _string_list(data.get("excluded_checks"), "excluded_checks"),
        "freecad": str(data.get("freecad") or ""),
        "budget_seconds": float(budget),
        "adapter": adapter,
        "require_native": bool(data.get("require_native", True)),
        "repair": bool(data.get("repair", False)),
        "registry": data.get("registry"),
        "mock_snapshots": mock if adapter == "mock" else None,
        "upstream_build": _upstream(data.get("upstream_build")),
    }


def load_task(path):
    file_path = Path(path)
    data = json.loads(file_path.read_text(encoding="utf-8"))
    task = validate_task(data, file_path.parent)
    task["task_path"] = file_path.resolve()
    return task


def digest_file(path):
    hasher = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def fingerprint(task):
    payload = {
        "mode": task["mode"],
        "candidate": digest_file(task["candidate"]),
        "source": digest_file(task["source"]) if task["source"] else None,
        "target": task["target"],
        "document_type": task["document_type"],
        "required_preservation": task["required_preservation"],
        "expected_changes": task["expected_changes"],
        "dependencies": [{k: item[k] for k in ("id", "path", "exists")} for item in task["dependencies"]],
        "tolerances": task["tolerances"],
        "allowed_operations": task["allowed_operations"],
        "excluded_checks": task["excluded_checks"],
        "adapter": task["adapter"],
        "freecad_supplied": bool(task["freecad"]),
        "require_native": task["require_native"],
        "repair": task["repair"],
        "upstream_build": task["upstream_build"],
        "profile_revision": "1",
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
