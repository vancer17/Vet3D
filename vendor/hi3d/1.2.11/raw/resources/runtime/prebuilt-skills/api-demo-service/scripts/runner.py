"""Run the copied user algorithm with JSON on stdin. Argv is fixed; request fields are not interpolated."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def load_run(algorithm: Path, function: str):
    spec = importlib.util.spec_from_file_location('user_algorithm', algorithm)
    if spec is None or spec.loader is None:
        raise RuntimeError('cannot load algorithm module')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    func = getattr(module, function, None)
    if not callable(func):
        raise RuntimeError('algorithm is missing callable ' + function)
    return func


def main(argv=None):
    argv = list(argv or sys.argv[1:])
    if '--plan' not in argv:
        raise SystemExit('runner requires --plan')
    plan_path = Path(argv[argv.index('--plan') + 1])
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    payload = json.loads(sys.stdin.read())
    func = load_run(plan_path.parent / plan['entry'], plan['function'])
    result = func(payload)
    if not isinstance(result, dict):
        raise SystemExit('algorithm must return an object')
    json.dump(result, sys.stdout, ensure_ascii=False)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
