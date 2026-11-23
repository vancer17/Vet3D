"""Local file primitives and report sanitization; never inspect credential sources."""

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


IMAGE_FAILURE_ACTION = (
    "Stop the current image generation flow and report the failure. Preserve the task ID and job file; "
    "do not change parameters, model, paths or tools to resubmit. Resume only if the user explicitly asks."
)

QUERY_FAILURE_ACTION = (
    "Explain the specific error reason in the user's language without displaying numeric error codes unless requested, "
    "then end the current turn. Do not query, wait, download, retry or resubmit again until the user explicitly asks."
)

# API business meanings. These describe the failed request; only the query
# adapter may infer a task's terminal state from a task-specific rejection.
DOMAIN_ERRORS = {
    10030103: ("generation_failed", "Generation failed.",
               "Report the failure and preserve the task. The documented credit refund normally takes about 15 minutes; verify the balance rather than claiming a refund completed. Do not automatically resubmit."),
    10030104: ("retry_task_not_found", "The original task for retry was not found.",
               "Verify the original task ID and account/environment before retrying. Do not create a replacement automatically."),
    10030105: ("retry_limit_exceeded", "The allowed retry count was exceeded.",
               "Stop retrying this task and report the retry limit. A new generation requires a separate user decision."),
    10030106: ("concurrency_limit_exceeded", "The plan's concurrent task limit was exceeded.",
               "Report the concurrency limit and wait for existing tasks to finish before an explicitly requested retry. Do not resubmit automatically."),
    10030107: ("plan_quota_exhausted", "The current plan's feature quota is exhausted.",
               "Report the exhausted feature quota and ask the user to check their plan allowance. Do not repeatedly retry."),
    10000024: ("input_content_rejected", "The input image does not meet platform rules.",
               "Report the input rejection and stop this generation. A compliant replacement input requires the user's decision; do not automatically resubmit."),
    32001: ("model_content_rejected", "The generated model was rejected by platform content rules.",
            "Report the model rejection and stop delivery of this result. Do not download or automatically regenerate the rejected result."),
}


def business_error_details(code, domain_code):
    """Map documented code pairs to safe explanations/actions, without side effects."""
    if domain_code == 500:
        details = ("system_error", "The service is busy or encountered an unknown exception.",
                   "Preserve the task and report the service error. Recheck the existing task later; do not infer task failure or repeat submission.")
    elif code == 1003 and domain_code in DOMAIN_ERRORS:
        details = DOMAIN_ERRORS[domain_code]
    elif domain_code is None:
        details = {
            1003: ("invalid_request", "The request parameters are invalid.",
                   "Check the parameters against the endpoint contract and report the reason. Do not repeat the unchanged request or infer that an existing task failed."),
            30010000: ("insufficient_credits", "The credit balance is insufficient.",
                       "Report the insufficient balance and ask the user to check credits. Do not automatically purchase credits or resubmit."),
            30010001: ("credit_confirmation_required", "Confirmation of credit consumption is required.",
                       "Explain the required credit consumption and obtain the user's confirmation before a new submission. Do not confirm automatically."),
            409: ("data_version_conflict", "The data version is not current.",
                  "Refresh the latest data before continuing. Preserve the existing task and do not repeat a stale submission."),
        }.get(code)
    else:
        details = None
    if details is None:
        return {}
    return dict(zip(("category", "reason", "next_action"), details))


def safe_error_message(message):
    """Bound a single reason; never stringify structured response bodies."""
    if not isinstance(message, str) or not message.strip():
        return None
    if re.search(r"cookie|authorization|bearer|token|secret|password|credential|sessionid|mm_aigc|api[ _-]?key|access[ _-]?key|fe26\.", message, re.I):
        return "[redacted sensitive error details]"
    message = re.sub(r"https?://\S+", "[redacted URL]", message, flags=re.I)
    message = re.sub(r"[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}", "[redacted]", message)
    message = re.sub(r"[A-Za-z0-9_+/=-]{64,}", "[redacted]", message)
    return " ".join(re.sub(r"[\x00-\x1f\x7f]", " ", message).split())[:500]


def response_error(status, body):
    """Extract transport/business errors without retaining the response body."""
    code = str(body.get("code", ""))
    result = {"http_status": status,
              "code": int(code) if re.fullmatch(r"[0-9]{1,12}", code) else None}
    if body.get("submission_has_task_id") is True:
        result["submission_has_task_id"] = True
    domain_code = str(body.get("domainCode", ""))
    if re.fullmatch(r"[0-9]{1,12}", domain_code):
        result["domainCode"] = int(domain_code)
    trace_id = body.get("trace_id")
    if isinstance(trace_id, str) and re.fullmatch(r"[A-Za-z0-9_.-]{8,64}", trace_id):
        result["trace_id"] = trace_id
    if body.get("error_source") in ("upstream", "desktop-proxy"):
        result["error_source"] = body["error_source"]
    nested = body.get("error")
    candidates = [body.get("msg"), body.get("message"), nested.get("message") if isinstance(nested, dict) else None]
    message = next((safe_error_message(value) for value in candidates if isinstance(value, str) and value.strip()), None)
    if message:
        result["message"] = message
    if (status == 200 and result.get("error_source") != "desktop-proxy"
            and (body.get("domainCode") in (None, "") or "domainCode" in result)):
        result.update(business_error_details(result["code"], result.get("domainCode")))
    return result


