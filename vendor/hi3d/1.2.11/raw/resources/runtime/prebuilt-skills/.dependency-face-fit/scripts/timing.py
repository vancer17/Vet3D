"""Append business stage attempts, including failures; never log exception values."""

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
import json
import uuid


@contextmanager
def stage(path, name, task_id=None, parent_id=None):
    start = datetime.now(timezone.utc).isoformat()
    tick = monotonic()
    row = dict(
        stage=name,
        attempt_id=uuid.uuid4().hex,
        task_id=task_id or str(Path(path).parent),
        parent_id=parent_id,
        start=start,
        status="running",
    )
    try:
        yield row
    except BaseException as error:
        row.update(
            status="interrupted"
            if isinstance(error, (KeyboardInterrupt, SystemExit))
            else "failed",
            error_type=type(error).__name__,
        )
        raise
    else:
        row["status"] = "succeeded"
    finally:
        row.update(
            end=datetime.now(timezone.utc).isoformat(), seconds=monotonic() - tick
        )
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as stream:
            stream.write(json.dumps(row, allow_nan=False) + "\n")
