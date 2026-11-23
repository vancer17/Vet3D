#!/usr/bin/env python3
"""Check the HTTP gateway, or inspect explicitly selected SDK configuration."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Union
from urllib.parse import urlsplit

from online_service_atoms import ContractViolation, atomic_write_json, utc_now
from mdf_gateway import (
    DEFAULT_ENDPOINT, DEFAULT_GATEWAY_SERVICE, check_gateway, gateway_health_url,
    get_health_json, resolve_endpoint, validate_endpoint,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PACKAGE_ROOT / "assets" / "config.test.yaml"
DEFAULT_ENVIRONMENT = "test"
CATALOG_PATH = PACKAGE_ROOT / "assets" / "services.json"
PathLike = Union[str, Path]


def validate_config_path(config_path: PathLike) -> Path:
    """Require an existing YAML file; never echo its contents."""
    if not isinstance(config_path, (str, Path)) or not str(config_path).strip():
        raise ContractViolation("MDF3 config path must be a non-empty path")
    path = Path(config_path).expanduser()
    try:
        path = path.resolve()
    except OSError as exc:
        raise ContractViolation("MDF3 config path cannot be resolved") from exc
    if not path.is_file():
        raise ContractViolation("MDF3 config file is missing")
    if path.suffix.lower() not in (".yaml", ".yml"):
        raise ContractViolation("MDF3 config must be a YAML file")
    return path


def resolve_config_path(
    config_path: Optional[PathLike] = None,
    *,
    environment: str = DEFAULT_ENVIRONMENT,
    environ: Optional[Mapping[str, str]] = None,
) -> Path:
    """Explicit --config > MDF3_CONFIG_PATH > bundled test config.

    MDF3_CONFIG_PATH may be a YAML file or a directory containing
    config.<environment>.yaml. A present but empty setting is an error.
    """
    if not isinstance(environment, str) or not environment.strip():
        raise ContractViolation("environment is required")
    if config_path is not None:
        return validate_config_path(config_path)
    env = os.environ if environ is None else environ
    if "MDF3_CONFIG_PATH" in env:
        configured = env.get("MDF3_CONFIG_PATH", "")
        if not isinstance(configured, str) or not configured.strip():
            raise ContractViolation("MDF3_CONFIG_PATH is set but empty")
        path = Path(configured.strip()).expanduser()
        if path.is_dir():
            path = path / ("config.%s.yaml" % environment.strip())
        return validate_config_path(path)
    if environment != DEFAULT_ENVIRONMENT:
        raise ContractViolation(
            "Non-test environments require --config or MDF3_CONFIG_PATH"
        )
    return validate_config_path(DEFAULT_CONFIG_PATH)


def validate_queue_url(endpoint: str) -> str:
    """Validate a TaskQueue URL without echoing credentials or the original value."""
    if not isinstance(endpoint, str) or not endpoint.strip():
        raise ContractViolation("task_queue endpoint must be a non-empty URL")
    endpoint = endpoint.strip()
    try:
        parsed = urlsplit(endpoint)
        port = parsed.port
    except ValueError as exc:
        raise ContractViolation("task_queue endpoint has an invalid authority") from exc
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or (port is not None and not 1 <= port <= 65535)
        or any(char.isspace() for char in endpoint)
    ):
        raise ContractViolation(
            "task_queue endpoint requires HTTP(S) host without credentials, query or fragment"
        )
    return endpoint


def load_config_mapping(path: PathLike) -> Dict[str, Any]:
    """Parse YAML without returning or logging file contents on failure."""
    try:
        import yaml
    except ImportError as exc:
        raise ContractViolation("PyYAML is required to read the MDF3 config") from exc
    try:
        loaded = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError):
        raise ContractViolation("Cannot read the MDF3 config") from None
    except Exception:
        raise ContractViolation("Cannot parse the MDF3 config") from None
    if not isinstance(loaded, dict):
        raise ContractViolation("MDF3 config must be a mapping")
    return loaded


def inspect_config(path: PathLike) -> Dict[str, Any]:
    """Confirm required queue settings; never infer downstream routing."""
    config = load_config_mapping(path)
    queue = config.get("task_queue")
    endpoints = queue.get("endpoints") if isinstance(queue, dict) else None
    if not isinstance(endpoints, list) or not endpoints:
        raise ContractViolation("task_queue.endpoints must be a nonempty list")
    for item in endpoints:
        validate_queue_url(item)
    nacos = config.get("nacos") if isinstance(config.get("nacos"), dict) else {}
    nacos_address = nacos.get("nacos_server_addresses")
    return {
        "checked_at": utc_now(),
        "config_ready": True,
        "task_queue_endpoint_count": len(endpoints),
        "nacos_configured": isinstance(nacos_address, str) and bool(nacos_address.strip()),
        "downstream_routing": "unverified",
        "business_execution": "not_run",
        "reason": "config_and_task_queue_confirmed",
    }


def check_config(
    config_path: Optional[PathLike] = None,
    *,
    environment: str = DEFAULT_ENVIRONMENT,
    environ: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Resolve and inspect config identity only; do not contact workers."""
    report = {
        "checked_at": utc_now(),
        "config_ready": False,
        "downstream_routing": "unverified",
        "business_execution": "not_run",
        "environment": environment,
    }
    try:
        path = resolve_config_path(
            config_path, environment=environment, environ=environ
        )
        report["config_alias"] = path.name
        report.update(inspect_config(path))
        report["config_path"] = str(path)
    except ContractViolation as exc:
        report["reason"] = str(exc)
        report["error_type"] = type(exc).__name__
    except Exception as exc:
        report["reason"] = "config_check_failed"
        report["error_type"] = type(exc).__name__
    return report


def load_service_names(path: Path = CATALOG_PATH):
    """Read the bundled inventory, checking names and duplicates without imports."""
    catalog = json.loads(path.read_text(encoding="utf-8"))
    entries = catalog.get("services")
    if (
        catalog.get("schema_version") != 1
        or not isinstance(entries, list)
        or not entries
    ):
        raise ContractViolation("Invalid MDF service inventory")
    names = [entry.get("name") for entry in entries if isinstance(entry, dict)]
    if (
        len(names) != len(entries)
        or any(not isinstance(name, str) or not name.strip() for name in names)
        or len(set(names)) != len(names)
    ):
        raise ContractViolation("MDF service inventory requires unique non-empty names")
    return names


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transport", choices=("http", "sdk"), default="http")
    parser.add_argument("--endpoint")
    parser.add_argument("--expected-service", default=DEFAULT_GATEWAY_SERVICE)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument(
        "--config",
        help="YAML file; overrides MDF3_CONFIG_PATH and the bundled test config",
    )
    parser.add_argument("--environment", default=DEFAULT_ENVIRONMENT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.transport == "http" and args.config is not None:
        parser.error("--config requires --transport sdk")
    if args.transport == "sdk" and args.endpoint is not None:
        parser.error("--endpoint requires --transport http")
    try:
        if args.transport == "http":
            report = check_gateway(resolve_endpoint(args.endpoint),
                expected_service=args.expected_service, timeout_sec=args.timeout)
        else:
            report = check_config(args.config, environment=args.environment)
        report["transport"] = args.transport
    except ContractViolation as exc:
        parser.error(str(exc))
    if args.output:
        atomic_write_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("config_ready") or report.get("gateway_ready") else 1


if __name__ == "__main__":
    raise SystemExit(main())
