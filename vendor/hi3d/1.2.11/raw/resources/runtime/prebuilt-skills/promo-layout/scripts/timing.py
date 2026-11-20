"""Small, single-writer timing journal; no cache, recovery, or token estimates.

All paths belong to the task output directory. JSON and JSONL changes replace a
temporary file atomically; JSONL retains prior events. Callers must serialize
writes to one run directory. External records contain measured values or an
explicit ``missing_reason``; this module never infers missing times.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import tempfile
import time


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _identifier(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(field + " must be a non-empty string")
    return value


def _timestamp(value, field):
    if not isinstance(value, str):
        raise ValueError(field + " must be an ISO timestamp with a timezone")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("Timezone is required")
    except ValueError as exc:
        raise ValueError(field + " must be an ISO timestamp with a timezone") from exc
    return parsed.astimezone(timezone.utc).isoformat()


def _finite_number(value, field, nonnegative=True):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(field + " must be a finite number")
    if nonnegative and value < 0:
        raise ValueError(field + " must be non-negative")
    return value


def _atomic_text(path, content):
    """Replace one file, retaining the previous complete file on write failure."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix="." + path.name + ".", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _append_event(run_dir, record):
    path = Path(run_dir) / "timings.jsonl"
    event = dict(record, recorded_at=_utc_now())
    line = json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n"
    previous = path.read_text(encoding="utf-8") if path.exists() else ""
    if previous and not previous.endswith("\n"):
        raise ValueError("timings.jsonl has an incomplete final event; preserve and inspect it")
    _atomic_text(path, previous + line)


def write_json(path, value):
    """Atomically write a task report with the journal's shared file adapter."""
    _atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def _validated_record(record):
    if not isinstance(record, dict):
        raise ValueError("Stage record must be an object")
    result = dict(record)
    for field in ("task_id", "attempt_id", "stage"):
        _identifier(result.get(field), field)
    previous = result.setdefault("previous_attempt_id", None)
    if previous is not None:
        _identifier(previous, "previous_attempt_id")
    if result.get("status") not in {"completed", "failed", "interrupted", "skipped"}:
        raise ValueError("External records must have a final stage status")
    for field in ("started_at", "ended_at"):
        value = result.setdefault(field, None)
        if value is not None:
            result[field] = _timestamp(value, field)
    if result["started_at"] is not None and result["ended_at"] is not None:
        if datetime.fromisoformat(result["ended_at"]) < datetime.fromisoformat(result["started_at"]):
            raise ValueError("ended_at must not precede started_at")
    elapsed = result.setdefault("elapsed_seconds", None)
    if result["status"] == "skipped":
        _identifier(result.get("reason"), "reason")
        if any(result[field] is not None for field in ("started_at", "ended_at", "elapsed_seconds")):
            raise ValueError("A skipped stage has no execution timestamps or elapsed time")
        result.setdefault("missing_reason", "Stage was not executed: " + result["reason"])
        result.setdefault("timing_method", "not_executed")
    else:
        if elapsed is not None:
            _finite_number(elapsed, "elapsed_seconds")
        if any(result[field] is None for field in ("started_at", "ended_at", "elapsed_seconds")):
            _identifier(result.get("missing_reason"), "missing_reason")
        if elapsed is None:
            result.setdefault("timing_method", "unavailable")
    _identifier(result.get("timing_method"), "timing_method")
    # Check optional caller metadata before any file is changed.
    json.dumps(result, allow_nan=False)
    return result


def record_external_stage(run_dir, record):
    """Validate and append a measured external final record, without a summary.

    Required identity fields are task_id, attempt_id and stage. Timestamps must
    include a timezone and are normalized to UTC. Missing timestamps/duration
    stay null and require missing_reason. Supply timing_method for a measured
    duration. A skipped phase instead requires reason and no execution times.
    This function does not derive a duration from wall-clock timestamps.
    """
    normalized = _validated_record(record)
    _append_event(run_dir, normalized)
    return normalized


