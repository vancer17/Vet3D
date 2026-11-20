"""Validate and animate front removal after webbing has already been removed.
No cloth unfastening or human comfort simulation is claimed."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import bpy, sys, json, math, argparse, numpy as np
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from stage_cli import cli_arguments, StageFinished, _finish_stage
from mesh_snapshot import mesh_snapshot
from surface_pairs import surface_tree, pair_counts

def tree(o, dy=0):
    data = mesh_snapshot(o, evaluated=False, space='world')
    offset = Vector((0,dy,0))
    points = [Vector(v)+offset for v in data['vertices']]
    return surface_tree(points, data['triangles'].tolist(), epsilon=1e-8)

def build_parser():
    p = argparse.ArgumentParser()
    p.add_argument('--scene', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--frames', type=Path, required=True)
    p.add_argument('--render', action='store_true')
    p.add_argument('--start-frame', type=int, default=1)
    return p

def execute(a):
    """Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate."""
    out = a.output
    out.mkdir(parents=True, exist_ok=True)
    a.frames.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(a.scene))
    s = bpy.context.scene
    body = next((o for o in s.objects if o.type == 'MESH' and o.name.startswith('Hi3D anatomical body')))
    shell = next((o for o in s.objects if o.type == 'MESH' and o.get('printable')))
    pads = [o for o in s.objects if o.type == 'MESH' and 'foam pad' in o.name.lower()]
    straps = [o for o in s.objects if o.type == 'MESH' and any((x in o.name.lower() for x in ['webbing', 'overlap']))]
    for o in [body, shell, *pads, *straps]:
        o.hide_render = False
        o.hide_set(False)
    bodytree = tree(body)
    checks = []
    for dy in np.linspace(0, -0.18, 16):
        rows = []
        for o in [shell, *pads]:
            rows.append({'part': o.name, 'surface_intersections': pair_counts({body.name:bodytree,o.name:tree(o,float(dy))},[(body.name,o.name)])[body.name+' / '+o.name]})
        checks.append({'front_translation_mm': round(float(dy) * 1000, 3), 'parts': rows})
        print('CHECK', round(dy * 1000, 1), [x['surface_intersections'] for x in rows], flush=True)
    report = {'scope': 'Actual full-resolution shell and foam translated forwards after webbing is removed. The animation does not simulate unthreading straps or bending a human joint.', 'poses': checks, 'all_clear': all((x['surface_intersections'] == 0 for q in checks for x in q['parts'])), 'distance_mm': 180, 'pressure_friction_comfort': 'not tested'}
    (out / 'donning-check.json').write_text(json.dumps(report, indent=2))
    assert report['all_clear'], 'Removal path intersects body'
    group = bpy.data.objects.new('Front removal with webbing removed', None)
    bpy.context.collection.objects.link(group)
    for o in [shell, *pads]:
        mw = o.matrix_world.copy()
        o.parent = group
        o.matrix_world = mw
    for frame, dy in [(1, 0), (60, 0), (132, -0.18), (156, -0.18), (192, 0)]:
        group.location.y = dy
        group.keyframe_insert('location', frame=frame)
    for o in straps:
        for frame, hidden in [(1, False), (48, False), (49, True), (191, True), (192, False)]:
            o.hide_render = hidden
            o.keyframe_insert('hide_render', frame=frame)
    cam = s.camera
    cam.data.type = 'ORTHO'
    target = Vector((0, -0.065, 0.31))
    cam.location = target + Vector((0.62, -1, -0.035))
    cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.ortho_scale = 0.86
    s.frame_start = 1
    s.frame_end = 192
    s.render.fps = 24
    s.render.resolution_x = 1120
    s.render.resolution_y = 1000
    s.render.resolution_percentage = 100
    s.cycles.samples = 20
    s.render.threads_mode = 'FIXED'
    s.render.threads = 2
    s.cycles.use_denoising = True
    s.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / 'donning.blend'))
    preview = []
    for src in [body, shell, *pads]:
        d = src.copy()
        d.data = src.data.copy()
        bpy.context.collection.objects.link(d)
        d.name = src.name + ' | motion web copy'
        bpy.context.view_layer.objects.active = d
        targetfaces = 160000 if src == body else 210000 if src == shell else None
        if targetfaces and len(d.data.polygons) > targetfaces:
            q = d.modifiers.new('Web only', 'DECIMATE')
            q.ratio = targetfaces / len(d.data.polygons)
            q.use_collapse_triangulate = True
            bpy.ops.object.modifier_apply(modifier=q.name)
        preview.append(d)
    bpy.ops.object.select_all(action='DESELECT')
    group.select_set(True)
    for o in preview:
        o.select_set(True)
    bpy.context.view_layer.objects.active = preview[0]
    bpy.ops.export_scene.gltf(filepath=str(out / 'donning.glb'), export_format='GLB', use_selection=True, export_animations=True, export_force_sampling=True)
    for o in preview:
        bpy.data.objects.remove(o, do_unlink=True)
    if a.render:
        s.render.resolution_x = 960
        s.render.resolution_y = 858
        s.cycles.samples = 10
        s.frame_start = a.start_frame
        s.render.filepath = str(a.frames / 'frame-')
        bpy.ops.render.render(animation=True)
    print('DONNING COMPLETE', flush=True)

def main(argv=None):
    try:
        return execute(build_parser().parse_args(cli_arguments(argv)))
    except StageFinished as done:
        return done
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
