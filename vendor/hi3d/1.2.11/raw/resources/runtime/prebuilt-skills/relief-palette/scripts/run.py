"""Standalone CLI contract. --describe and check need Python 3.9+ only."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from spec import read_spec


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--describe', action='store_true')
    sub = parser.add_subparsers(dest='command')
    for mode in ('check', 'build'):
        p = sub.add_parser(mode)
        p.add_argument('--config', required=True)
        if mode == 'build':
            p.add_argument('--output', required=True)
            p.add_argument('--previous-attempt-id')
    p = sub.add_parser('validate')
    p.add_argument('--report', required=True)
    options = parser.parse_args(argv)
    if options.describe:
        result = {'skill': 'relief-palette', 'schema_version': 1, 'commands': ['check', 'build', 'validate'],
                  'builder_contract': 'build(ctx) -> stationary, moving, contents, studio, shots; optional mirror, contacts',
                  'geometry_runtime': 'Blender 5.x with NumPy, bmesh and mathutils',
                  'external_generation': 'Explicit independent image tool and hi3d-api; no service calls in this package'}
    elif options.command == 'check':
        config = read_spec(options.config)
        result = {'preflight': 'passed', 'pan_count': len(config['pans']), 'geometry_created': False}
    elif options.command == 'build':
        from pipeline import run
        result = run(options.config, options.output, options.previous_attempt_id)
    elif options.command == 'validate':
        import bpy
        from assembly import validate_scene
        path = Path(options.report).resolve()
        if path.exists():
            raise FileExistsError('Keep prior verification; use a new report path')
        result = validate_scene(bpy.context.scene)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    else:
        parser.error('Choose a command or --describe')
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if result.get('checks', result).get('passed', True) else 1


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    raise SystemExit(main(args))
