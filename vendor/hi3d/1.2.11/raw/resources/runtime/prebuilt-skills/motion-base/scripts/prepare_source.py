"""Source normalization CLI and optional inspection views."""
# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import os
import json
from source_normalize import normalize_source
from source_views import render_source_views
from stage_cli import cli_arguments, StageFinished, _finish_stage


def execute(arguments):
    source, out, height = arguments[:3]
    obj, report = normalize_source(source, out, float(height))
    print(json.dumps(report), flush=True)
    if os.environ.get('ASTRA_SKIP_SOURCE_VIEWS') == '1':
        _finish_stage(0)
    render_source_views(obj, out, float(height), extent_factor=1.65,
                        light_energy=15, light_size=0.2, light_distance=0.12,
                        camera_distance=0.5, world_name='Neutral inspection world')

def main(argv=None):
    try:
        return execute(cli_arguments(argv))
    except StageFinished as done:
        return done
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
