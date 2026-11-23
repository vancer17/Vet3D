"""HTTP gateway URL resolution and read-only identity/health checks."""
from __future__ import annotations
import http.client
import json
import math
import os
from typing import Any, Dict, Mapping, Optional
from urllib.parse import urlsplit, urlunsplit
from online_service_atoms import ContractViolation, utc_now
DEFAULT_ENDPOINT = "http://172.31.192.135:7789/generate_model"
DEFAULT_GATEWAY_SERVICE = "CenterControlService-Generic-Forward"
MAX_RESPONSE_BYTES = 1024 * 1024


def validate_endpoint(endpoint: str) -> str:
    """Validate a non-secret HTTP endpoint; never include its value in errors."""
    if not isinstance(endpoint, str) or not endpoint.strip():
        raise ContractViolation("MDF endpoint must be a non-empty URL")
    endpoint = endpoint.strip()
    try:
        parsed = urlsplit(endpoint)
        port = parsed.port
    except ValueError as exc:
        raise ContractViolation("MDF endpoint has an invalid authority") from exc
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not parsed.path
        or (port is not None and not 1 <= port <= 65535)
        or any(char.isspace() for char in endpoint)
    ):
        raise ContractViolation(
            "MDF endpoint requires HTTP(S), host and path, without credentials, query or fragment"
        )
    return endpoint


def resolve_endpoint(
    endpoint: Optional[str] = None, *, environment: Optional[Mapping[str, str]] = None
) -> str:
    """Explicit endpoint > MDF_ENDPOINT > bundled internal deployment address.

    Only MDF_ENDPOINT is read. A present but empty setting is an error, not a
    reason to silently send the request to a different deployment.
    """
    if endpoint is None:
        env = os.environ if environment is None else environment
        endpoint = env.get("MDF_ENDPOINT", DEFAULT_ENDPOINT)
    return validate_endpoint(endpoint)


def gateway_health_url(endpoint: str) -> str:
    """Use the sibling /health route, retaining an explicit reverse-proxy prefix."""
    parsed = urlsplit(validate_endpoint(endpoint))
    prefix = parsed.path.rsplit("/", 1)[0]
    return urlunsplit((parsed.scheme, parsed.netloc, prefix + "/health", "", ""))


def get_health_json(
    url: str, *, timeout_sec: float = 10.0, headers: Optional[Mapping[str, str]] = None
) -> Dict[str, Any]:
    """One bounded GET; no redirects, retries, proxy env or response-body logging."""
    if not math.isfinite(timeout_sec) or timeout_sec <= 0:
        raise ContractViolation("timeout_sec must be finite and positive")
    parsed = urlsplit(validate_endpoint(url))
    connection_type = (
        http.client.HTTPSConnection
        if parsed.scheme == "https"
        else http.client.HTTPConnection
    )
    connection = connection_type(parsed.hostname, parsed.port, timeout=timeout_sec)
    try:
        connection.request("GET", parsed.path, headers=dict(headers or {}))
        response = connection.getresponse()
        if response.status != 200:
            return {"http_status": response.status, "body": None}
        content = response.read(MAX_RESPONSE_BYTES + 1)
        if len(content) > MAX_RESPONSE_BYTES:
            raise ContractViolation("MDF health response exceeds size limit")
        return {"http_status": 200, "body": json.loads(content)}
    finally:
        connection.close()


def check_gateway(
    endpoint: str,
    *,
    expected_service: str = DEFAULT_GATEWAY_SERVICE,
    timeout_sec: float = 10.0,
    headers: Optional[Mapping[str, str]] = None,
    get_json=get_health_json,
) -> Dict[str, Any]:
    """Verify gateway identity only; never infer downstream routing or inference."""
    health_url = gateway_health_url(endpoint)
    if not isinstance(expected_service, str) or not expected_service.strip():
        raise ContractViolation("expected_service is required")
    report = {
        "checked_at": utc_now(),
        "gateway_ready": False,
        "downstream_routing": "unverified",
        "business_execution": "not_run",
    }
    try:
        response = get_json(health_url, timeout_sec=timeout_sec, headers=headers)
        report["http_status"] = response["http_status"]
        body = response["body"]
        if response["http_status"] != 200:
            report["reason"] = "health_http_error"
        elif not isinstance(body, dict):
            report["reason"] = "invalid_health_response"
        elif body.get("service_name") != expected_service:
            report["reason"] = "gateway_identity_mismatch"
        elif body.get("status") != "healthy":
            report["reason"] = "gateway_not_healthy"
        else:
            report["gateway_ready"] = True
            report["reason"] = "gateway_identity_and_health_confirmed"
    except Exception as exc:
        report["reason"] = "health_check_failed"
        report["error_type"] = type(exc).__name__
    return report
