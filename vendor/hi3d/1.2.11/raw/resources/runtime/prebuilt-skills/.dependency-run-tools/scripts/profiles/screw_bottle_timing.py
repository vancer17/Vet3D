"""Business-stage timing; callers own the external task directory and identifiers."""
from contextlib import contextmanager
import time
from stage_events import record_stage, utc_now, append_event


@contextmanager
def stage(path, task_id, attempt_id, stage_id, previous_attempt_id=None):
    def emit(record):
        event = dict(record)
        event.pop('missing_reason', None)
        event['stage_id'] = event.pop('stage')
        event.update(task_id=task_id, attempt_id=attempt_id, previous_attempt_id=previous_attempt_id)
        if event['status'] != 'running': event.setdefault('error_type', None)
        append_event(path, event)
    with record_stage(stage_id, emit, [], now=utc_now, clock=time.monotonic, wall_first=True):
        yield


def skipped(path, task_id, attempt_id, stage_id, reason, previous_attempt_id=None):
    append_event(path, {'task_id': task_id, 'attempt_id': attempt_id, 'stage_id': stage_id,
                       'previous_attempt_id': previous_attempt_id, 'status': 'skipped',
                       'started_at': None, 'ended_at': None, 'elapsed_seconds': None, 'reason': reason})
