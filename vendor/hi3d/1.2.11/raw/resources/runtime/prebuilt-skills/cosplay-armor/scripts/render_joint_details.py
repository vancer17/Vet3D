"""Render actual keyed split solids in neutral material from both cap-facing sides."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import bpy, sys, argparse
from pathlib import Path
from mathutils import Vector
from stage_cli import cli_arguments, StageFinished, _finish_stage

def build_parser():
    p = argparse.ArgumentParser()
    p.add_argument('--scene', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--target-mm', nargs=3, type=float, required=True)
    return p

def execute(a):
    """Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate."""
    a.output.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(a.scene))
    s = bpy.context.scene
    parts = [next((o for o in s.objects if o.name.startswith(n) and 'web preview' not in o.name)) for n in ['Lower shin', 'Upper shin']]
    mat = bpy.data.materials.new('Neutral technical proof polymer')
    mat.use_nodes = True
    bs = mat.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (0.35, 0.47, 0.53, 1)
    bs.inputs['Roughness'].default_value = 0.57
    for o in parts:
        o.data.materials.clear()
        o.data.materials.append(mat)
    s.render.engine = 'CYCLES'
    s.cycles.device = 'CPU'
    s.cycles.samples = 24
    s.cycles.use_denoising = True
    s.render.resolution_x = 1100
    s.render.resolution_y = 800
    s.render.resolution_percentage = 100
    s.render.threads_mode = 'FIXED'
    s.render.threads = 2
    cam = s.camera
    target = Vector(a.target_mm) * 0.001
    cam.data.ortho_scale = 0.06
    for index, delta, name in [(0, (0.018, 0.11, 0.09), 'alignment-tongues.png'), (1, (0.018, 0.11, -0.09), 'blind-pockets.png')]:
        for o in s.objects:
            if o.type == 'MESH':
                o.hide_render = o != parts[index]
                o.hide_set(o != parts[index])
        cam.location = target + Vector(delta)
        cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
        s.render.filepath = str(a.output / name)
        bpy.ops.render.render(write_still=True)
    print('JOINT DETAILS COMPLETE')

def main(argv=None):
    try:
        return execute(build_parser().parse_args(cli_arguments(argv)))
    except StageFinished as done:
        return done
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
