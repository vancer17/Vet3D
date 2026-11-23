"""Single-attempt JSON HTTP transport; no environment proxy/auth lookup."""
from __future__ import annotations
import http.client
import json
from typing import Any
from urllib.parse import urlsplit
from mdf_gateway import validate_endpoint

TRANSPORT_EXCEPTIONS = (OSError, http.client.HTTPException)


class JsonResponse:
    def __init__(self, status_code: int, body: Any):
        self.status_code = status_code
        self.body = body

    def json(self):
        if isinstance(self.body, Exception):
            raise self.body
        return self.body


def post_json(endpoint, *, headers, json, timeout, allow_redirects,
              max_response_bytes=512 * 1024 * 1024):
    """Standard-library single POST, bounded response, no redirects or retries."""
    if allow_redirects:
        raise ValueError("Redirects are forbidden")
    validate_endpoint(endpoint)
    if not isinstance(max_response_bytes, int) or max_response_bytes <= 0:
        raise ValueError("max_response_bytes must be positive")
    parsed = urlsplit(endpoint)
    connection_type = (
        http.client.HTTPSConnection
        if parsed.scheme == "https"
        else http.client.HTTPConnection
    )
    connection = connection_type(parsed.hostname, parsed.port, timeout=timeout)
    try:
        connection.request(
            "POST", parsed.path, body=encode_json(json), headers=dict(headers)
        )
        response = connection.getresponse()
        # Non-200 content cannot prove a downstream response and need not be read.
        if response.status != 200:
            return JsonResponse(response.status, None)
        content = response.read(max_response_bytes + 1)
        if len(content) > max_response_bytes:
            return JsonResponse(
                response.status, ValueError("Response exceeds configured byte limit")
            )
        try:
            body = decode_json(content)
        except ValueError as exc:
            body = exc
        return JsonResponse(response.status, body)
    finally:
        connection.close()


def encode_json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")


def decode_json(content):
    return json.loads(content)
