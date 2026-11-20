"""Durable single-submit jobs; retain only sanitized business error summaries."""

import re
import json
from contextlib import contextmanager
import time
from pathlib import Path
from urllib.parse import urlencode

from hi3d_client import BACKEND, CREATE, QUERY, RETRY, IMAGE_KINDS
from hi3d_parameters import multipart
from hi3d_progress import progress_snapshot, progress_changed
from hi3d_storage import load, now, public_record, save, response_error, task_failure, exception_summary, QUERY_FAILURE_ACTION

THREE_D_KINDS = ("model", "relief", "split", "multicolor")


def task_identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,200}", value):
        raise ValueError(
            "Expected a task identifier containing letters, digits, dots, underscores or hyphens"
        )
    return value


def retry_root_id(job):
    """All locally-created retry jobs keep the original root, not the child task."""
    return task_identifier(job.get("parent_task_id") if job.get("retry") is True
                           else job.get("parentId") or job.get("task_id"))


def record_parent(job, data):
    """Keep a verified parent; a conflicting response cannot rebind an existing retry."""
    if job.get("kind") not in THREE_D_KINDS:
        return
    parent = data.get("parentId")
    if parent is None or parent == "":
        return
    parent = task_identifier(parent)
    expected = job.get("parent_task_id") if job.get("retry") is True else job.get("parentId")
    if expected is not None and parent != expected:
        raise ValueError("Task response conflicts with the original retry root")
    job["parentId"] = parent


def _nonneg_int(value):
    if type(value) is int and value >= 0:
        return value
    return None


def retry_quota_view(data):
    """Project remaining free retries; missing or invalid counts are not eligible."""
    payload = data if isinstance(data, dict) else {}
    remaining = None
    for key in ("retryCount", "remaining", "remainingCount", "remainRetryTimes", "retryRemainTimes", "freeRetryCount"):
        remaining = _nonneg_int(payload.get(key))
        if remaining is not None:
            break
    limit = _nonneg_int(payload.get("limit")) or _nonneg_int(payload.get("retryLimit"))
    eligible = payload.get("eligible")
    if eligible not in (True, False):
        eligible = remaining is not None and remaining > 0
    if remaining is None:
        remaining = 0
        eligible = False
    elif remaining == 0:
        eligible = False
    if payload.get("can_retry") is False:
        eligible = False
    view = {"eligible": bool(eligible), "remaining": remaining, "can_retry": bool(eligible) and remaining > 0}
    if limit is not None:
        view["limit"] = limit
    return view


def read_retry_quota(client, task_id):
    """GET remaining free retries for one 3D task; does not submit or mutate a job."""
    task_id = task_identifier(task_id)
    if client.context is None:
        client.auth()
    status, body = client.request(QUERY["model"] + "?" + urlencode({"jobId": task_id}))
    error = response_error(status, body)
    if status != 200 or str(body.get("code")) != "200":
        return {"task_id": task_id, "eligible": False, "remaining": 0, "can_retry": False,
                "error": error or {"reason": "The retry quota query failed."}}
    view = retry_quota_view(body.get("data"))
    view["task_id"] = task_id
    return view


def retry_parent(kind, task_id, parent_job=None):
    """Resolve the original 3D task for a free retry; identity/billing fields stay server-owned."""
    if kind not in THREE_D_KINDS:
        raise ValueError("Free retry is only available for 3D model, relief, split and multicolor tasks")
    parent_id = task_identifier(task_id)
    fingerprint = "retry:" + parent_id
    if parent_job is not None:
        if parent_job.get("backend") != BACKEND:
            raise ValueError("Legacy public-API job cannot be retried on the account runtime")
        if parent_job.get("kind") != kind:
            raise ValueError("Retry kind must match the original task")
        if retry_root_id(parent_job) != parent_id:
            raise ValueError("Retry parent task ID does not match the original job")
    return {"kind": kind, "parent_task_id": parent_id, "fingerprint": fingerprint}


