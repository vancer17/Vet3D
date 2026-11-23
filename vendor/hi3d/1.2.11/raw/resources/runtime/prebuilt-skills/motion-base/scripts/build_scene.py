"""Real product render, full native scene, lightweight web GLB and synchronized motions."""
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)
import bpy, sys, json, numpy as np, math, struct
from pathlib import Path
from mathutils import Vector
from studio_core import empty, mat, parent
from studio_preview import camera, render, save
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
        mint = mat('Warm honey birch library cart', (0.62, 0.39, 0.17), 0, 0.44)
        wheelmat = mat('Cream FDM wheels', (0.83, 0.77, 0.6), 0, 0.56)
        rootobj = empty('Complete cart and character')
        subject = loadmesh(d / 'parts/character.npz', 'Art character | high resolution foot sockets', original=True, cream=cream, original_materials=original_materials)
        parent(subject, rootobj)
        deck = loadmesh(d / 'parts/skateboard.npz', 'Continuous library cart with hidden foot keys', mint, cream=cream, original_materials=original_materials)
        parent(deck, rootobj)
        wheels = []
        for i, row in enumerate(info['board']['wheel_centers']):
            axis = empty('Wheel axis ' + str(i + 1), row['center_mm'])
            parent(axis, rootobj)
            o = loadmesh(d / 'parts' / f'wheel-{i + 1}.npz', 'Urethane wheel ' + str(i + 1), wheelmat, cream=cream, original_materials=original_materials)
            parent(o, axis)
            wheels.append(axis)
        for i in [1, 2]:
            o = loadmesh(d / 'parts' / f'axle-{i}.npz', 'M3 threaded rod envelope ' + str(i), metal, cream=cream, original_materials=original_materials)
            parent(o, rootobj)
        for path in sorted((d / 'parts').glob('hardware-*.npz')):
            o = loadmesh(path, path.stem, metal, cream=cream, original_materials=original_materials)
            parent(o, rootobj)
        target, extent = setup()
        render(d / 'hero.png', res=1050)
        camera((0, -1, 0.1), target, extent)
        render(d / 'front.png', res=760)
        camera((1, 1, 0.65), target, extent)
        render(d / 'rear.png', res=760)
        camera((1, -1, -0.9), target, extent)
        render(d / 'underside.png', res=700)
        camera((1.25, -2, 0.9), target, extent)
        save(d / 'scene.blend')
        web_export(d / 'model.glb', _web_mesh_cache=_web_mesh_cache)
        subject.location.z = 0.045
        camera((1.25, -2, 0.8), target + Vector((0, 0, 0.02)), extent * 1.25)
        render(d / 'exploded.png', res=900)
        web_export(d / 'exploded.glb', _web_mesh_cache=_web_mesh_cache)
        subject.location.z = 0
        camera((1.25, -2, 0.85), target, extent * 1.15)
        for f in range(1, 97):
            x = -22 + 44 * ease((f - 10) / 76)
            rootobj.location.x = x * 0.001
            rootobj.keyframe_insert('location', frame=f)
            for w in wheels:
                w.rotation_euler.y = x / info['board']['wheel_radius_mm']
                w.keyframe_insert('rotation_euler', frame=f)
        sc = bpy.context.scene
        sc.frame_end = 96
        sc.frame_set(1)
        save(d / 'motion.blend')
        web_export(d / 'motion.glb', True, _web_mesh_cache=_web_mesh_cache)
        frames(d, 'motion', 96, work=work)
        rootobj.animation_data_clear()
        rootobj.location.x = 0
        for w in wheels:
            w.animation_data_clear()
            w.rotation_euler.y = 0
        camera((1.25, -2, 0.7), target + Vector((0, 0, 0.02)), extent * 1.3)
        for f in range(1, 97):
            subject.location.z = 0.045 * (1 - ease((f - 8) / 28) + ease((f - 62) / 28))
            subject.keyframe_insert('location', frame=f)
        sc.frame_set(1)
        save(d / 'installation.blend')
        web_export(d / 'installation.glb', True, _web_mesh_cache=_web_mesh_cache)
        frames(d, 'installation', 96, work=work)
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
