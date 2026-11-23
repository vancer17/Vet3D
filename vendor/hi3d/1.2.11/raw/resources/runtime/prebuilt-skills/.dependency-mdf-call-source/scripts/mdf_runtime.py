"""Load the installed MDF3 codec, or the bundled HTTP-only wire subset.

The subset is deliberately outside scripts/mdf3 so it cannot shadow an installed
full SDK. SDK mode never adds the fallback path or silently selects HTTP.
"""
from __future__ import annotations
import importlib
import importlib.util
from pathlib import Path
import sys
import threading

_codec_lock = threading.RLock()


def load_codec(*, transport="http"):
    if transport not in ("http", "sdk"):
        raise ValueError("transport must be http or sdk")
    with _codec_lock:
        spec = importlib.util.find_spec("mdf3")
        # An empty directory left by an upgrade is a namespace, not an SDK.
        missing = spec is None
        empty_namespace = (
            spec is not None and spec.origin is None
            and importlib.util.find_spec("mdf3.mdf_tool") is None
        )
        if transport == "http" and (missing or empty_namespace):
            if empty_namespace:
                sys.modules.pop("mdf3", None)
            sys.path.append(str(Path(__file__).resolve().parent / "_wire"))
            importlib.invalidate_caches()
        codec = importlib.import_module("mdf3.mdf_tool")
        if transport == "sdk":
            importlib.import_module("mdf3.service_invoke_tool")
        return codec
