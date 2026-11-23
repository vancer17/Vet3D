"""Local staged path and timing contracts; no Blender/service calls."""
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import json
import time
from types import SimpleNamespace
from frame_runtime import validate_paths


def paths_overlap(a, b):
    """True for equal/resolved ancestor paths, including existing symlink aliases."""
    a, b = Path(a).expanduser().resolve(), Path(b).expanduser().resolve()
    return a == b or a in b.parents or b in a.parents


def prepare_paths(*, output, raw_inputs=None, derived_inputs=None, work=None):
    """Validate without writes; protect package and original input files.

    Derived inputs may be in the output tree for staged replay, but callers must
    not overwrite the derived input itself. Raw inputs must stay outside output
    and work trees. Returns resolved output, work and named input paths.
    """
    raw_inputs = raw_inputs or {}
    derived_inputs = derived_inputs or {}
    resolved = {}
    for name, value in {**raw_inputs, **derived_inputs}.items():
        path = Path(value).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f'{name} must be an existing file: {path}')
        resolved[name] = path
    roots = {'output': output}
    if work is not None:
        roots['work'] = work
    package = Path(__file__).resolve().parents[1]
    for name, value in roots.items():
        option = SimpleNamespace(output=value)
        validate_paths(option)
        path = option.output
        if path.exists() and not path.is_dir():
            raise ValueError(f'{name} must be a directory: {path}')
        if paths_overlap(path, package):
            raise ValueError(f'{name} overlaps the Skill package')
        for source_name in raw_inputs:
            if paths_overlap(path, resolved[source_name]):
                raise ValueError(f'{name} overlaps original input {source_name}')
        roots[name] = path
    return roots, resolved


def require_distinct_outputs(inputs, outputs):
    """Reject output files that alias any declared source before writing them."""
    sources = [Path(p).expanduser().resolve() for p in inputs]
    for output in outputs:
        destination = Path(output).expanduser().resolve()
        if any(destination == source for source in sources):
            raise ValueError('A generated file must not overwrite its source')






@contextmanager
def timed_stage(*, log, task_id, attempt_id, stage, parent_stage=None, resume_of=None):
    """Append actual local stage timing; caller validates the log root first."""
    started = datetime.now().astimezone().isoformat()
    clock = time.monotonic()
    status, failure_type = 'succeeded', None
    try:
        yield
    except BaseException as error:
        status = 'interrupted' if isinstance(error, KeyboardInterrupt) else 'failed'
        failure_type = type(error).__name__
        raise
    finally:
        record = dict(task_id=task_id, attempt_id=attempt_id, stage_id=stage,
                      parent_stage=parent_stage, resume_of=resume_of, status=status,
                      started_at=started, ended_at=datetime.now().astimezone().isoformat(),
                      duration_seconds=time.monotonic()-clock, clock_source='time.monotonic',
                      scope='local selected stage', failure_type=failure_type)
        log = Path(log)
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(record, ensure_ascii=False)+'\n')
