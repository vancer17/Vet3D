"""detail views local stage adapter."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import bpy, sys
from pathlib import Path
from mathutils import Vector
from studio_preview import camera, render
from stage_cli import cli_arguments, StageFinished, _finish_stage

def execute(arguments):
    """Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate."""
    A = arguments
    d = Path(A[0])
    bpy.ops.wm.open_mainfile(filepath=str(d / 'scene.blend'))
    for o in bpy.context.scene.objects:
        if o.type == 'MESH' and o.name != 'Stage':
            o.hide_render = o.name != 'Art character | high resolution foot sockets'
    camera((0, -0.35, -1), Vector((0, 0.002, 0.029)), 0.085)
    render(d / 'foot-sockets.png', res=900)
    for o in bpy.context.scene.objects:
        if o.type == 'MESH' and o.name != 'Stage':
            o.hide_render = o.name != 'Continuous library cart with hidden foot keys'
    camera((1, -1, 1.5), Vector((0, 0.002, 0.029)), 0.12)
    render(d / 'hidden-pegs.png', res=900)

def main(argv=None):
    try:
        return execute(cli_arguments(argv))
    except StageFinished as done:
        return done
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