def task_failure(result):
    """Project optional task-failure fields; a successful query is not task success."""
    nested = result.get("error")
    nested = nested if isinstance(nested, dict) else {}
    candidates = [result.get(key) for key in ("failReason", "failureReason", "errorMessage", "errorMsg", "message", "msg", "error")]
    candidates.append(nested.get("message"))
    message = next((value for value in candidates if isinstance(value, str) and value.strip()), None)
    error = response_error(200, {"code": result.get("errorCode", nested.get("code", result.get("code"))),
                                 "domainCode": result.get("domainCode", nested.get("domainCode")), "message": message})
    return {**error, "phase": "generation",
            "message": error.get("message") or "Image generation failed; the service returned no failure reason."}


def exception_summary(error):
    """Describe local failures without echoing arbitrary transport exceptions."""
    if isinstance(error, TimeoutError):
        message = "Operation timed out."
    elif isinstance(error, OSError):
        message = os.strerror(error.errno) if isinstance(error.errno, int) else "File or network operation failed."
    elif isinstance(error, (ValueError, TypeError)) or type(error).__name__ == "ApiError":
        message = safe_error_message(str(error)) or "Local validation failed."
    else:
        message = "Operation failed; preserve the job and inspect the failed stage."
    result = {"type": type(error).__name__, "message": message}
    code = getattr(error, "code", None)
    if type(code) is int:
        result["code"] = code
    return result


def now():
    return datetime.now(timezone.utc).isoformat()


def load(path):
    return json.loads(workspace_path(path, must_exist=True).read_text(encoding="utf-8"))


def workspace_path(value, must_exist=False):
    configured = os.environ.get("SPARC3D_TOOL_WORKSPACE")
    if not configured:
        raise ValueError("Runtime workspace is required")
    if os.name != "nt" and "\\" in str(value):
        raise ValueError("Local path must stay inside the current workspace")
    root = Path(configured).resolve(strict=True)
    candidate = Path(os.path.abspath(Path(value).expanduser()))
    try:
        parts = candidate.relative_to(root).parts
    except ValueError:
        raise ValueError("Local path must stay inside the current workspace") from None
    cursor = root
    for part in parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError("Workspace paths must not contain symbolic links")
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(root) or (must_exist and not resolved.exists()):
        raise ValueError("Invalid workspace path")
    return resolved


def digest(path):
    result = hashlib.sha256()
    with workspace_path(path, must_exist=True).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def save(path, value, exclusive=False):
    """Write JSON with mode 0600; reserve intent exclusively or replace atomically."""
    path = workspace_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode()
    if exclusive:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        return
    fd, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def public_record(value):
    """Hide URL queries/fragments and credential fields without reading their values."""
    if isinstance(value, dict):
        result = {}
        for key in value:
            normalized = str(key).upper().replace("-", "_")
            if any(
                word in normalized
                for word in (
                    "TOKEN",
                    "COOKIE",
                    "SECRET",
                    "PASSWORD",
                    "AUTHORIZATION",
                    "CREDENTIAL",
                )
            ) or normalized in {"AK", "SK", "HI3D_AK", "HI3D_SK", "ACCESS_KEY"}:
                result[key] = "[redacted]"
            else:
                result[key] = public_record(value[key])
        return result
    if isinstance(value, list):
        return [public_record(item) for item in value]
    if isinstance(value, str) and value.lstrip().startswith(("{", "[")):
        try:
            nested = json.loads(value)
        except ValueError:
            pass
        else:
            return json.dumps(public_record(nested), ensure_ascii=False)
    if isinstance(value, str) and value.startswith(("https://", "http://")):
        parsed = urlsplit(value)
        return urlunsplit(
            (
                parsed.scheme,
                parsed.hostname or "",
                parsed.path,
                "[redacted]" if parsed.query else "",
                "",
            )
        )
    return value


def private_result_path(job, context):
    """Resolve a host-owned cache outside the workspace; never an agent-supplied path."""
    configured = os.environ.get("SPARC3D_TOOL_STATE_DIR")
    if not configured:
        raise ValueError("Runtime private result cache is required")
    root = Path(os.path.abspath(configured))
    workspace = workspace_path(os.environ["SPARC3D_TOOL_WORKSPACE"], True)
    if root == workspace or root.is_relative_to(workspace):
        raise ValueError("Private result cache must be outside the workspace")
    if any(p.is_symlink() for p in [root, *root.parents]):
        raise ValueError("Private result cache cannot contain symbolic links")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    identity = json.dumps([str(workspace_path(job)), context], sort_keys=True).encode()
    return root / (hashlib.sha256(identity).hexdigest() + ".json")


def save_private_result(job, context, response):
    """Persist download credentials only in host state, never in the reviewable job."""
    path = private_result_path(job, context)
    fd, temporary = tempfile.mkstemp(prefix=".result-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(response, stream, ensure_ascii=False, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        if path.is_symlink():
            raise ValueError("Invalid private result file")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def load_private_result(job, context):
    path = private_result_path(job, context)
    if path.is_symlink():
        raise ValueError("Invalid private result file")
    return json.loads(path.read_text(encoding="utf-8"))