class StageRecorder:
    """Record one attempt with explicit lineage and measured stage durations.

    Optional started_at/started_clock must come from the same process and be
    supplied together, for example to include a preflight performed before the
    output directory was known. add_record then incorporates that measured
    preflight. A new recorder always represents a new caller-specified attempt;
    existing journal events are retained but never treated as cached work.
    """

    def __init__(self, run_dir, task_id, attempt_id, previous_attempt_id=None,
                 started_at=None, started_clock=None):
        self.run_dir = Path(run_dir)
        self.task_id = _identifier(task_id, "task_id")
        self.attempt_id = _identifier(attempt_id, "attempt_id")
        self.previous_attempt_id = previous_attempt_id
        if previous_attempt_id is not None:
            _identifier(previous_attempt_id, "previous_attempt_id")
        if (started_at is None) != (started_clock is None):
            raise ValueError("started_at and started_clock must be provided together")
        now_clock = time.monotonic()
        if started_clock is not None:
            _finite_number(started_clock, "started_clock", nonnegative=False)
            if started_clock > now_clock:
                raise ValueError("started_clock is later than the current monotonic clock")
        self.started_clock = now_clock if started_clock is None else started_clock
        self.started_at = _utc_now() if started_at is None else _timestamp(started_at, "started_at")
        self.records = []
        self._active = 0
        self._summary = None
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def _ensure_open(self):
        if self._summary is not None:
            raise RuntimeError("This attempt has already finished")

    def _identity(self, name):
        return dict(
            task_id=self.task_id, attempt_id=self.attempt_id,
            previous_attempt_id=self.previous_attempt_id,
            stage=_identifier(name, "stage"),
        )

    def _complete_stage(self, record, clock, status):
        record.update(
            status=status, ended_at=_utc_now(),
            elapsed_seconds=time.monotonic() - clock,
        )
        record.pop("missing_reason", None)
        self.records.append(dict(record))
        _append_event(self.run_dir, record)

    @contextmanager
    def stage(self, name):
        """Yield a record; retain failure/interruption and re-raise it unchanged."""
        self._ensure_open()
        clock = time.monotonic()
        record = self._identity(name)
        record.update(
            status="running", started_at=_utc_now(), ended_at=None,
            elapsed_seconds=None, timing_method="monotonic",
            timing_scope="This stage invocation; nested stages are included",
            missing_reason="Stage is still running; no end has been observed",
        )
        # Persist the start before invoking the action, including for hard kills.
        _append_event(self.run_dir, record)
        self._active += 1
        try:
            yield record
        except BaseException as exc:
            record["error_type"] = type(exc).__name__
            status = "interrupted" if isinstance(exc, (KeyboardInterrupt, SystemExit, GeneratorExit)) else "failed"
            try:
                self._complete_stage(record, clock, status)
            except Exception as write_error:
                # A journal failure must not turn an interruption into another
                # exception. The start event and in-memory record are retained.
                if hasattr(exc, "add_note"):
                    exc.add_note("Could not persist the final timing event: " + type(write_error).__name__)
            raise
        else:
            self._complete_stage(record, clock, "completed")
        finally:
            self._active -= 1

    def add_record(self, record):
        """Append an already measured final stage to this attempt and summary."""
        self._ensure_open()
        if not isinstance(record, dict):
            raise ValueError("Stage record must be an object")
        complete = dict(record)
        for field, value in self._identity(record.get("stage")).items():
            if field in complete and complete[field] != value:
                raise ValueError("Stage record does not belong to this attempt: " + field)
            complete[field] = value
        normalized = record_external_stage(self.run_dir, complete)
        self.records.append(dict(normalized))
        return normalized

    def skip(self, name, reason):
        """Record non-execution without fabricating a zero-duration interval."""
        return self.add_record(dict(
            stage=name, status="skipped", reason=_identifier(reason, "reason"),
            started_at=None, ended_at=None, elapsed_seconds=None,
            timing_method="not_executed",
            missing_reason="Stage was not executed: " + reason,
        ))

    def finish(self, status):
        """Write this attempt's wall-clock summary; nested times are not added."""
        _identifier(status, "status")
        if self._summary is not None:
            if self._summary["status"] != status:
                raise RuntimeError("Cannot change the status of a finished attempt")
            return self._summary
        if self._active:
            raise RuntimeError("Cannot finish while a stage is still running")
        summary = dict(
            task_id=self.task_id, attempt_id=self.attempt_id,
            previous_attempt_id=self.previous_attempt_id, status=status,
            started_at=self.started_at, ended_at=_utc_now(),
            elapsed_seconds=time.monotonic() - self.started_clock,
            timing_method="monotonic", stages=list(self.records),
            timing_scope="This attempt's start/end interval; stage and nested durations are contained, not summed",
            history="timings.jsonl",
        )
        write_json(self.run_dir / "timing_summary.json", summary)
        self._summary = summary
        return summary
