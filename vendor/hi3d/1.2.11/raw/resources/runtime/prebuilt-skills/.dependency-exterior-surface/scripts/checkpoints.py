"""Local content verification only; never decides whether remote work can retry."""
from pathlib import Path
import hashlib


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def artifacts_match(artifacts, *, base=None, expected=(), allow_empty=False):
    """Check required names and every recorded file hash without changing state.

    Missing or changed files reject the cache; invalid artifact mappings reject it.
    A caller separately checks input/config fingerprint and record schema.
    """
    if not isinstance(artifacts, dict) or (not artifacts and not allow_empty):
        return False
    if not set(map(str, expected)).issubset(artifacts):
        return False
    for name, value in artifacts.items():
        if not isinstance(name, str) or not isinstance(value, str):
            return False
        path = Path(name) if base is None else Path(base) / name
        if not path.is_file() or digest(path) != value:
            return False
    return True
