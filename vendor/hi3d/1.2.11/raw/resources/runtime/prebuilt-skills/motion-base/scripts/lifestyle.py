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
from studio_core import cube, mat
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
    for i, (size, loc, m) in enumerate([((85, 62, 10), (-92, 35, 6), green), ((78, 58, 9), (-90, 38, 17), gold), ((70, 54, 7), (-96, 36, 27), blue)]):
        x, y, z = size
        cx, cy, cz = loc
        cube('Context book pages ' + str(i), (x - 3, y - 2, z - 2), loc, paper, r=1, printable=False)
        for zz in [cz - z / 2, cz + z / 2]:
            cube('Context book cover ' + str(i), (x, y, 1.4), (cx, cy, zz), m, r=0.7, printable=False)
        cube('Context book spine ' + str(i), (2.5, y, z), (cx - x / 2 + 0.5, cy, cz), m, r=0.7, printable=False)
    target = Vector((-0.018, 0.005, 0.064))
    scale = 0.285
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
