"""Verify model versions with glb-clips.read_glb."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from glb_clips import read_glb


def inspect_models(plan, media_root: Path):
    reports = []
    for version in plan.get('versions') or []:
        if version.get('kind') != 'model':
            continue
        path = media_root / version['file']
        if not path.is_file():
            reports.append({'id': version['id'], 'ok': False, 'reason': 'missing model'})
            continue
        try:
            read_glb(path.read_bytes())
            reports.append({'id': version['id'], 'ok': True, 'file': version['file']})
        except ValueError as error:
            reports.append({'id': version['id'], 'ok': False, 'reason': str(error)})
    return reports


def main(argv=None):
    parser = argparse.ArgumentParser(description='Inspect review-board models')
    parser.add_argument('--plan', required=True)
    parser.add_argument('--media', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    out = Path(args.output)
    if out.exists():
        raise SystemExit('output must be a new file')
    plan = json.loads(Path(args.plan).read_text(encoding='utf-8'))
    reports = inspect_models(plan, Path(args.media))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'models': reports}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0 if all(item['ok'] for item in reports) else 1


if __name__ == '__main__':
    raise SystemExit(main())
