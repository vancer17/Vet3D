"""FreeCAD is the first software-series adapter. Unimplemented capabilities stay off."""
from __future__ import annotations

import json
import os
from pathlib import Path

from readers import read_static
from snapshot import cell, read_items

ADAPTER_ID = "freecad-native"
ADAPTER_VERSION = "1"
IMPLEMENTED = {
    "identify": True,
    "open_native": True,
    "read_layers": True,
    "read_objects": True,
    "read_parameters": False,
    "read_features": True,
    "read_assembly_relations": False,
    "resolve_dependencies": True,
    "save_copy": True,
    "reopen_copy": True,
    "rebuild_copy": False,
    "edit_probe": False,
}
NEEDS_FREECAD = {"open_native", "save_copy", "reopen_copy"}
NATIVE_SOFTWARE = "FreeCAD"


class FreecadAdapter:
    id = ADAPTER_ID
    version = ADAPTER_VERSION

    def __init__(self):
        self.snapshots = 0

    def probe(self, task):
        software = task["target"].get("software") or ""
        supported = software == NATIVE_SOFTWARE
        path = task.get("freecad") or ""
        binary_ready = bool(path) and Path(path).is_file() and os.access(path, os.X_OK)
        runnable = supported and binary_ready
        if not supported:
            blocked = "没有" + software + "的原生适配器。ClassCAD 或其他源端检查不能代替该软件中的打开、重开和编辑探针；这不是文件不兼容的证据"
        elif not binary_ready:
            blocked = "目标软件不可用，原生打开未执行；这不是文件不兼容的证据"
        else:
            blocked = ""
        executable = {}
        for name, implemented in IMPLEMENTED.items():
            executable[name] = bool(implemented and (name not in NEEDS_FREECAD or runnable))
        return {
            "software": NATIVE_SOFTWARE,
            "version": task["target"].get("version") or "",
            "build": task["target"].get("build") or "",
            "platform": task["target"].get("platform") or "",
            "freecad_runnable": runnable,
            "target_supported": supported,
            "blocked_reason": blocked,
            "implemented": dict(IMPLEMENTED),
            "executable": executable,
        }

    def snapshot(self, path, task, workspace, runner=None, native_result=None):
        self.snapshots += 1
        snap = read_static(path)
        probe = self.probe(task)
        if native_result is not None:
            _merge_native(snap, native_result)
            return snap
        if not probe["freecad_runnable"]:
            snap["open"] = {
                "native": False,
                "status": "blocked",
                "recovered": None,
                "reason": probe.get("blocked_reason") or "未提供可执行的 FreeCAD，原生打开未执行",
            }
            return snap
        try:
            native = self._kernel(path, task, workspace, "snapshot", runner)
        except Exception as exc:
            if exc.__class__.__name__ == "BudgetTimeout":
                snap["open"] = {"native": True, "status": "blocked", "recovered": None, "reason": "原生打开达到墙钟预算并已停止"}
                snap["warnings"].append(snap["open"]["reason"])
                return snap
            raise
        _merge_native(snap, native)
        return snap

    def roundtrip(self, path, task, workspace, source_realpath, runner=None):
        saved = Path(workspace) / "roundtrip" / Path(path).name
        saved.parent.mkdir(parents=True, exist_ok=True)
        first = self._kernel(path, task, workspace, "save_copy", runner, dest=saved, source_realpath=source_realpath)
        second = self._kernel(saved, task, workspace, "snapshot", runner, source_realpath=source_realpath)
        unexpected = []
        first_names = {item["name"] for item in first.get("objects") or []}
        second_names = {item["name"] for item in second.get("objects") or []}
        if first_names != second_names:
            unexpected.append({"path": "roundtrip.objects", "reason": "重新打开后的对象标识与保存前不一致"})
            status, reason = "fail", "保存后重新打开的对象标识发生了变化"
        else:
            status, reason = "pass", "已在隔离副本中保存并重新打开。这只证明本次无头往返，不替代语义校对。"
        return {"status": status, "reason": reason, "unexpected": unexpected, "saved": str(saved), "reopened": True}

    def _kernel(self, path, task, workspace, op, runner, dest=None, source_realpath=None):
        from freecad_kernel import assert_workspace_write

        call = Path(workspace) / "native" / op
        if call.exists():
            call = Path(workspace) / "native" / (op + "-" + Path(path).name)
        call.mkdir(parents=True, exist_ok=True)
        source = source_realpath or path
        spec = {
            "op": op,
            "path": str(path),
            "workspace": str(workspace),
            "source_realpath": str(source),
            "budget_seconds": task["budget_seconds"],
            "freecad": task["freecad"],
        }
        if dest is not None:
            assert_workspace_write(dest, workspace, source)
            spec["dest"] = str(dest)
        request = call / "request.json"
        request.write_text(json.dumps(spec), encoding="utf-8")
        (call / "budget.json").write_text(
            json.dumps({"max_wall_seconds": task["budget_seconds"]}) + "\n",
            encoding="utf-8",
        )
        kernel = Path(__file__).with_name("freecad_kernel.py")
        boot = call / "boot.py"
        boot.write_text(
            "import runpy\nrunpy.run_path(%r, init_globals={'SPEC': %r, 'OUT': %r})\n"
            % (str(kernel), str(request), str(call)),
            encoding="utf-8",
        )
        log = call / "log.txt"
        heartbeat = call / "heartbeat.json"
        if runner is None:
            from process_run import run_budgeted
            runner = run_budgeted
        runner(
            [task["freecad"], str(boot)],
            log,
            max_wall_seconds=task["budget_seconds"],
            heartbeat_path=heartbeat,
        )
        native_path = call / "native.json"
        if not native_path.is_file():
            raise OSError("native snapshot missing")
        return json.loads(native_path.read_text(encoding="utf-8"))


class MockAdapter:
    id = "mock"
    version = "0"

    def __init__(self):
        self.snapshots = 0

    def probe(self, task):
        return {
            "software": "Mock",
            "version": "",
            "build": "",
            "platform": "",
            "freecad_runnable": False,
            "implemented": {key: False for key in IMPLEMENTED},
            "executable": {key: False for key in IMPLEMENTED},
        }

    def snapshot(self, path, task, workspace, runner=None, native_result=None):
        self.snapshots += 1
        snaps = task["mock_snapshots"]
        key = "source" if _is_source(path, task) else "candidate"
        return json.loads(json.dumps(snaps[key]))


def _is_source(path, task):
    return Path(path).parent.name == "source"


def _merge_native(snap, native):
    snap["evidence_origin"] = "native"
    snap["open"] = {
        "native": True,
        "status": "fail" if native.get("recovered") or native.get("opener_invoked_repair") else "pass",
        "recovered": bool(native.get("recovered") or native.get("opener_invoked_repair")),
        "reason": "无头打开返回了文档对象" if not native.get("recovered") else "打开过程报告了恢复",
    }
    geometry = {}
    for item in native.get("objects") or []:
        if "volume" not in item:
            continue
        geometry[item["name"]] = {
            "volume": cell(item["volume"]),
            "solids": cell(item.get("solids")),
            "placement": cell(item.get("placement")),
        }
    if geometry:
        snap["geometry"] = read_items(geometry, "FreeCAD Shape")
        snap["placement"] = read_items({name: {"placement": attrs["placement"]} for name, attrs in geometry.items()})
    if native.get("version"):
        snap["native_environment"] = {
            "software": native.get("software") or "FreeCAD",
            "version": native.get("version") or "",
            "build": native.get("build") or "",
        }
    for warning in native.get("warnings") or []:
        snap["warnings"].append(warning)