def retry_job(client, path, planned, *, check_existing=True):
    """Submit one free retry of an existing 3D task into a new job; never rewrite the parent job."""
    kind = planned["kind"]
    parent_id = planned["parent_task_id"]
    fingerprint = planned["fingerprint"]
    if Path(path).exists():
        old = load(path)
        if old.get("backend") != BACKEND or old.get("fingerprint") != fingerprint:
            raise ValueError("Job belongs to a different plan; preserve it")
        if old.get("parent_task_id") != parent_id or old.get("kind") != kind:
            raise ValueError("Job belongs to a different plan; preserve it")
        if check_existing:
            client.check_job(old)
        return {"reused": True, "job": old}
    client.auth()
    job = {
        "schema_version": 2,
        "backend": BACKEND,
        "kind": kind,
        "fingerprint": fingerprint,
        "parent_task_id": parent_id,
        "retry": True,
        **client.context,
        "created_at": now(),
        "state": "submitting",
    }
    save(path, job, exclusive=True)
    phase = "request"
    try:
        payload = json.dumps({"parentGenerateId": parent_id}, ensure_ascii=False, allow_nan=False).encode()
        status, body = client.request(RETRY, "POST", payload, "application/json", len(payload))
        response = body.get("data")
        if status == 200 and str(body.get("code")) == "200" and isinstance(response, dict):
            phase = "task_id_validation"
            job["task_id"] = task_identifier(response.get("jobId"))
            if _nonneg_int(response.get("retryCount")) is not None:
                job["submitted_retry_quota"] = retry_quota_view(response)
            phase = "task_id_persistence"
            save(path, job)
            record_parent(job, response)
            phase = "state_update"
            job.update(state="queueing", submitted_at=now())
        else:
            rejected = (status == 200 and str(body.get("code")) == "1003"
                        and str(body.get("domainCode")) in {"10030104", "10030105", "10030106", "10030107"}
                        and body.get("error_source") != "desktop-proxy"
                        and not body.get("submission_has_task_id")
                        and not (isinstance(response, dict) and ("jobId" in response or "taskId" in response)))
            state = "submission_rejected" if 400 <= status < 500 or rejected else "submission_uncertain"
            job.update(state=state, error={**response_error(status, body), "phase": "request"})
    except Exception as error:  # noqa: BLE001 - suppress response/transport details at the reporting boundary
        job.update(state="submission_uncertain", error={**exception_summary(error), "phase": phase})
    job["updated_at"] = now()
    save(path, job)
    return {"reused": False, "job": job}


def adopt_job(client, kind, task_id, path):
    if kind not in QUERY:
        raise ValueError("Unsupported task kind")
    client.auth()
    job = {
        **client.context,
        "schema_version": 2,
        "backend": BACKEND,
        "kind": kind,
        "task_id": task_identifier(task_id),
        "state": "created",
        "adopted_at": now(),
    }
    save(path, job, exclusive=True)
    return job


@contextmanager
def request_body(planned):
    if planned["files"]:
        with multipart(planned["parameters"], planned["files"]) as assembled:
            yield assembled
    else:
        data = json.dumps(planned["parameters"]["request"], ensure_ascii=False, allow_nan=False).encode()
        yield data, "application/json", len(data)


