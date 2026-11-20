#!/usr/bin/env python3
"""Call one MDF service from JSON with local BinaryFile references."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import sys
import uuid
import time

from check_runtime import check_runtime

from mdf_endpoint import (
    DEFAULT_ENVIRONMENT,
    inspect_config,
    load_service_names,
    resolve_config_path,
)
from mdf3_service_invoke import MDF3ServiceInvokeCaller
from mdf3_generic_forward import MDF3GenericForwardCaller
from mdf_gateway import resolve_endpoint
from mdf_runtime import load_codec
from online_service_atoms import (
    AuditWriter,
    _is_sensitive_key,
    atomic_write_bytes,
    atomic_write_json,
    sha256_file,
    summarize_for_audit,
    utc_now,
)


def materialize_request(value, *, base_dir: Path, binary_factory, field_name=""):
    """Replace explicit {$file: path} objects; paths are relative to the JSON file."""
    if isinstance(value, dict):
        if "$file" in value:
            if set(value) - {"$file", "field_name", "file_name"}:
                raise ValueError(
                    "File references accept only $file, field_name and file_name"
                )
            if not isinstance(value["$file"], str) or not value["$file"]:
                raise ValueError("$file must be a non-empty local path")
            path = Path(value["$file"])
            path = path if path.is_absolute() else base_dir / path
            return binary_factory(
                field_name=value.get("field_name", field_name),
                file_name=value.get("file_name", path.name),
                content=path.read_bytes(),
            )
        return {
            key: materialize_request(
                child, base_dir=base_dir, binary_factory=binary_factory, field_name=key
            )
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [
            materialize_request(
                child,
                base_dir=base_dir,
                binary_factory=binary_factory,
                field_name=field_name,
            )
            for child in value
        ]
    return value


def field_equals(result, field, expected):
    """Match a dotted response field exactly, including the JSON value's type."""
    value = result
    for part in field.split("."):
        if not isinstance(value, dict) or part not in value:
            return False
        value = value[part]
    return type(value) is type(expected) and value == expected


