"""lifestyle local stage adapter."""
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)
import bpy, sys, math
from pathlib import Path
from mathutils import Vector
from studio_audit import bounds
from studio_core import cube, mat, tube
from studio_preview import camera, render
from stage_cli import cli_arguments, StageFinished, _finish_stage

def execute(arguments):
    """Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate."""
    A = arguments
    cid = A[0]
    d = Path(A[1])
    bpy.ops.wm.open_mainfile(filepath=str(d / 'scene.blend'))
    lo, hi = bounds()
    c = (lo + hi) / 2
    paper = mat('Warm book pages', (0.72, 0.68, 0.53), 0, 0.7)
    green = mat('Quiet sage cloth', (0.12, 0.24, 0.19), 0, 0.65)
    gold = mat('Ochre fabric', (0.46, 0.23, 0.055), 0, 0.65)
    blue = mat('Deep teal cloth', (0.055, 0.18, 0.2), 0, 0.6)
    cube('Linen desktop notebook', (80, 106, 9), (-68, 32, 4.5), green, r=5, printable=False)
    cube('Notebook page edge', (77, 102, 5), (-68, 32, 5.5), paper, r=3, printable=False)
    tube('Loose USB-C cable context', [(37, 16, 2), (62, 24, 2), (80, 14, 2), (77, -14, 2), (53, -31, 2)], 1.5, blue, False)
    target = Vector((-0.014, 0, 0.034))
    scale = 0.215
    for o in bpy.context.scene.objects:
        if o.name.startswith('Context') or o.name.startswith('Linen') or o.name.startswith('Notebook') or o.name.startswith('Loose'):
            o['asset'] = False
    camera((1.1, -2, 1.0), target, scale)
    render(d / 'lifestyle.png', res=1100)

def main(argv=None):
    try:
        return execute(cli_arguments(argv))
    except StageFinished as done:
        return done
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
