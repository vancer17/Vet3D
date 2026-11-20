"""Safe progress snapshots and streaming CLI presentation, without API side effects."""
import json
import math
from datetime import datetime, timezone

from hi3d_client import IMAGE_KINDS
from hi3d_storage import IMAGE_FAILURE_ACTION, QUERY_FAILURE_ACTION, task_failure


def number(value, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if (isinstance(value, float) and not math.isfinite(value)) or value < 0 or (maximum is not None and value > maximum):
        return None
    return value


def progress_snapshot(job, observed_at=None):
    """Only expose contract-defined numeric fields and locally known state labels."""
    result = job.get("result") or {}
    state = job.get("state", "created")
    image = job.get("kind") in IMAGE_KINDS
    position = number(result.get("queuePosition" if image else "position"))
    stage = state
    if state == "processing":
        if image:
            stage = {0: "queueing", 1: "dispatched", 2: "processing"}.get(result.get("taskStatus"), state)
        elif position is not None and position > 0:
            stage = "queueing"
    query_error = job.get("last_query_error") or {}
    stale = bool(query_error) and not (state == "failed" and query_error.get("query_failed") is True)
    snapshot = {
        "task_id": job.get("task_id"), "state": state, "stage": "query_error" if stale else stage,
        "percentage": number(result.get("percentage"), 100),
        "queue_position": position, "stale": stale,
        "observed_at": job.get("result_observed_at"),
    }
    if not image:
        snapshot["geometry_percentage"] = number(result.get("percentGeo"), 100)
        snapshot["texture_percentage"] = number(result.get("percentTex"), 100)
    # Elapsed wall time is not an ETA or a synthetic percentage.
    started = job.get("submitted_at") or job.get("created_at") or job.get("adopted_at")
    snapshot["elapsed_seconds"] = None
    try:
        start = datetime.fromisoformat(started.replace("Z", "+00:00"))
        end = observed_at or datetime.now(timezone.utc)
        if job.get("first_observed_terminal_at"):
            end = datetime.fromisoformat(job["first_observed_terminal_at"].replace("Z", "+00:00"))
        snapshot["elapsed_seconds"] = max(0, int((end - start).total_seconds()))
    except (AttributeError, TypeError, ValueError, OverflowError):
        pass
    return snapshot


def progress_changed(previous, current):
    """Emit stage/queue/error changes or ten percentage points since last emission."""
    if previous is None:
        return True
    if any(previous.get(key) != current.get(key)
           for key in ("state", "stage", "queue_position", "stale")):
        return True
    for key in ("percentage", "geometry_percentage", "texture_percentage"):
        old, new = previous.get(key), current.get(key)
        if (old is None) != (new is None):
            return True
        if old is not None and new is not None and abs(new - old) >= 10:
            return True
    return False


def job_summary(job, path):
    """Small model-facing result; full parameters and assets remain in the job file."""
    summary = {key: job[key] for key in
               ("backend", "kind", "task_id", "parent_task_id", "state", "progress", "error", "last_query_error")
               if key in job}
    if job.get("kind") in IMAGE_KINDS:
        if job.get("state") == "failed" and not summary.get("error"):
            summary["error"] = task_failure(job.get("result") or {})
        if job.get("state") in {"failed", "submission_rejected", "submission_uncertain", "submitting"} or job.get("last_query_error"):
            summary["next_action"] = IMAGE_FAILURE_ACTION
    if job.get("last_query_error"):
        summary["next_action"] = QUERY_FAILURE_ACTION
    summary["job_file"] = str(path)
    return summary


def emit_progress(snapshot, stream, mode="text"):
    """Flush one safe update to the supplied stream; never include response bodies."""
    if mode == "none":
        return
    if mode == "json":
        line = json.dumps({"event": "progress", **snapshot}, ensure_ascii=False, allow_nan=False)
    elif mode == "text":
        labels = {"created": "Adopted", "submitting": "Submitting", "queueing": "Queued",
                  "dispatched": "Dispatched", "processing": "Generating", "success": "Completed",
                  "failed": "Failed", "query_error": "Query failed (showing the last known progress)"}
        parts = [labels.get(snapshot["stage"], "Waiting")]
        for field, label in (("percentage", "Progress"), ("geometry_percentage", "Geometry"),
                             ("texture_percentage", "Texture")):
            value = snapshot.get(field)
            if value is not None:
                parts.append(f"{label} {value:g}%")
        position = snapshot.get("queue_position")
        if position is not None and position > 0:
            parts.append(f"队列位置 {position:g}")
        elapsed = snapshot.get("elapsed_seconds")
        if elapsed is not None:
            parts.append(f"已用时 {elapsed}s")
        line = "[Hi3D] " + " | ".join(parts)
    else:
        raise ValueError("Unsupported progress mode")
    print(line, file=stream, flush=True)
