"""Local file primitives and report sanitization; never inspect credential sources."""

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


def now():
    return datetime.now(timezone.utc).isoformat()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def save(path, value, exclusive=False):
    """Write JSON with mode 0600; reserve intent exclusively or replace atomically."""
    path = Path(path)
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
