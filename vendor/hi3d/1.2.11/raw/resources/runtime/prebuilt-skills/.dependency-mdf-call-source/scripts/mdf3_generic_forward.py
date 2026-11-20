#!/usr/bin/env python3
"""Audited, single-attempt MDF3 generic-forward protocol adapter."""

from __future__ import annotations

import base64
import math
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Tuple

from mdf_gateway import resolve_endpoint

from online_service_atoms import (
    AmbiguousOutcome,
    AuditWriter,
    BusinessFailure,
    CallIdFactory,
    ContractViolation,
    DefinitiveRejection,
    stable_digest,
    summarize_for_audit,
)


class MDF3GenericForwardCaller:
    """Call one MDF3 target service without automatic retries.

    Dependencies and business semantics are injectable so the adapter can be
    tested offline and does not impose project-specific success fields.
    """

    def __init__(
        self,
        *,
        endpoint: Optional[str] = None,
        endpoint_alias: str,
        environment: str,
        audit: AuditWriter,
        success_predicate: Callable[[Mapping[str, Any]], bool],
        workflow_name: str = "generic-forward",
        trace_header: str = "traceid",
        idempotency_header: Optional[str] = None,
        headers: Optional[Mapping[str, str]] = None,
        post: Optional[Callable[..., Any]] = None,
        dumps_fn: Optional[Callable[[Any], bytes]] = None,
        loads_fn: Optional[Callable[[bytes], Any]] = None,
        transport_exceptions: Optional[Tuple[type, ...]] = None,
        extra_sensitive_keys: Iterable[str] = (),
        input_audit_summarizer: Optional[Callable[[Mapping[str, Any]], Any]] = None,
        output_audit_summarizer: Optional[Callable[[Mapping[str, Any]], Any]] = None,
    ) -> None:
        endpoint = resolve_endpoint(endpoint)
        if not endpoint_alias.strip() or not environment.strip():
            raise ContractViolation("endpoint_alias and environment are required")
        if not callable(success_predicate):
            raise ContractViolation("success_predicate must be callable")
        self.endpoint = endpoint
        self.endpoint_alias = endpoint_alias
        self.environment = environment
        self.audit = audit
        self.success_predicate = success_predicate
        self.workflow_name = workflow_name
        self.trace_header = trace_header
        self.idempotency_header = idempotency_header
        self.headers = dict(headers or {})
        self._post = post
        self._dumps = dumps_fn
        self._loads = loads_fn
        self._transport_exceptions = transport_exceptions
        self.extra_sensitive_keys = tuple(extra_sensitive_keys)
        self.input_audit_summarizer = input_audit_summarizer
        self.output_audit_summarizer = output_audit_summarizer
        self._call_ids = CallIdFactory("mdf3")

    def _mapping_audit_summary(
        self,
        value: Mapping[str, Any],
        hook: Optional[Callable[[Mapping[str, Any]], Any]],
    ) -> Any:
        if hook is not None:
            return summarize_for_audit(
                hook(value),
                extra_sensitive_keys=self.extra_sensitive_keys,
            )
        return {
            "keys": sorted(str(key) for key in value),
            "digest": stable_digest(
                value,
                extra_sensitive_keys=self.extra_sensitive_keys,
            ),
        }

    def _ensure_dependencies(self) -> None:
        if self._post is None or self._transport_exceptions is None:
            from mdf_http import post_json, TRANSPORT_EXCEPTIONS
            if self._post is None:
                self._post = post_json
            if self._transport_exceptions is None:
                self._transport_exceptions = TRANSPORT_EXCEPTIONS
        if self._dumps is None or self._loads is None:
            try:
                from mdf_runtime import load_codec
                codec = load_codec(transport="http")
                dumps, loads = codec.dumps, codec.loads
            except ImportError as exc:
                raise ContractViolation(
                    "mdf3 is required for MDF3 generic-forward"
                ) from exc
            if self._dumps is None:
                self._dumps = dumps
            if self._loads is None:
                self._loads = loads

    def call_once(
        self,
        *,
        service: str,
        input_data: Mapping[str, Any],
        trace_id: str,
        timeout_sec: float,
        run_id: str,
        case_id: str,
        idempotency_key: Optional[str] = None,
        call_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not service.strip() or not trace_id.strip():
            raise ContractViolation("service and trace_id are required")
        if not math.isfinite(float(timeout_sec)) or timeout_sec <= 0:
            raise ContractViolation("timeout_sec must be finite and positive")
        if idempotency_key is not None and not self.idempotency_header:
            raise ContractViolation(
                "idempotency_key supplied without a confirmed idempotency_header"
            )

        self._ensure_dependencies()
        assert self._post is not None
        assert self._dumps is not None
        assert self._loads is not None
        assert self._transport_exceptions is not None

        resolved_call_id = call_id or self._call_ids.next(service)
        try:
            serialized = self._dumps(dict(input_data))
        except Exception as exc:
            raise ContractViolation(
                "failed to serialize request before submission: %s"
                % type(exc).__name__,
                call_id=resolved_call_id,
            ) from exc
        if not isinstance(serialized, bytes):
            raise ContractViolation(
                "dumps_fn must return bytes", call_id=resolved_call_id
            )

        payload = {
            "workflow_name": self.workflow_name,
            "input_data": {
                "target_service": service,
                "pickle_payload": base64.b64encode(serialized).decode("ascii"),
            },
        }
        request_headers = dict(self.headers)
        request_headers.update(
            {
                "Content-Type": "application/json",
                self.trace_header: trace_id,
            }
        )
        if idempotency_key is not None:
            request_headers[self.idempotency_header] = idempotency_key

        common = {
            "run_id": run_id,
            "case_id": case_id,
            "trace_id": trace_id,
            "call_id": resolved_call_id,
            "service": service,
            "environment": self.environment,
            "endpoint_alias": self.endpoint_alias,
        }
        self.audit.write(
            "request_sent",
            **dict(
                common,
                **{
                    "timeout_sec": float(timeout_sec),
                    "retries": 0,
                    "idempotency_key": idempotency_key,
                    "input": self._mapping_audit_summary(
                        input_data,
                        self.input_audit_summarizer,
                    ),
                },
            ),
        )

        try:
            response = self._post(
                self.endpoint,
                headers=request_headers,
                json=payload,
                timeout=float(timeout_sec),
                allow_redirects=False,
            )
        except self._transport_exceptions as exc:
            self.audit.write(
                "request_ambiguous",
                **dict(
                    common,
                    **{
                        "status": "transport_unknown",
                        "error_type": type(exc).__name__,
                    },
                ),
            )
            raise AmbiguousOutcome(
                "%s transport outcome is unknown; not retried" % service,
                call_id=resolved_call_id,
            ) from exc

        status_code = int(getattr(response, "status_code", 0))
        if (
            status_code >= 500
            or status_code <= 0
            or (200 <= status_code < 400 and status_code != 200)
        ):
            self.audit.write(
                "request_ambiguous",
                **dict(
                    common,
                    **{
                        "status": "http_%s" % status_code,
                        "http_status": status_code,
                    },
                ),
            )
            raise AmbiguousOutcome(
                "%s returned ambiguous HTTP %s; not retried"
                % (
                    service,
                    status_code,
                ),
                call_id=resolved_call_id,
            )
        if status_code != 200:
            self.audit.write(
                "request_finished",
                **dict(
                    common,
                    **{
                        "status": "rejected",
                        "http_status": status_code,
                    },
                ),
            )
            raise DefinitiveRejection(
                "%s was rejected with HTTP %s" % (service, status_code),
                call_id=resolved_call_id,
            )

        try:
            body = response.json()
        except Exception as exc:
            self.audit.write(
                "request_ambiguous",
                **dict(
                    common,
                    **{
                        "status": "invalid_json",
                        "http_status": status_code,
                    },
                ),
            )
            raise AmbiguousOutcome(
                "%s returned an unreadable success response; not retried" % service,
                call_id=resolved_call_id,
            ) from exc
        if not isinstance(body, dict):
            self.audit.write(
                "request_ambiguous",
                **dict(
                    common,
                    **{
                        "status": "invalid_envelope",
                        "http_status": status_code,
                    },
                ),
            )
            raise AmbiguousOutcome(
                "%s returned a non-object envelope; not retried" % service,
                call_id=resolved_call_id,
            )
        if body.get("success") is not True and body.get("success") is not False:
            self.audit.write(
                "request_ambiguous",
                **dict(common, status="invalid_success_flag", http_status=status_code),
            )
            raise AmbiguousOutcome(
                "%s envelope has no explicit success/failure; not retried" % service,
                call_id=resolved_call_id,
            )
        if body.get("success") is not True:
            self.audit.write(
                "request_finished",
                **dict(
                    common,
                    **{
                        "status": "failed",
                        "http_status": status_code,
                        "envelope": self._mapping_audit_summary(body, None),
                    },
                ),
            )
            raise BusinessFailure(
                "%s generic-forward envelope reported failure" % service,
                call_id=resolved_call_id,
            )

        encoded_result = body.get("pickle_payload")
        if not isinstance(encoded_result, str) or not encoded_result:
            self.audit.write(
                "request_ambiguous",
                **dict(
                    common,
                    **{
                        "status": "missing_pickle_payload",
                        "http_status": status_code,
                    },
                ),
            )
            raise AmbiguousOutcome(
                "%s success envelope lacks a result; not retried" % service,
                call_id=resolved_call_id,
            )
        try:
            result = self._loads(base64.b64decode(encoded_result, validate=True))
        except Exception as exc:
            self.audit.write(
                "request_ambiguous",
                **dict(
                    common,
                    **{
                        "status": "invalid_pickle_payload",
                        "http_status": status_code,
                    },
                ),
            )
            raise AmbiguousOutcome(
                "%s result cannot be decoded; not retried" % service,
                call_id=resolved_call_id,
            ) from exc
        if not isinstance(result, dict):
            self.audit.write(
                "request_finished",
                **dict(
                    common,
                    **{
                        "status": "invalid_output",
                        "http_status": status_code,
                        "output_type": type(result).__name__,
                    },
                ),
            )
            raise ContractViolation(
                "%s returned %s, expected dict"
                % (
                    service,
                    type(result).__name__,
                ),
                call_id=resolved_call_id,
            )
        try:
            succeeded = self.success_predicate(result)
        except Exception as exc:
            self.audit.write(
                "request_finished",
                **dict(
                    common,
                    **{
                        "status": "invalid_output",
                        "http_status": status_code,
                        "predicate_error_type": type(exc).__name__,
                        "output": self._mapping_audit_summary(
                            result,
                            self.output_audit_summarizer,
                        ),
                    },
                ),
            )
            raise ContractViolation(
                "%s success predicate raised %s"
                % (
                    service,
                    type(exc).__name__,
                ),
                call_id=resolved_call_id,
            ) from exc
        if succeeded is not True:
            self.audit.write(
                "request_finished",
                **dict(
                    common,
                    **{
                        "status": "failed",
                        "http_status": status_code,
                        "output": self._mapping_audit_summary(
                            result,
                            self.output_audit_summarizer,
                        ),
                    },
                ),
            )
            raise BusinessFailure(
                "%s business result failed its success predicate" % service,
                call_id=resolved_call_id,
            )

        self.audit.write(
            "request_finished",
            **dict(
                common,
                **{
                    "status": "succeeded",
                    "http_status": status_code,
                    "output": self._mapping_audit_summary(
                        result,
                        self.output_audit_summarizer,
                    ),
                },
            ),
        )
        return result
