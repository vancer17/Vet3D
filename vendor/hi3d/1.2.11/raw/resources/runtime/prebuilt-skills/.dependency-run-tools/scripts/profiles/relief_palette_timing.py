"""Append-only, single-writer business-stage timing in the external run directory."""
from stage_events import record_stage
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import uuid


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name+'.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    temporary.replace(path)


class Recorder:
    def __init__(self, directory, task_id, previous_attempt_id=None):
        self.directory = Path(directory)
        self.identity = dict(task_id=task_id, attempt_id=uuid.uuid4().hex, previous_attempt_id=previous_attempt_id)
        self.start, self.clock = now(), time.monotonic()
        self.records = []

    def append(self, record):
        with (self.directory/'timings.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(dict(self.identity, **record), ensure_ascii=False, allow_nan=False)+'\n')

    def stage(self, name):
        return record_stage(name, self.append, self.records)

    def skip(self, name, reason):
        record = dict(stage=name, status='skipped', reason=reason, started_at=None,
                      ended_at=None, elapsed_seconds=None, timing_method='not_executed')
        self.append(record)
        self.records.append(record)

    def finish(self, status):
        result = dict(self.identity, started_at=self.start, ended_at=now(),
                      elapsed_seconds=time.monotonic()-self.clock, status=status, stages=self.records,
                      scope='This local attempt only; contained stages are not added. External stages are recorded separately.')
        write_json(self.directory/'timing_summary.json', result)
        return result
