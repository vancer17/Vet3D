#!/usr/bin/env python3
"""Explicitly submit one invalid-input diagnostic per selected MDF service.

This is an online invocation, not a read-only health check. A decoded downstream
error proves a round trip; it does not establish successful business execution.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import math
from pathlib import Path
import sys
import time
from typing import Any, Dict
import uuid

from mdf_endpoint import (
    DEFAULT_ENVIRONMENT,
    check_config,
    load_service_names,
    resolve_config_path,
)
from mdf3_service_invoke import MDF3ServiceInvokeCaller
from mdf3_generic_forward import MDF3GenericForwardCaller
from mdf_gateway import check_gateway, resolve_endpoint
from online_service_atoms import AuditWriter, atomic_write_json, utc_now


def probe_service(
    service: str,
    *,
    config_path: str = None,
    run_dir: Path,
    run_id: str,
    timeout_sec: float = 60.0,
    environment: str = DEFAULT_ENVIRONMENT,
    session_factory=None,
    transport: str = "http",
    endpoint: str = None,
    post=None,
) -> Dict[str, Any]:
    """Submit once, preserve trace/audit, classify response without saving its body."""
    if not math.isfinite(timeout_sec) or timeout_sec <= 0:
        raise ValueError("timeout_sec must be finite and positive")
    if transport not in ("http", "sdk"):
        raise ValueError("transport must be http or sdk")
    if transport == "http" and (config_path is not None or session_factory is not None):
        raise ValueError("config_path and session_factory require SDK transport")
    if transport == "sdk" and (endpoint is not None or post is not None):
        raise ValueError("endpoint and post require HTTP transport")
    trace_id = "mdf-probe-" + uuid.uuid4().hex
    record = {
        "service": service,
        "transport": transport,
        "trace_id": trace_id,
        "started_at": utc_now(),
        "attempts": 1,
        "request_kind": "missing_business_inputs",
        "reachability": "unverified",
        "business_validation": "not_run",
    }

    def observe(result):
        if isinstance(result, dict):
            record["reachability"] = "downstream_response_received"
            # Keep only booleans and field names, never error text, paths or logs.
            record["has_error_message"] = any(
                key in result for key in ("error", "error_info", "error_message")
            )
            record["downstream_success"] = result.get("success") is True
        return result.get("success") is True if isinstance(result, dict) else False

    started = time.monotonic()
    try:
        common = dict(
            endpoint_alias="mdf3-service-invoke" if transport == "sdk" else "configured-generic-forward",
            environment=environment,
            audit=AuditWriter(run_dir / (trace_id + ".jsonl")),
            success_predicate=observe,
        )
        if transport == "sdk":
            caller = MDF3ServiceInvokeCaller(config_path=config_path,
                session_factory=session_factory, **common)
        else:
            caller = MDF3GenericForwardCaller(endpoint=endpoint, post=post, **common)
        caller.call_once(
            service=service,
            input_data={"__mdf_connectivity_probe__": True},
            trace_id=trace_id,
            timeout_sec=timeout_sec,
            run_id=run_id,
            case_id=service,
            call_id=trace_id,
        )
        record["adapter_outcome"] = "SUCCEEDED"
    except Exception as exc:
        record["adapter_outcome"] = type(exc).__name__
    record["elapsed_seconds"] = round(time.monotonic() - started, 3)
    atomic_write_json(run_dir / (trace_id + ".json"), record)
    return record


def main(argv=None, *, session_factory=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transport", choices=("http", "sdk"), default="http")
    parser.add_argument("--endpoint", help="HTTP gateway URL")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--service", action="append", choices=load_service_names())
    selection.add_argument("--all-services", action="store_true")
    parser.add_argument(
        "--config",
        help="YAML file; overrides MDF3_CONFIG_PATH and the bundled test config",
    )
    parser.add_argument("--environment", default=DEFAULT_ENVIRONMENT)
    parser.add_argument(
        "--run-dir", type=Path, required=True, help="New directory per run"
    )
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--workers", type=int, default=1, choices=range(1, 5))
    args = parser.parse_args(argv)
    if args.transport == "http" and args.config is not None:
        parser.error("--config requires --transport sdk")
    if args.transport == "sdk" and args.endpoint is not None:
        parser.error("--endpoint requires --transport http")
    if args.transport == "http" and session_factory is not None:
        parser.error("session_factory requires --transport sdk")
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be finite and positive")
    if args.run_dir.exists():
        parser.error(
            "--run-dir already exists; inspect original traces before any new submission"
        )
    try:
        config_path = resolve_config_path(args.config, environment=args.environment) if args.transport == "sdk" else None
        endpoint = resolve_endpoint(args.endpoint) if args.transport == "http" else None
    except Exception:
        parser.error("Invalid configuration for the selected MDF transport")
    names = (
        load_service_names() if args.all_services else list(dict.fromkeys(args.service))
    )
    args.run_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    run_id = "mdf-probe-" + uuid.uuid4().hex
    gateway = check_config(config_path, environment=args.environment) if args.transport == "sdk" else check_gateway(endpoint)
    gateway["transport"] = args.transport
    atomic_write_json(args.run_dir / ("config.json" if args.transport == "sdk" else "gateway.json"), gateway)
    if not (gateway.get("config_ready") or gateway.get("gateway_ready")):
        print(json.dumps(gateway, ensure_ascii=False, indent=2))
        return 1
    atomic_write_json(
        args.run_dir / "plan.json",
        {
            "run_id": run_id,
            "transport": args.transport,
            "services": names,
            "timeout_sec": args.timeout,
            "request_kind": "missing_business_inputs",
            "created_at": utc_now(),
        },
    )
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending = [
            pool.submit(
                probe_service,
                name,
                config_path=str(config_path) if config_path else None,
                transport=args.transport,
                endpoint=endpoint,
                run_dir=args.run_dir,
                run_id=run_id,
                timeout_sec=args.timeout,
                environment=args.environment,
                session_factory=session_factory,
            )
            for name in names
        ]
        for future in as_completed(pending):
            record = future.result()
            results.append(record)
            print(json.dumps(record, ensure_ascii=False), flush=True)
    results.sort(key=lambda item: item["service"])
    reached = sum(
        item["reachability"] == "downstream_response_received" for item in results
    )
    report = {
        "run_id": run_id,
        "transport": args.transport,
        "config" if args.transport == "sdk" else "gateway": gateway,
        "services": results,
        "total": len(results),
        "downstream_responses": reached,
        "all_services_reached": reached == len(results),
        "business_validation": "not_run",
    }
    atomic_write_json(args.run_dir / "report.json", report)
    return 0 if report["all_services_reached"] else 2


if __name__ == "__main__":
    sys.exit(main())
