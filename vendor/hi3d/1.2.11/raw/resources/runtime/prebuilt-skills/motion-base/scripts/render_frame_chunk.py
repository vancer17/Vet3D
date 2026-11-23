"""render frame chunk local stage adapter."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import bpy, sys
from pathlib import Path
from render_scene import render_scene
from stage_cli import cli_arguments, StageFinished, _finish_stage

def execute(arguments):
    """Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate."""
    source, out = map(Path, arguments[:2])
    start, end = map(int, arguments[2:4])
    return render_scene(source, out, range(start, end+1), engine='BLENDER_EEVEE',
                        resolution=(864,768), fps=24, threads=2)

def main(argv=None):
    try:
        return execute(cli_arguments(argv))
    except StageFinished as done:
        return done
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
