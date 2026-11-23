"""Append stage timing without credentials, request bodies, or model usage estimates."""

from contextlib import contextmanager
from datetime import datetime
import json
from pathlib import Path
from time import monotonic


@contextmanager
def record_stage(path, task, stage, attempt="1"):
    start = datetime.now().astimezone().isoformat()
    clock = monotonic()
    status = "complete"
    try:
        yield
    except BaseException:
        status = "failed_or_interrupted"
        raise
    finally:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    {
                        "task_id": task,
                        "stage": stage,
                        "attempt": attempt,
                        "status": status,
                        "start": start,
                        "end": datetime.now().astimezone().isoformat(),
                        "seconds": monotonic() - clock,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
