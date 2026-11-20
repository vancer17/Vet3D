"""CLI for recipe B-rep build: budget first, CadQuery kernel under run_budgeted."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from brep_spec import estimate_budget, load_spec, spec_digest, validate_spec
from process_run import BudgetTimeout, run_budgeted, utc_stamp, write_heartbeat

WAITING_SCHEMA = 'brep-build.waiting.v1'
CHOICES = [
    {'id': 'confirm_build', 'title': '按当前预算执行建模'},
    {'id': 'review_only', 'title': '已有 STEP/STL，只核对'},
    {'id': 'change_spec', 'title': '回退修改配方或细分'},
    {'id': 'back_build', 'title': '回退到建模检查点'},
]


def _dump(path, payload):
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def _waiting(output, reason, budget, elapsed_s=None):
    payload = {
        'schema': WAITING_SCHEMA,
        'reason': reason,
        'band': budget['band'],
        'budget_s': budget['max_wall_s'],
        'elapsed_s': elapsed_s,
        'extend_used': budget['extend_used'],
        'choices': CHOICES,
    }
    _dump(output / 'waiting.json', payload)
    return payload


def prepare_output(spec, output):
    output = Path(output)
    if output.exists():
        raise ValueError(f'output directory must not exist: {output}')
    output.mkdir(parents=True)
    budget = estimate_budget(spec)
    budget_doc = {
        'schema': 'run-tools.budget.v1',
        'status': 'ready',
        'phase': 'input',
        'entry': 'brep-build',
        'spec_sha256': spec_digest(spec),
        **budget,
    }
    _dump(output / 'budget.json', budget_doc)
    write_heartbeat(
        output / 'progress.json',
        status='running',
        phase='input',
        elapsed_s=0,
        budget_s=budget['max_wall_s'],
        heartbeat_s=budget['heartbeat_s'],
        last_heartbeat=utc_stamp(),
        entry='brep-build',
    )
    return budget


def run_kernel(spec_path, output, budget, *, python=sys.executable):
    kernel = Path(__file__).resolve().parent / 'brep_kernel.py'
    log = output / 'kernel.log'
    run_budgeted(
        [python, str(kernel), '--spec', str(spec_path), '--output', str(output)],
        log,
        max_wall_seconds=budget['max_wall_s'],
        heartbeat_path=output / 'progress.json',
        heartbeat_seconds=budget['heartbeat_s'],
        error_prefix='brep kernel exited',
    )


def build_output(spec_path, output, *, confirm_budget=False, check_only=False, python=sys.executable):
    spec_path = Path(spec_path)
    spec = load_spec(spec_path)
    budget = estimate_budget(spec)
    if check_only:
        return {'status': 'checked', 'budget': budget, 'spec_sha256': spec_digest(spec)}
    budget = prepare_output(spec, output)
    output = Path(output)
    if budget['needs_confirm'] and not confirm_budget:
        _waiting(output, 'budget_confirm', budget)
        return {'status': 'waiting_choice', 'reason': 'budget_confirm', 'budget': budget, 'output': str(output)}
    if budget['extend_used'] and not confirm_budget:
        raise ValueError('extend_used requires --confirm-budget')
    try:
        run_kernel(spec_path, output, budget, python=python)
    except BudgetTimeout as exc:
        _waiting(output, 'timeout', budget, elapsed_s=exc.elapsed_s)
        return {
            'status': 'waiting_choice',
            'reason': 'timeout',
            'budget': budget,
            'elapsed_s': exc.elapsed_s,
            'output': str(output),
        }
    manifest_path = output / 'manifest.json'
    if not manifest_path.is_file():
        raise ValueError('kernel finished without manifest.json')
    return {'status': 'completed', 'budget': budget, 'output': str(output), 'manifest': str(manifest_path)}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Build millimetre B-rep solids from a recipe JSON.')
    parser.add_argument('--spec', required=True)
    parser.add_argument('--output')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--confirm-budget', action='store_true')
    args = parser.parse_args(argv)
    if args.check:
        result = build_output(args.spec, args.output or Path('.'), check_only=True)
        json.dump(result, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write('\n')
        return 0
    if not args.output:
        raise ValueError('--output is required unless --check')
    result = build_output(args.spec, args.output, confirm_budget=args.confirm_budget)
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write('\n')
    if result['status'] == 'waiting_choice' and result['reason'] == 'budget_confirm':
        return 2
    if result['status'] == 'waiting_choice' and result['reason'] == 'timeout':
        return 3
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
        raise SystemExit(1)
