#!/usr/bin/env python3
"""Capture local runtime provenance without contacting online services."""

from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any, Dict, Optional

from online_service_atoms import (
    atomic_write_json,
    sha256_file,
    summarize_for_audit,
    utc_now,
)


_SENSITIVE_ENV_PARTS = frozenset(
    (
        "authorization",
        "cookie",
        "credential",
        "key",
        "password",
        "secret",
        "signature",
        "token",
    )
)


def _command(args: list) -> Optional[str]:
    try:
        completed = subprocess.run(
            args,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            universal_newlines=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout.strip()


def _module_info(name: str) -> Dict[str, Any]:
    module = importlib.import_module(name)
    raw_path = getattr(module, "__file__", None)
    version = getattr(module, "__version__", None)
    result = {
        "name": name,
        "file": raw_path,
        "version": summarize_for_audit(version),
    }
    if raw_path:
        path = Path(raw_path).resolve()
        result["resolved_file"] = str(path)
        if path.is_file():
            result["size"] = path.stat().st_size
            result["sha256"] = sha256_file(path)
    return result


def _repo_info(raw_path: str) -> Dict[str, Any]:
    path = Path(raw_path).resolve()
    commit = _command(["git", "-C", str(path), "rev-parse", "HEAD"])
    branch = _command(["git", "-C", str(path), "symbolic-ref", "--short", "HEAD"])
    status = _command(["git", "-C", str(path), "status", "--porcelain"])
    return {
        "path": str(path),
        "commit": commit,
        "branch": branch,
        "dirty": None if status is None else bool(status),
    }


def _env_info(name: str) -> Dict[str, Any]:
    normalized_parts = {
        part for part in name.lower().replace("-", "_").split("_") if part
    }
    value = os.environ.get(name)
    if normalized_parts & _SENSITIVE_ENV_PARTS:
        return {"name": name, "present": value is not None, "value": "<redacted>"}
    return {"name": name, "present": value is not None, "value": value}


def capture_runtime(
    *, modules=(), repositories=(), environment_keys=(), labels=None
) -> Dict[str, Any]:
    """Collect local provenance; selected modules must be safe to import."""
    return {
        "schema_version": 1,
        "captured_at": utc_now(),
        "cwd": str(Path.cwd()),
        "python": {
            "executable": sys.executable,
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
        },
        "sys_path": list(sys.path),
        "modules": [_module_info(name) for name in modules],
        "repositories": [_repo_info(path) for path in repositories],
        "environment": [_env_info(name) for name in environment_keys],
        "labels": summarize_for_audit(labels or {}),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--module", action="append", default=[])
    parser.add_argument("--repo", action="append", default=[])
    parser.add_argument("--env-key", action="append", default=[])
    parser.add_argument("--label", action="append", default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    labels = {}
    for item in args.label:
        if "=" not in item:
            parser.error("--label must be KEY=VALUE")
        key, value = item.split("=", 1)
        labels[key] = value

    result = capture_runtime(
        modules=args.module,
        repositories=args.repo,
        environment_keys=args.env_key,
        labels=labels,
    )
    if args.output:
        atomic_write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
