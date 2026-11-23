#!/usr/bin/env python3
"""Check the selected MDF transport without network, credentials or submission."""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path
import sys
from online_service_atoms import atomic_write_json
from mdf_runtime import load_codec


def check_runtime(*, require_numpy=False, transport="http"):
    """Check only dependencies needed by the explicitly selected transport."""
    result = {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "business_execution": "not_run",
        "network_checked": False,
        "numpy_required": require_numpy,
        "ready": False,
        "transport": transport,
    }
    try:
        codec = load_codec(transport=transport)
        import mdf3
        BinaryFile, dumps, loads = codec.BinaryFile, codec.dumps, codec.loads

        sample = {
            "file": BinaryFile(field_name="probe", content=b"local-roundtrip"),
            "slots": [None, True, 1000000],
        }
        restored = loads(dumps(sample))
        if restored["file"].content != b"local-roundtrip" or restored["slots"] != sample["slots"]:
            raise ValueError("Local codec round trip failed")
        result["codec_module"] = str(Path(sys.modules[BinaryFile.__module__].__file__).resolve())
        result["codec_version"] = getattr(mdf3, "__version__", "unavailable")
        if transport == "sdk":
            from mdf3.service_invoke_tool import ServiceInvokeSession
            result["invoke_module"] = ServiceInvokeSession.__module__
            result["worker_callback_required"] = True
        else:
            from mdf_http import post_json
            result["http_transport"] = post_json.__module__
            result["worker_callback_required"] = False
        result["numpy_available"] = importlib.util.find_spec("numpy") is not None
        if require_numpy:
            import numpy as np

            array = np.arange(6, dtype=np.float32).reshape(2, 3)
            if not np.array_equal(loads(dumps(array)), array):
                raise ValueError("NumPy codec round trip failed")
            result["numpy_version"] = np.__version__
        result["ready"] = True
    except Exception as exc:
        result["error_type"] = type(exc).__name__
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transport", choices=("http", "sdk"), default="http")
    parser.add_argument(
        "--require-numpy",
        action="store_true",
        help="Require an importable NumPy runtime for array contracts",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = check_runtime(require_numpy=args.require_numpy, transport=args.transport)
    if args.output:
        atomic_write_json(args.output, result)
    print(json.dumps(result, indent=2))
    return 0 if result["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
