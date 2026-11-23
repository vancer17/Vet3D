"""Render a checked native animation without re-running expensive geometry checks."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import bpy, sys, argparse
from pathlib import Path
from render_scene import render_scene
from stage_cli import cli_arguments, StageFinished, _finish_stage

def build_parser():
    p = argparse.ArgumentParser()
    p.add_argument('--scene', type=Path, required=True)
    p.add_argument('--frames', type=Path, required=True)
    p.add_argument('--start', type=int, default=1)
    p.add_argument('--end', type=int, default=192)
    p.add_argument('--width', type=int, default=960)
    p.add_argument('--height', type=int, default=858)
    p.add_argument('--samples', type=int, default=12)
    return p

def execute(a):
    """Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate."""
    return render_scene(a.scene, a.frames, range(a.start, a.end+1), engine='CYCLES',
                        resolution=(a.width,a.height), fps=24, threads=2,
                        samples=a.samples, device='CPU', denoise=True,
                        prefix='frame-', animation=True)

def main(argv=None):
    try:
        return execute(build_parser().parse_args(cli_arguments(argv)))
    except StageFinished as done:
        return done
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
