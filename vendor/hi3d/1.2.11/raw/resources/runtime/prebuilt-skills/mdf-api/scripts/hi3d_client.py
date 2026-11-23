"""Desktop-only transport. Account cookies never enter the Python process."""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

BACKEND = "hi3d-codex-v1"
IMAGE_KINDS = {"text-to-image", "image-edit"}
CREATE = {kind: "/model3d/submit" for kind in ("model", "relief", "split", "multicolor")}
CREATE.update({kind: "/image-task/img-edit" for kind in IMAGE_KINDS})
QUERY = {kind: "/model3d/result" for kind in CREATE}
QUERY.update({kind: "/image-task/image-edit/result" for kind in IMAGE_KINDS})
RETRY = "/model3d/retry"
ROUTES = frozenset(CREATE.values()) | frozenset(QUERY.values()) | {RETRY}


class ApiError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__({401: "Please sign in to Hi3D", 409: "Switch back to the task's environment and account"}.get(code, "Generation request failed"))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Client:
    def __init__(self, opener=None):
        self.opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect)
        self.base = os.environ.get("HI3D_API_BASE_URL", "").rstrip("/")
        url = urllib.parse.urlsplit(self.base)
        self.token = os.environ.get("HI3D_API_PROXY_TOKEN", "")
        if url.scheme != "http" or url.hostname != "127.0.0.1" or not url.port or url.path != "/v1" or url.username or url.password or url.query or url.fragment:
            raise ValueError("Desktop generation proxy is not configured")
        if not re.fullmatch(r"[A-Za-z0-9_-]{20,200}", self.token):
            raise ValueError("Desktop generation proxy credential is missing")
        self.request_headers = {}
        for header, variable in (("X-Session-Id", "SPARC3D_TOOL_SESSION_ID"),
                                 ("X-Turn-Id", "SPARC3D_TOOL_TURN_ID")):
            value = os.environ.get(variable, "")
            if value:
                if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value):
                    raise ValueError("Invalid request correlation ID")
                self.request_headers[header] = value
        self.context = None

    def auth(self):
        status, body = self._send("/session", timeout=20)
        if status != 200 or body.get("code") != 200:
            raise ApiError(status)
        context = body.get("data") or {}
        if context.get("environment") not in {"test", "pre", "prod"} or not isinstance(context.get("owner_id"), str) or not context["owner_id"]:
            raise ValueError("Invalid desktop session metadata")
        self.context = {"environment": context["environment"], "owner_id": context["owner_id"]}

    def check_job(self, job):
        if self.context is None:
            self.auth()
        if any(job.get(key) != value for key, value in self.context.items()):
            raise ApiError(409)

    def request(self, path, method="GET", data=None, content_type="application/json", length=None, timeout=120):
        parsed = urllib.parse.urlsplit(path)
        if parsed.scheme or parsed.netloc or parsed.fragment or parsed.path not in ROUTES:
            raise ValueError("Unsupported API route")
        if self.context is None:
            self.auth()
        return self._send(path, method, data, content_type, length, timeout)

    def send(self, path, method, body=None, content_type=None, length=None, timeout=180):
        """Host-authenticated transport for explicitly supported account tool routes."""
        if path != '/mesh/invoke' or method != 'POST':
            raise ValueError('Unsupported shared transport route')
        return self._send(path, method, body, content_type, length, timeout)

    def _send(self, path, method="GET", data=None, content_type="application/json", length=None, timeout=120):
        headers = {"Authorization": "Bearer " + self.token, "Content-Type": content_type, "User-Agent": "Hi3D-codex-skill/2.0"}
        headers.update(self.request_headers)
        if self.context:
            headers.update({"X-Hi3D-Environment": self.context["environment"], "X-Hi3D-Account": self.context["owner_id"]})
        if length is not None:
            headers["Content-Length"] = str(length)
        if hasattr(data, "seek"):
            data.seek(0)
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=timeout) as response:
                body, status = json.load(response), response.status
        except urllib.error.HTTPError as error:
            status = error.code
            try:
                body = json.loads(error.read())
            except (ValueError, UnicodeError):
                body = {}
            finally:
                error.close()
        if not isinstance(body, dict):
            raise TypeError("API response is not an object")
        # No automatic retry of submissions, even on authentication expiry.
        return status, body

    def balance(self):
        raise NotImplementedError("hi3d-codex has no balance endpoint; no request was sent")
