"""Shared single-submit, silent wait and download workflow for 2D and 3D."""
from pathlib import Path

from hi3d_artifacts import download_job
from hi3d_jobs import submit_job, retry_job, wait_job, job_outcome
from hi3d_progress import job_summary, progress_snapshot
from hi3d_storage import load, workspace_path, exception_summary, IMAGE_FAILURE_ACTION
from hi3d_client import IMAGE_KINDS


def generate_task(client, planned, path, output, seconds=1800, interval=30,
                   waiter=wait_job, downloader=download_job, on_progress=None):
    """Reuse persistent intent; never retry a submission or hide incomplete generation."""
    if not 0 <= seconds <= 3600 or not 5 <= interval <= 300:
        raise ValueError("Invalid wait bounds")
    path = workspace_path(path)
    directory = workspace_path(output)
    output = str(directory)
    if directory.exists() and (not directory.is_dir() or
                               (not Path(path).exists() and any(directory.iterdir()))):
        raise ValueError("Use a new output directory")
    # Existing jobs authenticate inside query_job so failed checks are recorded
    # as query errors without replacing the last known task result.
    submitted = submit_job(client, path, planned, check_existing=False)
    job = submitted["job"]
    # An explicit resume may query again after a prior GET error; submission
    # uncertainty and terminal failure still stop without another POST.
    outcome, code = job_outcome({**job, "last_query_error": None})
    query_error = job.get("last_query_error") or {}
    resume_query = (job.get("state") == "failed" and bool(query_error)
                    and query_error.get("query_failed") is not True and bool(job.get("task_id")))
    if code and not resume_query:
        return {"result": outcome, "job": job_summary(job, path)}, code
    phase = "wait"
    try:
        progress_options = {"on_progress": on_progress} if on_progress is not None else {}
        waited, code = waiter(client, path, seconds, interval, **progress_options)
        if waited["result"] != "success":
            return {"result": waited["result"], "job": job_summary(waited["job"], path)}, code
        job = waited["job"]
        phase = "download"
        downloaded = downloader(client, path, output)
        return {"result": "success", "task_id": job["task_id"], "job_file": str(path),
                "files": [item["path"] for item in downloaded["artifact"]["files"]]}, 0
    except Exception as error:
        # Download refreshes the job before fetching URLs; include any persisted
        # query error, but keep the last known snapshot if reloading fails.
        try:
            latest_job = load(path)
            if isinstance(latest_job, dict):
                job = latest_job
        except (OSError, ValueError):
            pass
        if (job.get("last_query_error") or {}).get("query_failed"):
            return {"result": "failed", "phase": phase, "job": job_summary(job, path)}, 1
        return {"result": "attention", "phase": phase,
                "error_type": type(error).__name__, "error": exception_summary(error),
                **({"next_action": IMAGE_FAILURE_ACTION} if job.get("kind") in IMAGE_KINDS else {}),
                "job": job_summary(job, path)}, 2


def generate_retry_task(client, planned, path, output, seconds=1800, interval=30,
                        waiter=wait_job, downloader=download_job, on_progress=None):
    """Submit one free retry into a new job, then wait and download like generate_task."""
    if not 0 <= seconds <= 3600 or not 5 <= interval <= 300:
        raise ValueError("Invalid wait bounds")
    path = workspace_path(path)
    directory = workspace_path(output)
    output = str(directory)
    if directory.exists() and (not directory.is_dir() or
                               (not Path(path).exists() and any(directory.iterdir()))):
        raise ValueError("Use a new output directory")
    submitted = retry_job(client, path, planned, check_existing=False)
    job = submitted["job"]
    if on_progress is not None and not submitted["reused"] and job.get("task_id"):
        # emit_progress preserves the explicit submitted event and flushes stderr.
        on_progress({**progress_snapshot(job), "event": "submitted"})
    outcome, code = job_outcome({**job, "last_query_error": None})
    query_error = job.get("last_query_error") or {}
    resume_query = (job.get("state") == "failed" and bool(query_error)
                    and query_error.get("query_failed") is not True and bool(job.get("task_id")))
    if code and not resume_query:
        return {"result": outcome, "job": job_summary(job, path)}, code
    phase = "wait"
    try:
        progress_options = {"on_progress": on_progress} if on_progress is not None else {}
        waited, code = waiter(client, path, seconds, interval, **progress_options)
        if waited["result"] != "success":
            return {"result": waited["result"], "job": job_summary(waited["job"], path)}, code
        job = waited["job"]
        phase = "download"
        downloaded = downloader(client, path, output)
        return {"result": "success", "task_id": job["task_id"], "parent_task_id": job.get("parent_task_id"),
                "job_file": str(path),
                "files": [item["path"] for item in downloaded["artifact"]["files"]]}, 0
    except Exception as error:
        try:
            latest_job = load(path)
            if isinstance(latest_job, dict):
                job = latest_job
        except (OSError, ValueError):
            pass
        if (job.get("last_query_error") or {}).get("query_failed"):
            return {"result": "failed", "phase": phase, "job": job_summary(job, path)}, 1
        return {"result": "attention", "phase": phase,
                "error_type": type(error).__name__, "error": exception_summary(error),
                "job": job_summary(job, path)}, 2