def submit_job(client, path, planned, *, check_existing=True):
    if Path(path).exists():
        old = load(path)
        if old.get("backend") != BACKEND or old.get("fingerprint") != planned["fingerprint"]:
            raise ValueError("Job belongs to a different plan; preserve it")
        if check_existing:
            client.check_job(old)
        return {"reused": True, "job": old}
    # Verify bytes before authentication or creating intent. Keep this exact stream.
    with request_body(planned) as (
        data,
        content_type,
        length,
    ):
        client.auth()
        job = {
            "schema_version": 2,
            "backend": BACKEND,
            **public_record(planned),
            **client.context,
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
                job["task_id"] = task_identifier(response.get("taskId" if planned["kind"] in IMAGE_KINDS else "jobId"))
                # Persist the recovery handle before optional response processing.
                phase = "task_id_persistence"
                save(path, job)
                record_parent(job, response)
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
                job.update(state=state, error={**response_error(status, body), "phase": "request"})
        except Exception as error:  # noqa: BLE001 - suppress response/transport details at the reporting boundary
            job.update(
                state="submission_uncertain",
                error={**exception_summary(error), "phase": phase},
            )
        job["updated_at"] = now()
        save(path, job)
    return {"reused": False, "job": job}


def record_query_failure(job, error, *, business_failure=False):
    """Only a valid business rejection changes task state; unavailable status stays stale."""
    error = {**error,
             "next_action": " ".join(filter(None, (QUERY_FAILURE_ACTION, error.get("next_action"))))}
    error.setdefault("reason", error.get("message") or "The status query failed; the service returned no specific reason.")
    job["last_query_error"] = error
    if business_failure:
        error["query_failed"] = True
        job.update(state="failed", error={**error, "phase": "query"},
                   result={}, result_observed_at=now())
        job.setdefault("first_observed_terminal_at", now())


def query_job(client, path, timeout=90):
    job = load(path)
    if job.get("backend") != BACKEND:
        raise ValueError("Legacy public-API job must be queried with its original adapter; not sent to hi3d-codex")
    task_id = task_identifier(job.get("task_id"))
    try:
        client.check_job(job)
        status, body = client.request(
            QUERY[job["kind"]] + "?" + urlencode({"taskId" if job["kind"] in IMAGE_KINDS else "jobId": task_id}), timeout=timeout
        )
        data = body.get("data")
        code = str(body.get("code"))
        if (
            status == 200
            and code == "200"
            and isinstance(data, dict)
            and type(data.get("status")) is int
            and data.get("status") in ({0, 1, 2} if job["kind"] in IMAGE_KINDS else {0, 1})
        ):
            record_parent(job, data)
            if job.get("error", {}).get("phase") == "query":
                job.pop("first_observed_terminal_at", None)
            job["state"] = {0: "processing", 1: "success", 2: "failed"}[data["status"]]
            if job["state"] == "failed":
                job["error"] = task_failure(data)
                # Keep failure diagnostics, not arbitrary free text or asset URLs.
                job["result"] = {key: data[key] for key in
                                 ("status", "taskStatus", "percentage", "queuePosition")
                                 if type(data.get(key)) in (int, float)}
            else:
                job["result"] = public_record(data)
                if job.get("error", {}).get("phase") in {"generation", "query"}:
                    job.pop("error")
            job["result_observed_at"] = now()
            job.pop("last_query_error", None)
            if job["state"] in {"success", "failed"}:
                job.setdefault("first_observed_terminal_at", now())
        else:
            error = response_error(status, body)
            if status == 200 and code == "200":
                error["reason"] = "The query response does not contain a valid task status."
            record_query_failure(job, error, business_failure=(
                status == 200 and error.get("code") is not None and error["code"] != 200
                and error.get("error_source") != "desktop-proxy"))
        transient = data if isinstance(data, dict) else {}
    except Exception as error:  # noqa: BLE001 - suppress response/transport details at the reporting boundary
        record_query_failure(job, {**exception_summary(error), "phase": "query"})
        transient = {}
    job["last_queried_at"] = now()
    job["progress"] = progress_snapshot(job)
    save(path, job)
    return job, transient


def job_outcome(job):
    if job["state"] == "failed" and (job.get("last_query_error") or {}).get("query_failed") is True:
        return "failed", 1
    if job.get("last_query_error"):
        return "attention", 2
    state = job["state"]
    if state in {"failed", "submission_rejected"}:
        return "failed", 1
    if state in {"submitting", "submission_uncertain"}:
        return "attention", 2
    return ("success" if state == "success" else "pending"), 0


def wait_job(
    client, path, seconds=1800, interval=30, clock=time.monotonic, sleep=time.sleep,
    on_progress=None,
):
    """Poll inside one process, returning on terminal state, error or bounded deadline."""
    if not 0 <= seconds <= 3600 or not 5 <= interval <= 300:
        raise ValueError("wait seconds must be 0..3600; interval 5..300")
    deadline = clock() + seconds
    last_progress = None
    while True:
        job, _ = query_job(client, path, timeout=max(1, min(20, deadline - clock())))
        if on_progress is not None and progress_changed(last_progress, job["progress"]):
            on_progress(job["progress"])
            last_progress = dict(job["progress"])
        outcome, code = job_outcome(job)
        if outcome != "pending" or clock() >= deadline:
            return {"result": outcome, "job": job}, code
        sleep(min(interval, max(0, deadline - clock())))
        if clock() >= deadline:
            return {"result": outcome, "job": job}, code
