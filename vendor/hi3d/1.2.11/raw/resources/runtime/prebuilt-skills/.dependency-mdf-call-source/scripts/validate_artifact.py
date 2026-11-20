#!/usr/bin/env python3
"""Validate a local service artifact with protocol-independent checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from online_service_atoms import ArtifactValidationError, validate_file


def parse_json(path: Path):
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    return {"json_type": type(value).__name__}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--min-size", type=int, default=1)
    parser.add_argument("--expected-size", type=int)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--json", action="store_true", dest="parse_as_json")
    args = parser.parse_args(argv)
    try:
        report = validate_file(
            args.artifact,
            min_size=args.min_size,
            expected_size=args.expected_size,
            expected_sha256=args.expected_sha256,
            parser=parse_json if args.parse_as_json else None,
        )
    except (ArtifactValidationError, OSError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "status": "invalid",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
