"""Registration-compatible content journal; retains workflow.json and seconds fields."""
from pathlib import Path
from uuid import uuid4
import json
import time
from checkpoints import digest, artifacts_match
from stage_events import utc_now as utc

class Journal:
    """Append start/end events; cache only complete stages whose artifacts still match."""

    def __init__(self, root):
        self.root = root
        self.path = root / "timings.jsonl"
        self.attempt = uuid4().hex
        self.state_path = root / "workflow.json"
        self.state = (
            json.loads(self.state_path.read_text())
            if self.state_path.exists()
            else dict(task_id=uuid4().hex, stages={})
        )
        self.records = []
        if self.path.exists():
            events = [json.loads(line) for line in self.path.read_text().splitlines()]
            pending = {}
            for e in events:
                key = (e["attempt_id"], e["stage"])
                if e["status"] == "running":
                    pending[key] = e
                else:
                    pending.pop(key, None)
            for e in pending.values():
                self.append(
                    dict(
                        e,
                        status="interrupted",
                        ended_at=utc(),
                        seconds=None,
                        reason="Prior process ended without an end event; elapsed time is unavailable",
                    )
                )
        self.save()

    def save(self):
        temp = self.state_path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.state, indent=2))
        temp.replace(self.state_path)

    def append(self, event):
        with self.path.open("a") as stream:
            stream.write(json.dumps(event) + "\n")

    def stage(self, name, key, outputs, action, enabled=True):
        start = time.monotonic()
        record = dict(
            task_id=self.state["task_id"],
            attempt_id=self.attempt,
            stage=name,
            started_at=utc(),
            status="running",
        )
        self.append(record)
        old = self.state["stages"].get(name, {})
        try:
            if not enabled:
                status = "skipped"
                reason = "Optional stage not requested"
            elif (key is not None and old.get("signature") == key
                  and artifacts_match(old.get("artifacts"), expected=outputs)):
                status = "skipped"
                reason = "Verified content cache"
                record["reused_attempt_id"] = old["attempt_id"]
            else:
                print("STAGE", name, flush=True)
                action()
                for p in outputs:
                    if not Path(p).is_file():
                        raise RuntimeError(f"Missing stage artifact: {p}")
                status = "completed"
                reason = None
                self.state["stages"][name] = dict(
                    signature=key,
                    artifacts={str(p): digest(p) for p in outputs},
                    attempt_id=self.attempt,
                )
                self.save()
        except BaseException as exc:
            status = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
            record.update(
                status=status,
                ended_at=utc(),
                seconds=time.monotonic() - start,
                reason=type(exc).__name__,
            )
            self.append(record)
            self.records.append(record)
            raise
        record.update(
            status=status,
            ended_at=utc(),
            seconds=time.monotonic() - start,
            reason=reason,
        )
        self.append(record)
        self.records.append(record)
