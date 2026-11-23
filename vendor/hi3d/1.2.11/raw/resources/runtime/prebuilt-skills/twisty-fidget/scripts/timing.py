"""Append-only stage timing. No tokens, environment, commands or credentials are logged."""
import time
from stage_events import record_stage, utc_now, append_event
from contextlib import contextmanager


@contextmanager
def stage(path, task_id, attempt_id, name, previous_attempt_id=None):
    def emit(record):
        event = dict(record)
        event.pop('missing_reason', None)
        event.update(task_id=task_id, attempt_id=attempt_id, previous_attempt_id=previous_attempt_id)
        if event['status'] != 'running': event.setdefault('error_type', None)
        append_event(path, event)
    with record_stage(name, emit, [], now=utc_now, clock=time.monotonic, wall_first=False):
        yield
