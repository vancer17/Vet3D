"""Armor source adapter: explicit yaw, skip switch and original review lighting."""
# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import json
from source_normalize import normalize_source
from source_views import render_source_views
from stage_cli import cli_arguments, StageFinished, _finish_stage


def execute(arguments):
    source, out, height = arguments[:3]
    yaw = float(arguments[arguments.index('--yaw-deg') + 1]) if '--yaw-deg' in arguments else 0
    obj, report = normalize_source(source, out, float(height), yaw_deg=yaw)
    print(json.dumps(report), flush=True)
    if '--skip-render' in arguments:
        _finish_stage(0)
    render_source_views(obj, out, float(height), extent_factor=1.2,
                        light_energy=110, light_size=0.45, light_distance=0.45,
                        camera_distance=1.2, world_name='Neutral review world',
                        replace_world=True)

def main(argv=None):
    try:
        return execute(cli_arguments(argv))
    except StageFinished as done:
        return done
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
