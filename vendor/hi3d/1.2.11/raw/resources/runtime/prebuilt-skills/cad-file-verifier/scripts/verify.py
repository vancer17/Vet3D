"""Orchestrate a CAD verification without modifying the caller's originals."""
from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from adapter import FreecadAdapter, MockAdapter
from compare import build_checks
from report import render_report
from registry import append_record
from snapshot import INFER_TYPE
from task import fingerprint, load_task
from workspace import external_reference_paths, prepare_workspace, unchanged

WAITING_CHOICES = [
    {"id": "run_check", "title": "按当前输入验收"},
    {"id": "review_done", "title": "已有结果，只核对"},
    {"id": "back_report", "title": "回退到读取检查点"},
]


def execute(task_path, output, registry=None, adapter=None, runner=None):
    task = load_task(task_path)
    if registry:
        task["registry"] = registry
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    signature = fingerprint(task)
    cached = _reuse(output, signature)
    if cached is not None:
        return cached
    adapter = adapter or (MockAdapter() if task["adapter"] == "mock" else FreecadAdapter())
    prepared = prepare_workspace(output, task)
    _write(output / "workspace.json", _public_workspace(prepared))
    probe = adapter.probe(task)
    _write(output / "scope.json", {
        "mode": task["mode"],
        "target": task["target"],
        "upstream_build": task["upstream_build"],
        "probe": probe,
        "fingerprint": signature,
    })
    candidate_copy = prepared["copied"]["candidate"]["workspace_path"]
    candidate = adapter.snapshot(candidate_copy, task, prepared["root"], runner=runner)
    source = None
    if "source" in prepared["copied"]:
        source = adapter.snapshot(prepared["copied"]["source"]["workspace_path"], task, prepared["root"], runner=runner)
        _write(output / "source-snapshot.json", source)
    _write(output / "candidate-snapshot.json", candidate)
    document_type = task["document_type"]
    if document_type is None and candidate["format"]["confidence"] == "high":
        document_type = INFER_TYPE.get(candidate["format"]["id"])
    external = external_reference_paths(candidate, task["candidate"].parent, prepared["root"])
    roundtrip = None
    timed_out = "预算" in ((candidate.get("open") or {}).get("reason") or "")
    if task["mode"] == "roundtrip" and "roundtrip" in task["allowed_operations"] and probe["executable"].get("save_copy"):
        try:
            roundtrip = adapter.roundtrip(
                candidate_copy, task, prepared["root"], task["candidate"].resolve(), runner=runner
            )
        except Exception as exc:
            if exc.__class__.__name__ != "BudgetTimeout":
                raise
            timed_out = True
            roundtrip = {"status": "blocked", "reason": "保存往返达到墙钟预算并已停止", "unexpected": []}
    if timed_out:
        _write(output / "waiting.json", {
            "schema": "cad-file-verifier.waiting.v1",
            "reason": "timeout",
            "choices": WAITING_CHOICES,
        })
    info = {
        "outside_dependencies": prepared["outside_dependencies"],
        "external_refs": external,
        "source_unchanged": unchanged(prepared["copied"]),
    }
    judged = build_checks(task, document_type, candidate, source, info, roundtrip, probe)
    _write(output / "compare.json", judged)
    native_env = candidate.get("native_environment") or {}
    target = {
        "software": task["target"]["software"],
        "version": native_env.get("version") or task["target"]["version"],
        "build": native_env.get("build") or task["target"]["build"],
        "platform": task["target"]["platform"],
    }
    coverage = _coverage(task, candidate, probe)
    confirmation = _confirmation(task)
    native_check = next((item for item in judged["checks"] if item["id"] == "native_open"), {})
    evidence = [name for name in (
        "candidate-snapshot.json", "source-snapshot.json", "compare.json", "workspace.json", "scope.json"
    ) if (output / name).is_file()]
    result = {
        "schema_version": 1,
        "completed": True,
        "reused": False,
        "fingerprint": signature,
        "overall_status": judged["overall_status"],
        "counts_as_measured_pass": (
            judged["overall_status"] == "pass"
            and task["adapter"] != "mock"
            and probe.get("target_supported", True)
        ),
        "mock": task["adapter"] == "mock",
        "coverage_scope": coverage,
        "upstream_build": task["upstream_build"],
        "target": target,
        "document_type": document_type,
        "checks": judged["checks"],
        "profile": judged["profile"],
        "omitted_checks": judged["omitted_checks"],
        "excluded_checks": task["excluded_checks"],
        "expected_confirmed": judged["expected_confirmed"],
        "unexpected": judged["unexpected"],
        "needs_confirmation": confirmation,
        "repairs_performed": False,
        "registry_updated": False,
        "registry_error": "",
        "source_unchanged": info["source_unchanged"],
        "native_reason": (candidate.get("open") or {}).get("reason") or native_check.get("reason") or "",
        "evidence_index": evidence,
        "report_path": str(output / "report.md"),
    }
    report_text = render_report(result)
    (output / "report.md").write_text(report_text, encoding="utf-8")
    result["evidence_index"] = ["report.md", *evidence]
    registry_dir = task.get("registry")
    if registry_dir:
        try:
            saved = append_record(registry_dir, _record(result, task, candidate, target))
            result["registry_updated"] = bool(saved["record_appended"])
            if not saved["view_updated"]:
                result["registry_error"] = "记录已追加，聚合视图未更新"
        except OSError as exc:
            result["registry_updated"] = False
            result["registry_error"] = "兼容记录未更新"
            result["coverage_scope"] = result["coverage_scope"] + " 兼容记录未更新。"
            report_text = render_report(result)
            (output / "report.md").write_text(report_text, encoding="utf-8")
            _ = exc
    elif "兼容记录未更新" not in report_text:
        result["registry_error"] = "未指定兼容记录目录"
    _write(output / "result.json", result)
    return result


