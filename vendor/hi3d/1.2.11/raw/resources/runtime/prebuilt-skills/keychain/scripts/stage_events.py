"""Shared start/end lifecycle for legacy append-only timing profiles."""
from contextlib import contextmanager
from datetime import datetime, timezone
import time
import json


def utc_now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def record_stage(name, emit, records, *, missing_reason="End not observed", timing_method="monotonic", now=None, clock=None, wall_first=False):
    """Append running and terminal records, retaining legacy elapsed_seconds fields.

    emit attaches task identity and writes; records accumulates terminal events.
    KeyboardInterrupt/SystemExit are interrupted, other errors failed and reraised.
    """
    now, clock = now or utc_now, clock or time.monotonic
    if wall_first:
        started_at, started_clock = now(), clock()
    else:
        started_clock, started_at = clock(), now()
    record = dict(stage=name, started_at=started_at, ended_at=None, elapsed_seconds=None,
                  status="running", missing_reason=missing_reason)
    if timing_method is not None:
        record["timing_method"] = timing_method
    emit(record)
    try:
        yield
    except BaseException as error:
        record["status"] = "interrupted" if isinstance(error, (KeyboardInterrupt, SystemExit)) else "failed"
        record["error_type"] = type(error).__name__
        raise
    else:
        record["status"] = "completed"
    finally:
        record.update(ended_at=now(), elapsed_seconds=clock()-started_clock)
        record.pop("missing_reason")
        emit(record)
        records.append(record)

def append_event(path, event):
    """Append one strict JSONL record; caller owns the directory, I/O errors propagate."""
    with open(path, 'a', encoding='utf-8') as stream:
        stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False)+'\n')
