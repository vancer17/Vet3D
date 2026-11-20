#!/usr/bin/env python3
"""Verify JSONL online-call audit pairing and terminal outcomes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from online_service_atoms import load_jsonl, verify_audit_records


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("audit", type=Path)
    parser.add_argument("--trace-id", default=None)
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args(argv)

    report = verify_audit_records(
        load_jsonl(args.audit),
        trace_id=args.trace_id,
        allow_incomplete=args.allow_incomplete,
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
