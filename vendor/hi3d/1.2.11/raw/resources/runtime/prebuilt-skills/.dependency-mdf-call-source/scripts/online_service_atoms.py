#!/usr/bin/env python3
"""Protocol-independent atoms for auditable online service calls.

The module uses only the Python standard library and is compatible with
Python 3.7+.  Project-specific protocols, success predicates, and artifact
parsers are injected by callers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import threading
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
)


SCHEMA_VERSION = 1
SUCCESS_STATUSES = frozenset(("success", "succeeded", "validated"))
TERMINAL_CALL_EVENTS = frozenset(("request_finished", "request_ambiguous"))
_SENSITIVE_KEYS = frozenset(
    (
        "authorization",
        "proxy_authorization",
        "api_key",
        "x_api_key",
        "access_key",
        "access_key_id",
        "secret_access_key",
        "secret_key",
        "token",
        "access_token",
        "refresh_token",
        "password",
        "passwd",
        "cookie",
        "set_cookie",
        "credential",
        "credentials",
        "private_key",
        "signature",
        "signed_url",
    )
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    if type(chunk_size) is not int or chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer")
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def _is_sensitive_key(key: Any, extra_sensitive_keys: Iterable[str]) -> bool:
    normalized = _normalize_key(key)
    extras = {_normalize_key(item) for item in extra_sensitive_keys}
    sensitive_suffixes = (
        "_token",
        "_password",
        "_passwd",
        "_secret",
        "_cookie",
        "_credential",
        "_credentials",
        "_signature",
        "_api_key",
        "_access_key",
        "_private_key",
    )
    return (
        normalized in _SENSITIVE_KEYS
        or normalized in extras
        or normalized.endswith(sensitive_suffixes)
    )


def summarize_for_audit(
    value: Any,
    *,
    extra_sensitive_keys: Iterable[str] = (),
    max_depth: int = 4,
    max_items: int = 16,
    max_string: int = 256,
    _depth: int = 0,
) -> Any:
    """Return a bounded, JSON-safe summary without known credential fields."""

    if _depth == 0:
        extra_sensitive_keys = tuple(extra_sensitive_keys)
    if _depth >= max_depth:
        return {"type": type(value).__name__}

    if is_dataclass(value):
        value = asdict(value)

    content = getattr(value, "content", None)
    if isinstance(content, bytes):
        result = {
            "type": type(value).__name__,
            "size": len(content),
            "sha256": sha256_bytes(content),
        }
        field_name = getattr(value, "field_name", None)
        file_name = getattr(value, "file_name", None)
        if field_name:
            result["field_name"] = str(field_name)
        if file_name:
            result["file_name"] = Path(str(file_name)).name
        return result

    if isinstance(value, bytes):
        return {
            "type": "bytes",
            "size": len(value),
            "sha256": sha256_bytes(value),
        }

    if isinstance(value, Path):
        return {
            "type": "Path",
            "name": value.name,
            "absolute": value.is_absolute(),
        }

    if isinstance(value, Mapping):
        result = {}
        for key, child in value.items():
            key_text = str(key)
            if _is_sensitive_key(key_text, extra_sensitive_keys):
                result[key_text] = "<redacted>"
            else:
                result[key_text] = summarize_for_audit(
                    child,
                    extra_sensitive_keys=extra_sensitive_keys,
                    max_depth=max_depth,
                    max_items=max_items,
                    max_string=max_string,
                    _depth=_depth + 1,
                )
        return result

    if isinstance(value, (list, tuple, set, frozenset)):
        items = list(value)
        source_items = (
            items if isinstance(value, (set, frozenset)) else items[:max_items]
        )
        summarized_items = [
            summarize_for_audit(
                child,
                extra_sensitive_keys=extra_sensitive_keys,
                max_depth=max_depth,
                max_items=max_items,
                max_string=max_string,
                _depth=_depth + 1,
            )
            for child in source_items
        ]
        if isinstance(value, (set, frozenset)):
            summarized_items.sort(
                key=lambda item: json.dumps(
                    item,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
        summarized = summarized_items[:max_items]
        if len(items) > max_items:
            return {
                "type": type(value).__name__,
                "length": len(items),
                "items": summarized,
                "truncated": True,
            }
        return summarized

    if isinstance(value, str):
        if len(value) > max_string:
            encoded = value.encode("utf-8")
            return {
                "type": "str",
                "length": len(value),
                "utf8_size": len(encoded),
                "sha256": sha256_bytes(encoded),
            }
        return value

    if isinstance(value, float):
        if not math.isfinite(value):
            return {"type": "float", "value": str(value)}
        return value

    if isinstance(value, (int, bool)) or value is None:
        return value

    return {"type": type(value).__name__}


def stable_digest(value: Any, *, extra_sensitive_keys: Iterable[str] = ()) -> str:
    """Hash the bounded audit summary; not a complete-input checkpoint key."""
    summarized = summarize_for_audit(
        value,
        extra_sensitive_keys=extra_sensitive_keys,
    )
    encoded = json.dumps(
        summarized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return sha256_bytes(encoded)


class OnlineCallError(RuntimeError):
    """Base class for a classified online call outcome."""

    def __init__(self, message: str, *, call_id: Optional[str] = None) -> None:
        super().__init__(message)
        self.call_id = call_id


class DefinitiveRejection(OnlineCallError):
    """The request is known not to have been accepted."""


class BusinessFailure(OnlineCallError):
    """The service explicitly reported business failure."""


class AmbiguousOutcome(OnlineCallError):
    """The request may have executed, but no authoritative result is known."""


class ContractViolation(OnlineCallError):
    """A local or remote value violates the confirmed contract."""


class ArtifactValidationError(ContractViolation):
    """A returned or persisted artifact failed validation."""


@dataclass(frozen=True)
class RunSpec:
    run_id: str
    case_id: str
    environment: str
    endpoint_alias: str
    protocol: str
    operation: str
    trace_id: str
    timeout_sec: float
    retry_policy: Dict[str, Any]
    success_predicate: str
    validators: Tuple[str, ...] = ()
    side_effects: Tuple[Dict[str, Any], ...] = ()
    input_digest: Optional[str] = None
    input_summary: Optional[Dict[str, Any]] = None
    contract_digest: Optional[str] = None
    runtime_provenance: Optional[str] = None
    idempotency_key: Optional[str] = None
    schema_version: int = SCHEMA_VERSION

    def validate(self) -> None:
        required = {
            "run_id": self.run_id,
            "case_id": self.case_id,
            "environment": self.environment,
            "endpoint_alias": self.endpoint_alias,
            "protocol": self.protocol,
            "operation": self.operation,
            "trace_id": self.trace_id,
            "success_predicate": self.success_predicate,
        }
        missing = sorted(
            key
            for key, value in required.items()
            if not isinstance(value, str) or not value.strip()
        )
        if missing:
            raise ContractViolation("RunSpec missing fields: %s" % ", ".join(missing))
        if not math.isfinite(float(self.timeout_sec)) or float(self.timeout_sec) <= 0:
            raise ContractViolation("RunSpec timeout_sec must be finite and positive")
        if self.schema_version != SCHEMA_VERSION:
            raise ContractViolation(
                "unsupported RunSpec schema_version: %r" % self.schema_version
            )
        max_attempts = self.retry_policy.get("max_attempts", 1)
        if type(max_attempts) is not int or max_attempts < 1:
            raise ContractViolation(
                "retry_policy.max_attempts must be a positive integer"
            )
        automatic = self.retry_policy.get("automatic", False)
        if not isinstance(automatic, bool):
            raise ContractViolation("retry_policy.automatic must be boolean")
        if automatic:
            safe_when = self.retry_policy.get("safe_when")
            if (
                max_attempts < 2
                or not isinstance(safe_when, str)
                or not safe_when.strip()
            ):
                raise ContractViolation(
                    "automatic retries require max_attempts >= 2 and explicit safe_when"
                )
        elif max_attempts != 1:
            raise ContractViolation(
                "non-automatic retry policy must use max_attempts=1"
            )
        valid_side_effects = {"required", "optional", "disabled", "reused"}
        for item in self.side_effects:
            policy = item.get("policy")
            if policy not in valid_side_effects:
                raise ContractViolation("invalid side effect policy: %r" % policy)

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RunSpec":
        data = dict(value)
        data["validators"] = tuple(data.get("validators") or ())
        data["side_effects"] = tuple(data.get("side_effects") or ())
        spec = cls(**data)
        spec.validate()
        return spec


class CallIdFactory:
    def __init__(self, prefix: str = "call") -> None:
        self.prefix = re.sub(r"[^a-zA-Z0-9_.-]+", "-", prefix).strip("-") or "call"
        self._counter = 0
        self._lock = threading.Lock()

    def next(self, operation: str) -> str:
        with self._lock:
            self._counter += 1
            counter = self._counter
        safe_operation = (
            re.sub(r"[^a-zA-Z0-9_.-]+", "-", operation).strip("-") or "operation"
        )
        return "%s-%03d-%s" % (self.prefix, counter, safe_operation)


class AuditWriter:
    """Append thread-safe, secret-aware JSONL audit records."""

    def __init__(
        self,
        path: Any,
        *,
        extra_sensitive_keys: Iterable[str] = (),
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.extra_sensitive_keys = tuple(extra_sensitive_keys)
        self._lock = threading.Lock()

    def write(self, event: str, **data: Any) -> Dict[str, Any]:
        if not event.strip():
            raise ValueError("audit event cannot be empty")
        record = {
            "schema_version": SCHEMA_VERSION,
            "time_utc": utc_now(),
            "event": event,
        }
        record.update(data)
        safe_record = summarize_for_audit(
            record,
            extra_sensitive_keys=self.extra_sensitive_keys,
            max_depth=8,
            max_items=64,
            max_string=512,
        )
        encoded = json.dumps(
            safe_record,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
        )
        with self._lock:
            descriptor = os.open(
                str(self.path),
                os.O_WRONLY | os.O_APPEND | os.O_CREAT,
                0o600,
            )
            with os.fdopen(descriptor, "a", encoding="utf-8") as stream:
                stream.write(encoded + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        return safe_record


def atomic_write_bytes(path: Any, content: bytes, mode: int = 0o600) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(
        ".%s.%d.%d.tmp" % (destination.name, os.getpid(), threading.get_ident())
    )
    descriptor = None
    try:
        descriptor = os.open(
            str(temporary),
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            mode,
        )
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temporary), str(destination))
        try:
            directory_fd = os.open(str(destination.parent), os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return destination


def atomic_write_json(path: Any, value: Any, mode: int = 0o600) -> Path:
    content = (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    return atomic_write_bytes(path, content, mode=mode)


def validate_file(
    path: Any,
    *,
    min_size: int = 1,
    expected_size: Optional[int] = None,
    expected_sha256: Optional[str] = None,
    parser: Optional[Callable[[Path], Any]] = None,
) -> Dict[str, Any]:
    artifact = Path(path)
    if not artifact.is_file():
        raise ArtifactValidationError("artifact is not a file: %s" % artifact)
    size = artifact.stat().st_size
    if size < min_size:
        raise ArtifactValidationError(
            "artifact is too small: %s < %s" % (size, min_size)
        )
    if expected_size is not None and size != expected_size:
        raise ArtifactValidationError(
            "artifact size mismatch: %s != %s" % (size, expected_size)
        )
    digest = sha256_file(artifact)
    if expected_sha256 is not None and digest.lower() != expected_sha256.lower():
        raise ArtifactValidationError("artifact sha256 mismatch: %s" % artifact)
    parser_result = None
    parser_name = None
    if parser is not None:
        parser_result = parser(artifact)
        parser_name = getattr(parser, "__name__", type(parser).__name__)
    return {
        "status": "validated",
        "path": str(artifact),
        "size": size,
        "sha256": digest,
        "parser": parser_name,
        "assertions": summarize_for_audit(parser_result),
        "validated_at": utc_now(),
    }


def load_jsonl(path: Any) -> List[Dict[str, Any]]:
    records = []
    with Path(path).open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except ValueError as exc:
                raise ContractViolation(
                    "invalid JSONL at line %d: %s" % (line_number, exc)
                )
            if not isinstance(value, dict):
                raise ContractViolation("audit line %d is not an object" % line_number)
            records.append(value)
    return records


@dataclass(frozen=True)
class AuditReport:
    trace_id: Optional[str]
    records: int
    sent: int
    succeeded: int
    failed: int
    ambiguous: int
    open_call_ids: Tuple[str, ...]
    failed_call_ids: Tuple[str, ...]
    ambiguous_call_ids: Tuple[str, ...]
    errors: Tuple[str, ...]
    allow_incomplete: bool

    @property
    def structure_ok(self) -> bool:
        return not self.errors

    @property
    def complete(self) -> bool:
        return not self.open_call_ids

    @property
    def ok(self) -> bool:
        incomplete_ok = self.allow_incomplete or self.complete
        return (
            self.structure_ok
            and incomplete_ok
            and self.failed == 0
            and self.ambiguous == 0
        )

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result.update(
            {
                "structure_ok": self.structure_ok,
                "complete": self.complete,
                "ok": self.ok,
            }
        )
        return result


def verify_audit_records(
    records: Sequence[Mapping[str, Any]],
    *,
    trace_id: Optional[str] = None,
    allow_incomplete: bool = False,
) -> AuditReport:
    selected = [
        dict(record)
        for record in records
        if trace_id is None or record.get("trace_id") == trace_id
    ]
    errors = []
    if not selected:
        errors.append("no audit records selected")

    calls = {}  # type: Dict[str, List[Dict[str, Any]]]
    for index, record in enumerate(selected, 1):
        event = record.get("event")
        if event not in ({"request_sent"} | set(TERMINAL_CALL_EVENTS)):
            continue
        call_id = record.get("call_id")
        if not isinstance(call_id, str) or not call_id:
            errors.append("call event %d lacks call_id" % index)
            continue
        calls.setdefault(call_id, []).append(record)

    if selected and not calls:
        errors.append("no request call events selected")

    sent = succeeded = failed = ambiguous = 0
    open_call_ids = []
    failed_call_ids = []
    ambiguous_call_ids = []
    for call_id, call_records in sorted(calls.items()):
        sent_records = [
            item for item in call_records if item.get("event") == "request_sent"
        ]
        terminal_records = [
            item for item in call_records if item.get("event") in TERMINAL_CALL_EVENTS
        ]
        sent += len(sent_records)
        if len(sent_records) != 1:
            errors.append(
                "%s has %d request_sent events" % (call_id, len(sent_records))
            )
        elif sent_records[0].get("retries") != 0:
            errors.append("%s request_sent must record retries=0" % call_id)
        if len(terminal_records) > 1:
            errors.append(
                "%s has %d terminal events" % (call_id, len(terminal_records))
            )
            continue
        if not terminal_records:
            open_call_ids.append(call_id)
            continue
        terminal = terminal_records[0]
        if sent_records:
            sent_record = sent_records[0]
            for field in ("trace_id", "service", "operation"):
                sent_value = sent_record.get(field)
                terminal_value = terminal.get(field)
                if (
                    sent_value is not None
                    and terminal_value is not None
                    and sent_value != terminal_value
                ):
                    errors.append("%s %s changes across call events" % (call_id, field))
        if terminal.get("event") == "request_ambiguous":
            ambiguous += 1
            ambiguous_call_ids.append(call_id)
            continue
        status = str(terminal.get("status", "")).lower()
        if status in SUCCESS_STATUSES:
            succeeded += 1
        else:
            failed += 1
            failed_call_ids.append(call_id)

    if open_call_ids and not allow_incomplete:
        errors.append("open calls: %s" % ", ".join(open_call_ids))

    return AuditReport(
        trace_id=trace_id,
        records=len(selected),
        sent=sent,
        succeeded=succeeded,
        failed=failed,
        ambiguous=ambiguous,
        open_call_ids=tuple(open_call_ids),
        failed_call_ids=tuple(failed_call_ids),
        ambiguous_call_ids=tuple(ambiguous_call_ids),
        errors=tuple(errors),
        allow_incomplete=allow_incomplete,
    )


@dataclass(frozen=True)
class CheckpointDecision:
    reusable: bool
    reasons: Tuple[str, ...]
    validation: Optional[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def evaluate_checkpoint(
    checkpoint: Mapping[str, Any],
    *,
    input_digest: str,
    contract_digest: str,
    parameter_digest: str,
    parser: Optional[Callable[[Path], Any]] = None,
) -> CheckpointDecision:
    """Revalidate an exact-input checkpoint before allowing reuse."""

    reasons = []
    expected = {
        "input_digest": input_digest,
        "contract_digest": contract_digest,
        "parameter_digest": parameter_digest,
    }
    if checkpoint.get("status") != "validated":
        reasons.append("checkpoint status is not validated")
    for field, expected_value in expected.items():
        if checkpoint.get(field) != expected_value:
            reasons.append("%s mismatch" % field)
    artifact = checkpoint.get("artifact")
    if not isinstance(artifact, Mapping):
        reasons.append("checkpoint artifact is missing")
        return CheckpointDecision(False, tuple(reasons), None)
    path = artifact.get("path")
    if not isinstance(path, str) or not path:
        reasons.append("checkpoint artifact path is missing")
        return CheckpointDecision(False, tuple(reasons), None)
    if type(artifact.get("size")) is not int or artifact["size"] < 1:
        reasons.append("checkpoint artifact size is missing or invalid")
    digest = artifact.get("sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", digest):
        reasons.append("checkpoint artifact sha256 is missing or invalid")
    if reasons:
        return CheckpointDecision(False, tuple(reasons), None)
    try:
        validation = validate_file(
            path,
            expected_size=artifact.get("size"),
            expected_sha256=artifact.get("sha256"),
            parser=parser,
        )
    except Exception as exc:
        reasons.append("artifact validation failed: %s" % type(exc).__name__)
        return CheckpointDecision(False, tuple(reasons), None)
    return CheckpointDecision(True, (), validation)
