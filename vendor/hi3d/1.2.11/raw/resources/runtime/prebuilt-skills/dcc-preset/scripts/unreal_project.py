"""Enable catalogued plugins in a .uproject without launching Unreal."""

from __future__ import annotations

import json
from pathlib import Path

from catalog import get_preset, parse_version, version_ok


def load_project(path):
    text = Path(path).read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("uproject is not JSON: %s" % exc) from exc
    if not isinstance(data, dict):
        raise ValueError("uproject must be a JSON object")
    return data


def resolve_version(project, engine_version):
    raw = project.get("EngineAssociation")
    from_file = parse_version(raw) if isinstance(raw, str) else None
    declared = parse_version(engine_version) if engine_version else None
    if engine_version and declared is None:
        raise ValueError("engine version must look like 5.7 or 5.7.1")
    if from_file and declared and from_file != declared:
        return {
            "ok": False,
            "status": "rejected",
            "reason": "engine version conflicts with EngineAssociation",
            "version_source": "conflict",
            "engine_version": None,
        }
    if from_file:
        return {
            "ok": True,
            "version_source": "project",
            "engine_version": from_file,
        }
    if declared:
        return {
            "ok": True,
            "version_source": "caller",
            "engine_version": declared,
        }
    return {
        "ok": False,
        "status": "rejected",
        "reason": "EngineAssociation is not a version; pass the installed engine version",
        "version_source": "missing",
        "engine_version": None,
    }


def merged_plugins(project, names):
    current = project.get("Plugins")
    if current is None:
        current = []
    if not isinstance(current, list):
        raise ValueError("Plugins must be a list")
    plugins = []
    index = {}
    for item in current:
        if not isinstance(item, dict) or not isinstance(item.get("Name"), str):
            raise ValueError("each plugin entry needs a Name")
        plugins.append(dict(item))
        index[item["Name"]] = len(plugins) - 1
    changed = []
    for name in names:
        slot = index.get(name)
        if slot is None:
            plugins.append({"Name": name, "Enabled": True})
            changed.append(name)
            continue
        if plugins[slot].get("Enabled") is not True:
            plugins[slot]["Enabled"] = True
            changed.append(name)
    return plugins, changed


def plan_enable(project, preset_id, engine_version=None):
    preset = get_preset(preset_id)
    if preset is None or preset["operation"] != "enable_plugins":
        raise ValueError("not an Unreal plugin preset: %s" % preset_id)
    resolved = resolve_version(project, engine_version)
    base = {
        "preset": preset_id,
        "plugins": list(preset["plugins"]),
        "version_source": resolved["version_source"],
    }
    if not resolved["ok"]:
        base.update(status=resolved["status"], reason=resolved["reason"], changed=[])
        return base
    found = resolved["engine_version"]
    base["engine_version"] = "%d.%d.%d" % found
    if not version_ok(found, preset["min_version"]):
        base.update(
            status="rejected",
            reason="engine is older than %s" % ".".join(str(part) for part in preset["min_version"]),
            changed=[],
        )
        return base
    plugins, changed = merged_plugins(project, preset["plugins"])
    base.update(status="ready", changed=changed)
    base["_plugins"] = plugins
    return base


def apply_enable(path, preset_id, engine_version=None, write=False):
    project_path = Path(path)
    original = project_path.read_bytes()
    project = load_project(project_path)
    planned = plan_enable(project, preset_id, engine_version)
    plugins = planned.pop("_plugins", None)
    planned["project"] = str(project_path)
    if planned["status"] != "ready":
        return planned
    if not planned["changed"]:
        planned["status"] = "already_enabled"
        return planned
    if not write:
        planned["status"] = "dry_run"
        return planned
    project["Plugins"] = plugins
    encoded = json.dumps(project, ensure_ascii=False, indent=2) + "\n"
    temporary = project_path.with_suffix(project_path.suffix + ".tmp")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(project_path)
    if project_path.read_bytes() == original:
        planned["status"] = "already_enabled"
    else:
        planned["status"] = "applied"
    return planned
