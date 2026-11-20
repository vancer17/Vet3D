"""Append-only timing for explicitly wrapped business stages, not an auto tracer.

One writer per JSONL file. Use separate files for concurrent workers and combine
records for summary. Logs belong in task output, never in the installed skill.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import uuid


def timestamp():
    """Return an aware UTC ISO timestamp from the wall clock."""
    return datetime.now(timezone.utc).isoformat()


def append_record(path, record):
    """Append one UTF-8 JSONL event, creating its parent; IO errors propagate."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n')


@contextmanager
def stage(path, task_id, stage_id, *, attempt=1, parent_id=None, scope='stage'):
    """Yield a run ID; append start/end and measured elapsed seconds.

    Exceptions are recorded by type and re-raised; their messages are not logged.
    SIGKILL cannot emit an end event. Each retry gets a new run ID with the same
    task/stage ID and a caller-supplied higher attempt. Parent is another run ID.
    """
    if not task_id or not stage_id or attempt < 1 or scope not in ('stage', 'task'):
        raise ValueError('invalid timing identity, attempt or scope')
    base = dict(task_id=task_id, stage_id=stage_id, run_id=uuid.uuid4().hex,
                attempt=attempt, parent_id=parent_id, scope=scope,
                started_at=timestamp(), clock='monotonic')
    start = time.monotonic()
    append_record(path, dict(base, status='running', event='start'))
    status = 'completed'
    failure = {}
    try:
        yield base['run_id']
    except BaseException as exc:
        status = 'interrupted' if isinstance(exc, (KeyboardInterrupt, SystemExit)) else 'failed'
        failure = {'exception_type': type(exc).__name__}
        raise
    finally:
        append_record(path, dict(base, event='end', status=status, ended_at=timestamp(),
                                elapsed_seconds=time.monotonic() - start, **failure))


def skipped(path, task_id, stage_id, reason, *, attempt=1, parent_id=None):
    """Append an explicit unexecuted stage with null timing, not fictitious zero."""
    append_record(path, dict(task_id=task_id, stage_id=stage_id, attempt=attempt,
                            parent_id=parent_id, run_id=uuid.uuid4().hex,
                            scope='stage', event='skip', status='skipped',
                            recorded_at=timestamp(), started_at=None, ended_at=None,
                            elapsed_seconds=None, reason=reason))


def summarize(records, task_id):
    """Return latest event per attempt plus whole-task wall span; no stage sums.

    Only explicit scope=task intervals define overall elapsed time. An unfinished
    task interval yields null total. Parent/child times remain inclusive.
    """
    latest = {}
    for record in records:
        if record['task_id'] == task_id:
            latest[record['run_id']] = record
    events = list(latest.values())
    roots = [r for r in events if r['scope'] == 'task' and r['event'] != 'skip']
    total = None
    if roots and all(r.get('ended_at') for r in roots):
        start = min(datetime.fromisoformat(r['started_at']) for r in roots)
        end = max(datetime.fromisoformat(r['ended_at']) for r in roots)
        if start.tzinfo is None or end.tzinfo is None or end < start:
            raise ValueError('invalid whole-task wall interval')
        total = (end - start).total_seconds()
    return {'task_id': task_id, 'attempts': events, 'wall_elapsed_seconds': total,
            'coverage': 'recorded intervals only; running events lack end evidence',
            'total_basis': 'explicit task wall interval, includes gaps and retries; not stage sum'}
