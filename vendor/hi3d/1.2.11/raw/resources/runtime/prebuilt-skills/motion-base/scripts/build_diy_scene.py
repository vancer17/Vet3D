"""Present current DIY solids with the unchanged high-resolution source character."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import bpy, sys, argparse, json, math, hashlib
from pathlib import Path
import numpy as np
from web_derivative import export_derivative
from glb_clips import merge_file
from mathutils import Vector
from studio_core import apply, empty, mat, parent
from studio_preview import camera, export, render, save, stage
import bmesh
from bpy_extras.object_utils import world_to_camera_view
from stage_cli import cli_arguments, StageFinished, _finish_stage

from render_engine import set_engine

def web_export(path, animated=False, *, char, sc, web_mesh_cache):
    """Independently callable web_export operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    export_derivative(path, [o for o in bpy.context.scene.objects if o.get('asset') or o == char],
                      derivatives=[char], collection=sc.collection,
                      polygon_budget=300000, texture_limit=2048, mesh_cache=web_mesh_cache,
                      export_animations=animated, export_current_frame=not animated,
                      export_animation_mode='ACTIONS', export_frame_range=True,
                      export_force_sampling=True, export_materials='EXPORT', export_yup=True)
    if animated:
        merge_file(path, path, clips='all', name='Complete hand assembly and rolling', in_place=True)

def still(name, direction, target, scale, res=900, *, a, out):
    """Independently callable still operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    camera(direction, target, scale)
    if not a.skip_stills:
        render(out / name, res=res)

def ease(t):
    """Independently callable ease operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    t = max(0, min(1, t))
    return t * t * (3 - 2 * t)

