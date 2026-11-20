"""Real product render, full native scene, lightweight web GLB and synchronized motions."""
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)
import bpy, sys, json, numpy as np, math, struct
from pathlib import Path
from mathutils import Vector
from studio_core import empty, parent
from studio_preview import camera, export, render, save
from stage_cli import cli_arguments, StageFinished, _finish_stage






from product_scene import frames, loadmesh, prep, setup, web_export

def ease(t):
    """Independently callable ease operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    t = max(0, min(1, t))
    return t * t * (3 - 2 * t)

def execute(arguments):
    """Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate."""
    A = arguments
    cid = A[0]
    srcdir = Path(A[1])
    root = Path(A[2])
    work = Path(A[3])
    work.mkdir(parents=True, exist_ok=True)
    _web_mesh_cache = {}
    for d in sorted(root.iterdir()):
        if not (d / 'construction.json').exists():
            continue
        original_materials, cream, metal, white, dark = prep(srcdir=srcdir)
        info = json.loads((d / 'construction.json').read_text())
        objects = {}
        lower = loadmesh(d / 'parts/cover-lower.npz', 'Art lower shell', original=True, cream=cream, original_materials=original_materials)
        lid = loadmesh(d / 'parts/cover-lid.npz', 'Art lid shell', original=True, cream=cream, original_materials=original_materials)
        fixture = loadmesh(d / 'parts/device-lower.npz', 'Nominal original lower device', white, cream=cream, original_materials=original_materials)
        ftop = loadmesh(d / 'parts/device-lid.npz', 'Nominal original device lid', white, cream=cream, original_materials=original_materials)
        hinge = empty('Nominal device hinge', info['hinge_axis_mm'])
        parent(lid, hinge)
        parent(ftop, hinge)
        plug = empty('Charging connector')
        ph = loadmesh(d / 'parts/plug-housing.npz', 'Connector housing', dark, cream=cream, original_materials=original_materials)
        pt = loadmesh(d / 'parts/plug-tip.npz', 'Connector tip', metal, cream=cream, original_materials=original_materials)
        parent(ph, plug)
        parent(pt, plug)
        plug.location.z = -0.025
        for o in [ph, pt]:
            o.hide_render = True
            o['asset'] = False
        target, extent = setup((1.1, -2, 0.8))
        render(d / 'hero.png', res=1050)
        web_export(d / 'model.glb', _web_mesh_cache=_web_mesh_cache)
        save(d / 'scene.blend')
        asset_states = [(o, o.get('asset'), o.hide_render) for o in bpy.context.scene.objects]
        for o in bpy.context.scene.objects:
            enabled = o in [fixture, ftop]
            o['asset'] = enabled
            if o.type == 'MESH' and o.name != 'Stage':
                o.hide_render = not enabled
        export(d / 'reference-fixture.glb')
        camera((1.1, -2, 1), Vector((0, 0, 0.0256)), 0.1)
        render(d / 'reference-fixture.png', res=760)
        for o, flag, hidden in asset_states:
            o['asset'] = flag
            o.hide_render = hidden
        hinge.rotation_euler.x = -math.radians(info['opening_degrees'])
        camera((1, -2, 1.2), target, extent * 1.1)
        render(d / 'open.png', res=900)
        camera((0, -1, 0.05), target, extent * 1.25)
        render(d / 'open-front.png', res=760)
        camera((1, 0, 0.05), target, extent * 1.25)
        render(d / 'open-side.png', res=760)
        camera((1, 1, 0.8), target, extent * 1.1)
        render(d / 'rear.png', res=760)
        hinge.rotation_euler.x = 0
        camera((1, -1, -1.2), target, extent)
        render(d / 'bottom.png', res=760)
        camera((1.1, -2, 1), target, extent * 1.6)
        bpy.data.objects['Stage'].hide_render = True
        for o in [ph, pt]:
            o.hide_render = False
            o['asset'] = True
        for f in range(1, 145):
            hinge.rotation_euler.x = -math.radians(info['opening_degrees']) * (ease((f - 6) / 25) - ease((f - 66) / 25))
            hinge.keyframe_insert('rotation_euler', frame=f)
            plug.location.z = -0.025 + 0.025 * (ease((f - 100) / 18) - ease((f - 128) / 16))
            plug.keyframe_insert('location', frame=f)
        bpy.context.scene.frame_end = 144
        bpy.context.scene.frame_set(1)
        save(d / 'motion.blend')
        web_export(d / 'motion.glb', True, _web_mesh_cache=_web_mesh_cache)
        frames(d, 'motion', 144, work=work)
        hinge.animation_data_clear()
        hinge.rotation_euler.x = 0
        plug.animation_data_clear()
        plug.location.z = -0.025
        for o in [ph, pt]:
            o.hide_render = True
            o['asset'] = False
        mw = lid.matrix_world.copy()
        lid.parent = None
        lid.matrix_world = mw
        device = empty('Complete nominal device')
        parent(fixture, device)
        parent(ftop, device)
        camera((1.1, -2, 0.8), Vector((0, 0, 0.075)), 0.22)
        for f in range(1, 121):
            lid.location.z = 0.07 * (ease((f - 6) / 26) - ease((f - 94) / 26))
            lid.keyframe_insert('location', frame=f)
            device.location.z = 0.05 * (ease((f - 32) / 25) - ease((f - 67) / 26))
            device.keyframe_insert('location', frame=f)
        bpy.context.scene.frame_end = 120
        bpy.context.scene.frame_set(60)
        render(d / 'exploded.png', frame=60, res=900)
        web_export(d / 'exploded.glb', _web_mesh_cache=_web_mesh_cache)
        bpy.context.scene.frame_set(1)
        save(d / 'installation.blend')
        web_export(d / 'installation.glb', True, _web_mesh_cache=_web_mesh_cache)
        frames(d, 'installation', 120, work=work)
        print('SCENE COMPLETE', d, flush=True)

def main(argv=None):
    try:
        return execute(cli_arguments(argv))
    except StageFinished as done:
        return done
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