def _reuse(output, signature):
    path = Path(output) / "result.json"
    if not path.is_file():
        return None
    existing = json.loads(path.read_text(encoding="utf-8"))
    if existing.get("fingerprint") != signature or not existing.get("completed"):
        raise ValueError("output directory already has a different result")
    reused = dict(existing)
    reused["reused"] = True
    return reused


def _coverage(task, candidate, probe):
    fmt = (candidate.get("format") or {}).get("id") or "未识别格式"
    if task["adapter"] == "mock":
        return "模拟流程，不记入实测通过。"
    native = "已执行无头打开。" if probe.get("freecad_runnable") and (candidate.get("open") or {}).get("status") == "pass" else "原生打开未作为通过证据。"
    extra = ""
    if not probe.get("target_supported", True):
        extra += "本次适配器不能验收所声明的目标软件。"
    if task["upstream_build"]["tool"] == "classcad":
        extra += "ClassCAD 源端证据另列，不证明第三方原生工程的图层、特征、约束或装配关系。"
    return "本次覆盖 " + fmt + " 的静态读取。" + native + extra + "结论只对本次文件和已检查项目成立。"


def _confirmation(task):
    if not task["repair"]:
        return None
    if "repair" not in task["allowed_operations"]:
        return {"action": "repair", "effect": "修复超出已有授权，未改动副本"}
    return {"action": "repair", "effect": "已授权但当前适配器不能修复，未改动副本"}


def _record(result, task, candidate, target):
    kind = "mock" if task["adapter"] == "mock" else "measured"
    return {
        "schema_version": 1,
        "record_id": uuid.uuid4().hex,
        "record_kind": kind,
        "evidence_origin": kind,
        "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_environment": target,
        "target_environment": target,
        "document": {
            "type": result["document_type"],
            "format": (candidate.get("format") or {}).get("id"),
            "format_version": (candidate.get("format") or {}).get("version"),
            "sample_id": result["fingerprint"][:16],
        },
        "adapter": {
            "id": "mock" if task["adapter"] == "mock" else "freecad-native",
            "version": "0" if task["adapter"] == "mock" else "1",
        },
        "check_profile": result["profile"],
        "expected_changes": task["expected_changes"],
        "checks": result["checks"],
        "overall_status": result["overall_status"],
        "upstream_build": result["upstream_build"],
        "coverage_scope": result["coverage_scope"],
        "evidence_index": result["evidence_index"],
        "supersedes": None,
    }


def _public_workspace(prepared):
    return {
        "root": str(prepared["root"]),
        "copied": {key: str(value["workspace_path"]) for key, value in prepared["copied"].items()},
        "outside_dependencies": prepared["outside_dependencies"],
    }


def _write(path, payload):
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verify a CAD file and write a local report")
    parser.add_argument("--task", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--registry", default="")
    args = parser.parse_args(argv)
    try:
        result = execute(args.task, args.output, registry=args.registry or None)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({
        "overall_status": result["overall_status"],
        "report": result["report_path"],
        "registry_updated": result["registry_updated"],
        "reused": result["reused"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