def save_binary_outputs(result, *, directory: Path, binary_type):
    """Save returned BinaryFile/bytes with safe unique names and integrity metadata."""
    files = []

    def visit(value, location):
        if isinstance(value, binary_type) or isinstance(value, bytes):
            content = value if isinstance(value, bytes) else value.content
            name = (
                "output.bin"
                if isinstance(value, bytes)
                else (value.file_name or "output.bin")
            )
            name = re.sub(
                r"[^A-Za-z0-9._-]", "_", name.replace("\\", "/").split("/")[-1]
            )[-120:]
            path = directory / ("%04d_%s" % (len(files) + 1, name))
            atomic_write_bytes(path, content)
            files.append(
                {
                    "field_path": location,
                    "file": path.name,
                    "size": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
        elif isinstance(value, dict):
            for key, child in value.items():
                if not _is_sensitive_key(str(key), ()):
                    visit(child, location + [str(key)])
        elif isinstance(value, (list, tuple)):
            for index, child in enumerate(value):
                visit(child, location + [index])

    visit(result, [])
    return files


def redact_summary_urls(value):
    """Remove potentially signed/credential URLs from the already redacted summary."""
    if isinstance(value, dict):
        return {key: redact_summary_urls(child) for key, child in value.items()}
    if isinstance(value, list):
        return [redact_summary_urls(child) for child in value]
    if isinstance(value, str) and ("http://" in value or "https://" in value):
        return "<url-containing text omitted>"
    return value


def main(argv=None, *, session_factory=None, binary_factory=None, post=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transport", choices=("http", "sdk"), default="http",
                        help="HTTP gateway by default; SDK needs worker TCP access to this host")
    parser.add_argument("--endpoint", help="HTTP gateway URL; HTTP transport only")
    parser.add_argument("--service", required=True, choices=load_service_names())
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="JSON; {$file: path} creates BinaryFile",
    )
    parser.add_argument(
        "--run-dir", required=True, type=Path, help="New directory for this invocation"
    )
    parser.add_argument(
        "--config",
        help="YAML file; overrides MDF3_CONFIG_PATH and the bundled test config",
    )
    parser.add_argument("--environment", default=DEFAULT_ENVIRONMENT)
    parser.add_argument("--timeout", type=float, default=3600.0)
    parser.add_argument("--success-field", default="success")
    parser.add_argument(
        "--success-value",
        default="true",
        help="JSON literal, e.g. true or '\"success\"'",
    )
    parser.add_argument("--require-numpy", action="store_true",
                        help="Preflight NumPy when the service contract contains arrays")
    args = parser.parse_args(argv)
    if args.transport == "http" and args.config is not None:
        parser.error("--config requires --transport sdk; HTTP uses --endpoint")
    if args.transport == "sdk" and args.endpoint is not None:
        parser.error("--endpoint requires --transport http; SDK uses --config")
    if args.transport == "http" and session_factory is not None:
        parser.error("session_factory requires --transport sdk")
    if args.transport == "sdk" and post is not None:
        parser.error("post requires --transport http")
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be finite and positive")
    if not args.success_field or any(
        not part for part in args.success_field.split(".")
    ):
        parser.error("--success-field must be a non-empty dotted field")
    if args.run_dir.exists():
        parser.error(
            "--run-dir exists; inspect original trace before another submission"
        )
    runtime = check_runtime(require_numpy=args.require_numpy, transport=args.transport)
    if not runtime["ready"] and session_factory is None:
        print(json.dumps({"status": "NOT_SUBMITTED", "runtime": runtime}), file=sys.stderr)
        return 2
    try:
        config_path = None
        endpoint = None
        if args.transport == "sdk":
            config_path = resolve_config_path(args.config, environment=args.environment)
            inspect_config(config_path)
        else:
            endpoint = resolve_endpoint(args.endpoint)
        expected = json.loads(args.success_value)
        request_json = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(request_json, dict) or "$file" in request_json:
            raise ValueError("Input must be a business parameter object")
        # Materialize files only for the selected authorized business call.
        if binary_factory is None:
            binary_factory = load_codec(transport=args.transport).BinaryFile

        request = materialize_request(
            request_json,
            base_dir=args.input.resolve().parent,
            binary_factory=binary_factory,
        )
    except Exception as exc:
        print(
            json.dumps({"status": "NOT_SUBMITTED", "error_type": type(exc).__name__}),
            file=sys.stderr,
        )
        return 2
    try:
        args.run_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    except FileExistsError:
        parser.error(
            "--run-dir exists; inspect original trace before another submission"
        )
    trace = "mdf-call-" + uuid.uuid4().hex
    record = {
        "service": args.service,
        "trace_id": trace,
        "created_at": utc_now(),
        "transport": args.transport,
        "endpoint_alias": "mdf3-service-invoke" if args.transport == "sdk" else "configured-generic-forward",
        "environment": args.environment,
        "timeout_sec": args.timeout,
        "attempts": 1,
        "success_field": args.success_field,
        "success_value": expected,
        "artifact_validation": "not_run",
        "status": "NOT_SUBMITTED",
    }
    if config_path is not None:
        record["config_alias"] = config_path.name
    atomic_write_json(args.run_dir / "invocation.json", record)
    atomic_write_json(args.run_dir / "runtime.json", runtime)
    observed = {}
    started = time.monotonic()

    def accept(result):
        observed["result"] = result
        return field_equals(result, args.success_field, expected)

    try:
        common = dict(
            endpoint_alias=record["endpoint_alias"],
            environment=args.environment,
            audit=AuditWriter(args.run_dir / "audit.jsonl"),
            success_predicate=accept,
        )
        if args.transport == "sdk":
            caller = MDF3ServiceInvokeCaller(config_path=str(config_path),
                session_factory=session_factory, **common)
        else:
            caller = MDF3GenericForwardCaller(endpoint=endpoint, post=post, **common)
        record["status"] = "IN_PROGRESS"
        atomic_write_json(args.run_dir / "invocation.json", record)
        result = caller.call_once(
            service=args.service,
            input_data=request,
            trace_id=trace,
            timeout_sec=args.timeout,
            run_id=trace,
            case_id=args.service,
            call_id=trace,
        )
        record["status"] = "SUCCEEDED"
        record["files"] = save_binary_outputs(
            result, directory=args.run_dir / "artifacts", binary_type=binary_factory
        )
    except Exception as exc:
        record["status"] = (
            "OUTPUT_SAVE_FAILED"
            if record["status"] == "SUCCEEDED"
            else type(exc).__name__
        )
    if "result" in observed:
        try:
            atomic_write_json(
                args.run_dir / "result.summary.json",
                redact_summary_urls(summarize_for_audit(observed["result"])),
            )
        except Exception as exc:
            record["output_error_type"] = type(exc).__name__
            if record["status"] == "SUCCEEDED":
                record["status"] = "OUTPUT_SAVE_FAILED"
    record["finished_at"] = utc_now()
    record["elapsed_seconds"] = time.monotonic() - started
    atomic_write_json(args.run_dir / "invocation.json", record)
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0 if record["status"] == "SUCCEEDED" else 1


if __name__ == "__main__":
    sys.exit(main())