def build_parser():
    p = argparse.ArgumentParser()
    p.add_argument('--source-scene', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--skip-stills', action='store_true')
    return p

def execute(a):
    """Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate."""
    out = a.output.resolve()
    a.work.mkdir(parents=True, exist_ok=True)
    info = json.loads((out / 'measurement.json').read_text())
    cfg = info['config']
    bpy.ops.wm.open_mainfile(filepath=str(a.source_scene.resolve()))
    sc = bpy.context.scene
    sc.frame_set(1)
    candidates = [o for o in sc.objects if o.type == 'MESH' and o.get('art')]
    if len(candidates) != 1:
        raise ValueError('Source scene must contain exactly one mesh tagged art=True; inspect and tag the intended character before using this adapter')
    char = candidates[0]
    bpy.context.view_layer.update()
    world = char.matrix_world.copy()
    char.parent = None
    char.matrix_world = world
    char.animation_data_clear()
    char.name = 'Art character | unchanged high-poly foot sockets'
    char['asset'] = True
    for o in list(sc.objects):
        if o != char:
            bpy.data.objects.remove(o, do_unlink=True)
    for im in bpy.data.images:
        if im.source == 'FILE' and (not im.packed_file):
            try:
                im.pack()
            except Exception:
                pass
    cream = mat('PLA | warm cream wheel', (0.82, 0.74, 0.55), 0, 0.59)
    honey = mat('PLA | honey book cart', (0.58, 0.34, 0.12), 0, 0.51)
    blue = mat('PLA | blue-gray printed spindles', (0.15, 0.28, 0.31), 0, 0.55)
    amber = mat('PLA | ochre rigid retaining keys', (0.83, 0.4, 0.075), 0, 0.55)
    root = empty('Complete printed-only library cart')
    parent(char, root)
    objects = {}
    wheels = []
    for row in info['parts']:
        d = np.load(out / row['assembly_npz'])
        v = d['vertices'] * 0.001
        f = d['faces']
        name = row['id']
        center = np.array(row['axis_center_mm'] or [0, 0, 0]) * 0.001 if name.startswith('wheel-') else np.zeros(3)
        me = bpy.data.meshes.new(name)
        me.from_pydata((v - center).tolist(), [], f.tolist())
        me.update()
        o = bpy.data.objects.new(name, me)
        sc.collection.objects.link(o)
        o.location = center
        o['asset'] = True
        o['diy_part'] = True
        o['print_id'] = name
        m = honey if name == 'chassis' else cream if name.startswith('wheel') else amber if 'key-' in name else honey
        me.materials.append(m)
        for face in me.polygons:
            face.use_smooth = name.startswith('wheel') and abs(face.normal.y) < 0.995
        parent(o, root)
        objects[name] = o
        if name.startswith('wheel'):
            wheels.append(o)
    target, extent = stage()
    set_engine(sc)
    sc.render.threads = 2
    sc.render.resolution_x = 1100
    sc.render.resolution_y = 1000
    sc.render.resolution_percentage = 100
    sc.world.node_tree.nodes['Background'].inputs[0].default_value = (0.65, 0.67, 0.6, 1)
    sc.world.node_tree.nodes['Background'].inputs[1].default_value = 0.35
    floor = bpy.data.materials.get('Stage | midnight')
    floor.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.61, 0.67, 0.57, 1)
    sc.render.fps = cfg['fps']
    sc.frame_start = 1
    sc.frame_end = cfg['video_frames']
    sc.render.image_settings.file_format = 'PNG'
    web_mesh_cache = {}
    still('hero.png', (1.25, -2, 0.9), target, extent, 1050, a=a, out=out)
    save(out / 'scene.blend')
    web_export(out / 'model.glb', char=char, sc=sc, web_mesh_cache=web_mesh_cache)
    still('underside.png', (1, -1, -0.8), Vector((0, 0, 0.024)), 0.15, 950, a=a, out=out)
    char.hide_render = True
    for name, o in objects.items():
        o.hide_render = name not in ['wheel-4', 'pin-4']
    basepos = {n: o.location.copy() for n, o in objects.items()}
    charbase = char.location.copy()
    objects['wheel-4'].location.y += 0.014
    objects['pin-4'].location.y += 0.032
    d = np.load(out / 'interface/seat.npz')
    me = bpy.data.meshes.new('section-seat')
    me.from_pydata((d['vertices'] * 0.001 + np.array([0.034, 0, 0])).tolist(), [], d['faces'].tolist())
    me.update()
    ss = bpy.data.objects.new('SECTION | fixed journal, X half removed', me)
    sc.collection.objects.link(ss)
    me.materials.append(honey)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.bisect_plane(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces), plane_co=(0.034, 0, 0), plane_no=(1, 0, 0), clear_outer=True, dist=1e-08)
    bm.to_mesh(me)
    bm.free()
    still('joint-exploded.png', (1.3, -0.55, 0.8), Vector((0.034, 0.04, 0.012)), 0.095, 1000, a=a, out=out)
    objects['pin-4'].location = basepos['pin-4']
    objects['wheel-4'].location = basepos['wheel-4'] + Vector((0, 0.013, 0))
    still('joint-section.png', (1.6, -0.25, 0.6), Vector((0.034, 0.029, 0.011)), 0.075, 1000, a=a, out=out)
    objects['wheel-4'].location = basepos['wheel-4']
    original_mesh = objects['wheel-4'].data
    cutmesh = original_mesh.copy()
    objects['wheel-4'].data = cutmesh
    bm = bmesh.new()
    bm.from_mesh(cutmesh)
    bmesh.ops.bisect_plane(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces), plane_co=(0, 0, 0), plane_no=(1, 0, 0), clear_outer=True, dist=1e-08)
    bm.to_mesh(cutmesh)
    bm.free()
    still('assembled-section.png', (1.6, -0.25, 0.65), Vector((0.034, 0.028, 0.011)), 0.054, 1000, a=a, out=out)
    if not a.skip_stills:
        import base64
        specs = [('1', (0.034, 0.0292, 0.011), '完整肩段承重', 100, 110), ('2', (0.0374, 0.0151, 0.011), '双叉卡齿只负责防脱', 100, 220), ('3', (0.0385, 0.03825, 0.011), '轮毂与低头保留游隙', 810, 120)]
        lines = []
        for num, pos, label, tx, ty in specs:
            v = world_to_camera_view(sc, sc.camera, Vector(pos))
            px = v.x * 1150
            py = (1 - v.y) * 1000
            lines.append(f'<path d="M {tx + 15} {ty + 10} L {px:.1f} {py:.1f}" stroke="#6ce0e3" stroke-width="2"/><circle cx="{px:.1f}" cy="{py:.1f}" r="15" fill="#073f49" stroke="#c9ffff"/><text x="{px:.1f}" y="{py + 6:.1f}" text-anchor="middle" fill="white" font-size="18">{num}</text><text x="{tx}" y="{ty}" fill="white" font-size="24">{num} {label}</text>')
        raw = base64.b64encode((out / 'assembled-section.png').read_bytes()).decode()
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="1150" height="1120" viewBox="0 0 1150 1120"><rect width="1150" height="1120" fill="#1c3038"/><image width="1150" height="1000" href="data:image/png;base64,{raw}"/>' + ''.join(lines) + '<text x="50" y="1040" fill="white" font-size="27">真实装配位置 · 几何剖视（非受力仿真）</text><text x="50" y="1085" fill="#c6d8dc" font-size="23">肩座承载长 4.4 mm｜销窜动 0–0.30 mm｜轮总轴向游隙 1.10–1.40 mm</text></svg>'
        (out / 'assembled-section-annotated.svg').write_text(svg)
    objects['wheel-4'].data = original_mesh
    bpy.data.meshes.remove(cutmesh)
    objects['wheel-4'].location = basepos['wheel-4'] + Vector((0, 0.013, 0))
    for ob in [char, *objects.values()]:
        ob['asset'] = ob in [objects['pin-4'], objects['wheel-4']]
    ss['asset'] = True
    export(out / 'mechanism.glb')
    ss['asset'] = False
    bpy.data.objects.remove(ss, do_unlink=True)
    for name, o in objects.items():
        o.hide_render = False
        o['asset'] = True
        o.location = basepos[name]
    char.hide_render = False
    char['asset'] = True
    for i, center in enumerate(info['wheel_centers_mm'], 1):
        ob = objects[f'pin-{i}']
        ob.shape_key_add(name='Unloaded')
        key = ob.shape_key_add(name='Illustrated hand compression - not stress simulation')
        x0 = center[0] * 0.001
        side = 1 if center[1] > 0 else -1
        root_y = cfg['beam_root_y_mm']
        L = root_y - cfg['barb_back_y_mm']
        delta = info['snap']['illustrated_deflection_per_arm_mm'] * 0.001
        for v in key.data:
            u = max(0, min(1, (root_y - side * v.co.y * 1000) / L))
            f = u * u * (3 - u) / 2
            v.co.x -= (1 if v.co.x > x0 else -1) * delta * f
    phases = {'1-24': 'Hold wheels at their installation positions', '25-36': 'Illustrated hand precompression of exposed flexible tails', '37-78': 'Insert headed shoulder pins through wheels and fixed sockets', '79-90': 'Release tails after hard shoulders reach their stops', '91-112': 'Lower original character onto unchanged keyed foot sockets', '113-144': 'Hand-push rolling; angle = distance/radius'}
    for frame in range(1, cfg['video_frames'] + 1):
        travel = cfg['travel_mm'] * ease((frame - 113) / 31)
        root.location.x = (travel - cfg['travel_mm'] / 2) * 0.001
        root.keyframe_insert('location', frame=frame)
        for i, center in enumerate(info['wheel_centers_mm'], 1):
            side = 1 if center[1] > 0 else -1
            wh = objects[f'wheel-{i}']
            pp = objects[f'pin-{i}']
            wh.location = basepos[f'wheel-{i}'] + Vector((0, side * 14 * (1 - ease((frame - 1) / 23)) * 0.001, 0))
            wh.rotation_euler.y = travel / cfg['wheel_radius_mm']
            wh.keyframe_insert('location', frame=frame)
            wh.keyframe_insert('rotation_euler', frame=frame)
            pp.location = basepos[f'pin-{i}'] + Vector((0, side * 48 * (1 - ease((frame - 37) / 41)) * 0.001, 0))
            pp.keyframe_insert('location', frame=frame)
            key = pp.data.shape_keys.key_blocks[1]
            key.value = ease((frame - 25) / 11) * (1 - ease((frame - 79) / 11))
            key.keyframe_insert('value', frame=frame)
        char.location = charbase + Vector((0, 0, 50 * (1 - ease((frame - 91) / 21)) * 0.001))
        char.keyframe_insert('location', frame=frame)
    for action in bpy.data.actions:
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for fcurve in bag.fcurves:
                        for key in fcurve.keyframe_points:
                            key.interpolation = 'LINEAR'
    camera((1.1, -1.7, 0.8), Vector((-0.012, 0, 0.102)), 0.345)
    sc.frame_set(1)
    save(out / 'assembly.blend')
    web_export(out / 'assembly.glb', True, char=char, sc=sc, web_mesh_cache=web_mesh_cache)
    sc.frame_set(12)
    web_export(out / 'exploded.glb', char=char, sc=sc, web_mesh_cache=web_mesh_cache)
    if not a.skip_stills:
        render(out / 'exploded.png', frame=12, res=1000)
    char.hide_render = True
    for name, ob in objects.items():
        ob.hide_render = name not in ['wheel-4', 'pin-4', 'chassis']
    camera((1, -0.4, 0.8), Vector((0.034, 0.04, 0.014)), 0.115)
    sc.frame_set(60)
    if not a.skip_stills:
        render(out / 'snap-compression.png', frame=60, res=1000)
    for ob in objects.values():
        ob.hide_render = False
    char.hide_render = False
    camera((1.1, -1.7, 0.8), Vector((-0.012, 0, 0.102)), 0.345)
    sc.frame_set(1)
    frames = []
    for f in range(1, cfg['video_frames'] + 1):
        sc.frame_set(f)
        vals = [world_to_camera_view(sc, sc.camera, o.matrix_world @ Vector(v)) for o in [char, *objects.values()] for v in o.bound_box]
        lo = [min((x[j] for x in vals)) for j in [0, 1]]
        hi = [max((x[j] for x in vals)) for j in [0, 1]]
        frames.append({'frame': f, 'min_uv': lo, 'max_uv': hi})
        assert min(lo) > 0 and max(hi) < 1, (f, lo, hi)
    sc.frame_set(1)
    (out / 'animation-plan.json').write_text(json.dumps({'phases': phases, 'frames': cfg['video_frames'], 'fps': cfg['fps'], 'travel_mm': cfg['travel_mm'], 'wheel_radius_mm': cfg['wheel_radius_mm'], 'rolling_model': 'kinematic pure rolling, not measured traction', 'elastic_model': info['snap'], 'framing': frames, 'all_frames_inside_camera': True, 'stage': 'Assembly is digitally hand-held. Precompression is a small-deflection illustration, not strength, force, fatigue, or gravity simulation.'}, indent=2))
    print('DIY SCENE READY', out, flush=True)

def main(argv=None):
    try:
        return execute(build_parser().parse_args(cli_arguments(argv)))
    except StageFinished as done:
        return done
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
