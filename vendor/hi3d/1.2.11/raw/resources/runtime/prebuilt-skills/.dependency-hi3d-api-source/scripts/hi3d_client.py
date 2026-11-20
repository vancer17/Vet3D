"""Fixed-origin Hi3D transport; credentials are consumed only during authentication."""

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation

from hi3d_storage import now

BASE = "https://api.hitem3d.ai"
CREATE = {
    "model": "/open-api/v1/submit-task",
    "relief": "/open-api/v1/depth/create-task",
    "split": "/open-api/v1/split/create-task",
    "multicolor": "/open-api/v1/muilticolor/create-task",
}
QUERY = {
    "model": "/open-api/v1/query-task",
    "relief": "/open-api/v1/depth/query-task",
    "split": "/open-api/v1/split/query-task",
    "multicolor": "/open-api/v1/multicolor/query-task",
}


def environment_credentials():
    """Authentication-process boundary. Never call this to inspect or display values."""
    access_key = os.environ.get("HI3D_AK")
    secret_key = os.environ.get("HI3D_SK")
    if not access_key or not secret_key:
        raise RuntimeError(
            "Authentication requires HI3D_AK and HI3D_SK in the process environment"
        )
    return access_key, secret_key


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Client:
    def __init__(self, opener=None):
        self.opener = opener or urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirect
        )
        self._token = None

    def _http(
        self, path, method, data, content_type, authorization, length=None, timeout=90
    ):
        if not path.startswith("/open-api/v1/") or urllib.parse.urlsplit(path).netloc:
            raise ValueError("Unsupported API route")
        headers = {
            "Authorization": authorization,
            "Content-Type": content_type,
            "User-Agent": "Hi3D-skill/1.0",
        }
        if length is not None:
            headers["Content-Length"] = str(length)
        if hasattr(data, "seek"):
            data.seek(0)
        request = urllib.request.Request(
            BASE + path, data=data, headers=headers, method=method
        )
        try:
            with self.opener.open(request, timeout=timeout) as response:
                body = json.load(response)
                status = response.status
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
        return status, body

    def auth(self):
        access_key, secret_key = environment_credentials()
        basic = base64.b64encode((access_key + ":" + secret_key).encode()).decode()
        status, body = self._http(
            "/open-api/v1/auth/token",
            "POST",
            b"{}",
            "application/json",
            "Basic " + basic,
        )
        data = body.get("data")
        if (
            status != 200
            or str(body.get("code")) != "200"
            or not isinstance(data, dict)
            or not isinstance(data.get("accessToken"), str)
            or not data["accessToken"]
        ):
            raise RuntimeError(
                "Hi3D authentication failed; response details suppressed"
            )
        self._token = data["accessToken"]

    def request(
        self,
        path,
        method="GET",
        data=None,
        content_type="application/json",
        length=None,
        timeout=90,
    ):
        if self._token is None:
            self.auth()
        status, body = self._http(
            path, method, data, content_type, "Bearer " + self._token, length, timeout
        )
        # A read may refresh expired authentication once. A task POST is never repeated.
        if method == "GET" and (status == 401 or str(body.get("code")) == "401"):
            self.auth()
            status, body = self._http(
                path,
                method,
                data,
                content_type,
                "Bearer " + self._token,
                length,
                timeout,
            )
        return status, body

    def balance(self):
        status, body = self.request("/open-api/v1/balance")
        data = body.get("data")
        if (
            status != 200
            or str(body.get("code")) != "200"
            or not isinstance(data, dict)
        ):
            raise RuntimeError("Balance query failed; response details suppressed")
        value = data.get("totalBalance")
        try:
            valid = not isinstance(value, bool) and Decimal(str(value)).is_finite()
        except InvalidOperation:
            valid = False
        if not valid:
            raise ValueError("Balance response lacks a finite numeric totalBalance")
        return {
            "checked_at": now(),
            "totalBalance": value,
            "unit": "Not established by this adapter",
        }
