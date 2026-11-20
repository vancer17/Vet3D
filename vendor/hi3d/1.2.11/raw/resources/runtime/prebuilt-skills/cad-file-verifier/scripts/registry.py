"""Append-only compatibility records and a regenerable query view."""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path


def append_record(directory, record):
    directory = Path(directory)
    if directory.exists() and not directory.is_dir():
        raise OSError("registry path is not a directory")
    directory.mkdir(parents=True, exist_ok=True)
    _validate(record)
    path = directory / "records.jsonl"
    lock_path = directory / ".lock"
    view_updated = True
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            with path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            try:
                write_view(directory, load_records(path))
            except OSError:
                view_updated = False
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    return {"record_appended": True, "view_updated": view_updated, "record_id": record["record_id"]}


def load_records(path):
    path = Path(path)
    if not path.is_file():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def write_view(directory, records):
    view = build_view(records)
    directory = Path(directory)
    target = directory / "view.json"
    temporary = directory / ".view.json.tmp"
    temporary.write_text(json.dumps(view, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)
    return view


def build_view(records):
    superseded = {item.get("supersedes") for item in records if item.get("supersedes")}
    groups = {}
    mock_excluded = 0
    for record in records:
        if record.get("record_kind") == "mock" or record.get("evidence_origin") == "mock":
            mock_excluded += 1
            continue
        if record.get("record_id") in superseded:
            continue
        if record.get("record_kind") != "measured" or record.get("evidence_origin") != "measured":
            continue
        for check in record.get("checks") or []:
            bucket = groups.setdefault(_key(record, check["id"]), _bucket(record, check["id"]))
            status = check.get("status")
            if status in bucket["measured"]:
                bucket["measured"][status] += 1
            bucket["measured"]["samples"] += 1
            recorded = record.get("recorded_at")
            if recorded and (bucket["latest_measured_at"] is None or recorded > bucket["latest_measured_at"]):
                bucket["latest_measured_at"] = recorded
            if not record.get("evidence_index"):
                bucket["evidence_available"] = False
    rows = []
    for bucket in groups.values():
        measured = bucket["measured"]
        bucket["conflict"] = measured["pass"] > 0 and measured["fail"] > 0
        rows.append(bucket)
    rows.sort(key=lambda item: json.dumps(item["target_environment"], sort_keys=True) + item["check_id"])
    return {"schema_version": 1, "mock_excluded": mock_excluded, "rows": rows}


def _bucket(record, check_id):
    document = record.get("document") or {}
    return {
        "source_environment": record.get("source_environment"),
        "target_environment": record.get("target_environment"),
        "document_type": document.get("type"),
        "format": document.get("format"),
        "format_version": document.get("format_version"),
        "check_id": check_id,
        "adapter": record.get("adapter"),
        "check_profile": record.get("check_profile"),
        "measured": {"pass": 0, "fail": 0, "unknown": 0, "blocked": 0, "partial": 0, "samples": 0},
        "latest_measured_at": None,
        "evidence_available": True,
        "upstream_build": record.get("upstream_build") or {"tool": "not-specified", "version": "", "session_evidence_refs": []},
        "limits": _limits(record),
    }


def _key(record, check_id):
    document = record.get("document") or {}
    adapter = record.get("adapter") or {}
    profile = record.get("check_profile") or {}
    return json.dumps({
        "source": record.get("source_environment"),
        "target": record.get("target_environment"),
        "type": document.get("type"),
        "format": document.get("format"),
        "format_version": document.get("format_version"),
        "check": check_id,
        "adapter": adapter.get("id"),
        "adapter_version": adapter.get("version"),
        "profile": profile.get("id"),
        "revision": profile.get("revision"),
        "upstream": (record.get("upstream_build") or {}).get("tool") or "not-specified",
    }, sort_keys=True)


def _limits(record):
    tool = (record.get("upstream_build") or {}).get("tool") or "not-specified"
    if tool == "classcad":
        return "ClassCAD 源端样本不证明目标软件的原生工程兼容"
    return "当前样本统计，不是该软件版本的完全兼容"


def _validate(record):
    for key in ("schema_version", "record_id", "record_kind", "evidence_origin", "checks", "overall_status"):
        if key not in record:
            raise ValueError("record missing " + key)
    if record["record_kind"] == "measured":
        for key in ("recorded_at", "target_environment", "document", "adapter", "check_profile"):
            if not record.get(key):
                raise ValueError("measured record missing " + key)
        if record.get("evidence_origin") == "mock":
            raise ValueError("measured record cannot use mock evidence")
