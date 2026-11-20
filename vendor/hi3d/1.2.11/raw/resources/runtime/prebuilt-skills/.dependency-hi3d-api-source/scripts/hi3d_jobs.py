"""Durable single-submit jobs; server responses remain transient and unlogged."""

import re
import time
from pathlib import Path
from urllib.parse import urlencode

from hi3d_client import CREATE, QUERY
from hi3d_parameters import multipart
from hi3d_storage import load, now, public_record, save

STATES = {"created", "queueing", "processing", "success", "failed"}


def task_identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,200}", value):
        raise ValueError(
            "Expected a task identifier containing letters, digits, dots, underscores or hyphens"
        )
    return value


def response_error(status, body):
    code = str(body.get("code", ""))
    return {
        "http_status": status,
        "code": int(code) if re.fullmatch(r"[0-9]{1,12}", code) else None,
    }


def adopt_job(kind, task_id, path):
    if kind not in QUERY:
        raise ValueError("Unsupported task kind")
    job = {
        "schema_version": 1,
        "kind": kind,
        "task_id": task_identifier(task_id),
        "state": "created",
        "adopted_at": now(),
    }
    save(path, job, exclusive=True)
    return job


def submit_job(client, path, planned):
    if Path(path).exists():
        old = load(path)
        if old.get("fingerprint") != planned["fingerprint"]:
            raise ValueError("Job belongs to a different plan; preserve it")
        return {"reused": True, "job": old}
    # Verify bytes before authentication or creating intent. Keep this exact stream.
    with multipart(planned["parameters"], planned["files"]) as (
        data,
        content_type,
        length,
    ):
        client.auth()
        job = {
            "schema_version": 1,
            **public_record(planned),
            "created_at": now(),
            "state": "submitting",
        }
        save(path, job, exclusive=True)
        phase = "request"
        try:
            status, body = client.request(
                CREATE[planned["kind"]], "POST", data, content_type, length
            )
            response = body.get("data")
            if (
                status == 200
                and str(body.get("code")) == "200"
                and isinstance(response, dict)
            ):
                phase = "task_id_validation"
                job["task_id"] = task_identifier(response.get("task_id"))
                # Persist the recovery handle before optional response processing.
                phase = "task_id_persistence"
                save(path, job)
                phase = "state_update"
                job.update(
                    state="queueing",
                    submitted_at=now(),
                )
            else:
                # Only explicit HTTP 4xx is treated as rejection; all other uncertainty stops resubmission.
                state = (
                    "submission_rejected"
                    if 400 <= status < 500
                    else "submission_uncertain"
                )
                job.update(state=state, error=response_error(status, body))
        except Exception as error:  # noqa: BLE001 - suppress response/transport details at the reporting boundary
            job.update(
                state="submission_uncertain",
                error={"type": type(error).__name__, "phase": phase},
            )
        job["updated_at"] = now()
        save(path, job)
    return {"reused": False, "job": job}


def query_job(client, path, timeout=90):
    job = load(path)
    task_id = task_identifier(job.get("task_id"))
    try:
        status, body = client.request(
            QUERY[job["kind"]] + "?" + urlencode({"task_id": task_id}), timeout=timeout
        )
        data = body.get("data")
        code = str(body.get("code"))
        if code in {"50010001", "5001001"}:
            job.update(state="failed", failure=response_error(status, body))
            job.pop("last_query_error", None)
        elif (
            status == 200
            and code == "200"
            and isinstance(data, dict)
            and data.get("state") in STATES
        ):
            job["state"] = data["state"]
            job.pop("last_query_error", None)
            if job["state"] in {"success", "failed"}:
                job.setdefault("first_observed_terminal_at", now())
        else:
            job["last_query_error"] = response_error(status, body)
        transient = data if isinstance(data, dict) else {}
    except Exception as error:  # noqa: BLE001 - suppress response/transport details at the reporting boundary
        job["last_query_error"] = {"type": type(error).__name__}
        transient = {}
    job["last_queried_at"] = now()
    save(path, job)
    return job, transient


def job_outcome(job):
    if job.get("last_query_error"):
        return "attention", 2
    state = job["state"]
    if state in {"failed", "submission_rejected"}:
        return "failed", 1
    if state in {"submitting", "submission_uncertain"}:
        return "attention", 2
    return ("success" if state == "success" else "pending"), 0


def wait_job(
    client, path, seconds=50, interval=20, clock=time.monotonic, sleep=time.sleep
):
    """Bound polling scheduling to 50 seconds; each HTTP request has its own timeout."""
    if not 0 <= seconds <= 50 or not 5 <= interval <= 50:
        raise ValueError("wait seconds must be 0..50; interval 5..50")
    deadline = clock() + seconds
    while True:
        job, _ = query_job(client, path, timeout=max(1, min(20, deadline - clock())))
        outcome, code = job_outcome(job)
        if outcome != "pending" or clock() >= deadline:
            return {"result": outcome, "job": job}, code
        sleep(min(interval, max(0, deadline - clock())))
