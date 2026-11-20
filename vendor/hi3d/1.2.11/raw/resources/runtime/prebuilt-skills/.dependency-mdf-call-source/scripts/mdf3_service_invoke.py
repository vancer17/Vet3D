#!/usr/bin/env python3
"""Audited, single-attempt MDF3 ServiceInvokeSession adapter."""

from __future__ import annotations

import math
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterable, Mapping, Optional

from mdf_endpoint import DEFAULT_ENVIRONMENT, inspect_config, resolve_config_path

from online_service_atoms import (
    AmbiguousOutcome,
    AuditWriter,
    BusinessFailure,
    CallIdFactory,
    ContractViolation,
    stable_digest,
    summarize_for_audit,
)


DEFAULT_CALLER_SERVICE_NAME = "mdf-call"
DEFAULT_ENDPOINT_ALIAS = "mdf3-service-invoke"


@contextmanager
def default_session_factory(
    *, config_path, environment, caller_service_name=DEFAULT_CALLER_SERVICE_NAME
):
    """Create the official SDK session; imported only when a call is submitted."""
    try:
        from mdf3.service_invoke_tool import ServiceInvokeSession
    except ImportError as exc:
        raise ContractViolation(
            "mdf3 ServiceInvokeSession is required to call MDF services"
        ) from exc
    session = ServiceInvokeSession(
        environment=environment,
        config_path=str(config_path),
        caller_service_name=caller_service_name,
    )
    try:
        session.start()
        yield session
    finally:
        # __exit__ is not called when SDK startup fails inside __enter__.
        session.stop()


def _invoke_exceptions():
    try:
        from mdf3.service_invoke_tool import ServiceCallFailed, ServiceCallTimeout
    except ImportError:
        return (TimeoutError, OSError, RuntimeError)
    return (ServiceCallTimeout, ServiceCallFailed, TimeoutError, OSError, RuntimeError)


class MDF3ServiceInvokeCaller:
    """Call one MDF3 target service through ServiceInvokeSession.

    The session starts a local ControllerTcpServer and ServiceCaller, then
    pushes work to TaskQueue. Downstream workers are selected by service name;
    the client does not address them by IP. Dependencies are injectable so
    the adapter can be tested without contacting a queue.
    """

    def __init__(
        self,
        *,
        config_path: Optional[str] = None,
        endpoint_alias: str = DEFAULT_ENDPOINT_ALIAS,
        environment: str = DEFAULT_ENVIRONMENT,
        audit: AuditWriter,
        success_predicate: Callable[[Mapping[str, Any]], bool],
        caller_service_name: str = DEFAULT_CALLER_SERVICE_NAME,
        session_factory: Optional[Callable[..., Any]] = None,
        extra_sensitive_keys: Iterable[str] = (),
        input_audit_summarizer: Optional[Callable[[Mapping[str, Any]], Any]] = None,
        output_audit_summarizer: Optional[Callable[[Mapping[str, Any]], Any]] = None,
    ) -> None:
        if not endpoint_alias.strip() or not environment.strip():
            raise ContractViolation("endpoint_alias and environment are required")
        if not callable(success_predicate):
            raise ContractViolation("success_predicate must be callable")
        self.config_path = resolve_config_path(config_path, environment=environment)
        inspect_config(self.config_path)
        self.endpoint_alias = endpoint_alias
        self.environment = environment
        self.audit = audit
        self.success_predicate = success_predicate
        self.caller_service_name = caller_service_name
        self._session_factory = session_factory or default_session_factory
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

    def call_once(
        self,
        *,
        service: str,
        input_data: Mapping[str, Any],
        trace_id: str,
        timeout_sec: float,
        run_id: str,
        case_id: str,
        call_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not service.strip() or not trace_id.strip():
            raise ContractViolation("service and trace_id are required")
        if not math.isfinite(float(timeout_sec)) or timeout_sec <= 0:
            raise ContractViolation("timeout_sec must be finite and positive")

        resolved_call_id = call_id or self._call_ids.next(service)
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
                    "input": self._mapping_audit_summary(
                        input_data,
                        self.input_audit_summarizer,
                    ),
                },
            ),
        )

        try:
            session = self._session_factory(
                config_path=str(self.config_path),
                environment=self.environment,
                caller_service_name=self.caller_service_name,
            )
            with session as active_session:
                result = active_session.invoke(
                    service,
                    dict(input_data),
                    trace_id=trace_id,
                    timeout=float(timeout_sec),
                )
        except _invoke_exceptions() as exc:
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
        except Exception as exc:
            self.audit.write(
                "request_ambiguous",
                **dict(
                    common,
                    **{
                        "status": "invoke_unknown",
                        "error_type": type(exc).__name__,
                    },
                ),
            )
            raise AmbiguousOutcome(
                "%s invoke outcome is unknown; not retried" % service,
                call_id=resolved_call_id,
            ) from exc

        if not isinstance(result, dict):
            self.audit.write(
                "request_finished",
                **dict(
                    common,
                    **{
                        "status": "invalid_output",
                        "output_type": type(result).__name__,
                    },
                ),
            )
            raise ContractViolation(
                "%s returned %s, expected dict"
                % (service, type(result).__name__),
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
                        "predicate_error_type": type(exc).__name__,
                        "output": self._mapping_audit_summary(
                            result,
                            self.output_audit_summarizer,
                        ),
                    },
                ),
            )
            raise ContractViolation(
                "%s success predicate raised %s" % (service, type(exc).__name__),
                call_id=resolved_call_id,
            ) from exc
        if succeeded is not True:
            self.audit.write(
                "request_finished",
                **dict(
                    common,
                    **{
                        "status": "failed",
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
                    "output": self._mapping_audit_summary(
                        result,
                        self.output_audit_summarizer,
                    ),
                },
            ),
        )
        return result
