"""Explicit-input business stage and thin command-line adapter."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_engine import set_engine

import sys, argparse, json, math
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
from planar_core import MM
from planar_preview import camera, export_glb, save
from mathutils import Matrix
from types import SimpleNamespace
from functools import partial
from frame_runtime import cli_arguments, validate_paths
from planar_render import render as _render_base

from cli_schemas import animate_stage
from glb_clips import merge_file

def merge_scene_animation(path):
    """Merge this recipe's explicitly simultaneous channels; preserve its report keys."""
    report = merge_file(path, path, clips='all', name='Complete eclipse window assembly', in_place=True)
    return {'source_animation_count': report['before_clip_count'],
            'final_animation_count': report['after_clip_count'],
            'channels': report['channel_count'], 'distinct_node_properties': report['channel_count'],
            'merge_rule': 'Only disjoint node/property channels; shared data buffer unchanged'}

def animate(*, scene, output, render=False):
    """Run this named business stage. Inputs and all output paths are explicit.

    Mutates the active Blender scene when applicable; never runs on import.
    Files are generated only under the explicit destination. See code-contract.md.
    """
    a=SimpleNamespace(scene=scene, output=output, render=render)
    validate_paths(a)
    render=partial(_render_base, enabled=not getattr(a, "no_render", False))
    out = Path(a.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(Path(a.scene).resolve()))
    s = bpy.context.scene
    parts = list(bpy.data.collections['LUNAR FRAME ASSEMBLY — print parts and hardware'].objects)
    frame = next((o for o in parts if o.get('assembly_role') == 'frame'))
    basis = frame.matrix_world.copy()
    base = {o.name: o.matrix_world.copy() for o in parts}
    H = json.loads((Path(a.scene).parent / 'measurements.json').read_text())['aperture_mm'][1]
    cam = s.camera
    camera(cam, (0, 0, 80), (72, -370, 105), 212)
    render(out / 'hero.png', 1200, 1400, 32)
    camera(cam, (0, 24, 76), (170, 320, 150), 215)
    render(out / 'rear.png', 1100, 1200, 24)
    props = [o for o in bpy.data.objects if o.name in ['Closed notebook cover', 'Visible notebook pages', 'Top notebook cover', 'Graphite pencil', 'Hand thrown ceramic cup']]
    for o in props:
        o.hide_render = False
    camera(cam, (25, 30, 75), (180, -440, 190), 400)
    render(out / 'desk.png', 1500, 1200, 32)
    for o in props:
        o.hide_render = True
    s.render.fps = 12
    s.frame_start = 1
    s.frame_end = 120
    def move(o, frame, delta):
        o.matrix_world = basis @ Matrix.Translation(np.array(delta) * MM) @ basis.inverted() @ base[o.name]
        o.keyframe_insert(data_path='location', frame=frame)
        o.keyframe_insert(data_path='rotation_euler', frame=frame)
    for o in parts:
        role = o.get('assembly_role')
        if role == 'artwork':
            for f, d in [(1, (-90, 18, -40)), (5, (-90, 18, -40)), (16, (0, 0, -7)), (24, (0, 0, 0)), (120, (0, 0, 0))]:
                move(o, f, d)
        elif role == 'backboard':
            for f, d in [(1, (92, 18, -65)), (26, (92, 18, -65)), (35, (0, 0, -7)), (44, (0, 0, 0)), (120, (0, 0, 0))]:
                move(o, f, d)
        elif role == 'stand':
            for f, d in [(1, (-145, 25, -95)), (56, (-145, 25, -95)), (66, (0, 1.2, -8)), (74, (0, 0, 0)), (120, (0, 0, 0))]:
                move(o, f, d)
        elif role == 'easel_screw':
            for f, d in [(1, (-145, 25, -103)), (56, (-145, 25, -103)), (66, (0, 1.2, -16)), (74, (0, 0, -8)), (76, (0, 0, -8)), (84, (0, 0, 0)), (120, (0, 0, 0))]:
                move(o, f, d)
        elif role == 'keeper':
            v = Vector((*o['pivot_mm'], 0)) * MM
            o.rotation_mode = 'QUATERNION'
            for f in range(1, 121):
                angle = 180 if f <= 46 else 180 * (55 - f) / 9 if f < 55 else 0
                o.matrix_world = basis @ Matrix.Translation(v) @ Matrix.Rotation(math.radians(angle), 4, 'Z') @ Matrix.Translation(-v) @ basis.inverted() @ base[o.name]
                o.keyframe_insert(data_path='location', frame=f)
                o.keyframe_insert(data_path='rotation_quaternion', frame=f)
    cam.rotation_mode = 'QUATERNION'
    base_target = Vector((0, 0, 80)) * MM
    t0 = math.radians(25)
    cam.location = base_target + Vector((340 * math.sin(t0), 340 * math.cos(t0), 110)) * MM
    cam.rotation_quaternion = (base_target - cam.location).to_track_quat('-Z', 'Y')
    s.frame_set(1)
    bpy.context.view_layer.update()
    def projected_points():
        inv = cam.matrix_world.inverted()
        return np.array([inv @ (o.matrix_world @ Vector(c)) for o in parts for c in o.bound_box])
    q = projected_points()
    cx = (q[:, 0].max() + q[:, 0].min()) / 2
    cy = (q[:, 1].max() + q[:, 1].min()) / 2
    initial_target = base_target + cam.rotation_quaternion @ Vector((cx, cy, 0))
    initial_scale = max(np.ptp(q[:, 0]), np.ptp(q[:, 1]) * (4 / 3)) * 1.16
    framing = []
    for f in range(1, 121):
        s.frame_set(f)
        u = max(0, min(1, (f - 85) / 31))
        t = math.radians(25 + 143 * u)
        target = initial_target * (1 - u) + base_target * u
        cam.location = target + Vector((340 * math.sin(t), 340 * math.cos(t), 110)) * MM
        cam.rotation_quaternion = (target - cam.location).to_track_quat('-Z', 'Y')
        bpy.context.view_layer.update()
        q = projected_points()
        scale = max(initial_scale * (1 - u) + H * 1.6 * MM * u, 2 * np.abs(q[:, 1]).max() * (4 / 3) * 1.1, 2 * np.abs(q[:, 0]).max() * 1.1)
        cam.data.ortho_scale = scale
        cam.keyframe_insert(data_path='location', frame=f)
        cam.keyframe_insert(data_path='rotation_quaternion', frame=f)
        cam.data.keyframe_insert(data_path='ortho_scale', frame=f)
        framing.append({'frame': f, 'horizontal_fill_fraction': float(2 * np.abs(q[:, 0]).max() / scale), 'vertical_fill_fraction': float(2 * np.abs(q[:, 1]).max() / (scale / (4 / 3)))})
    (out / 'camera-framing-check.json').write_text(json.dumps({'method': 'Every frame projects all transformed assembly bounding-box corners; conservative check with at least10percent margin', 'frames': framing, 'maximum_frame_fill': max((max(q['horizontal_fill_fraction'], q['vertical_fill_fraction']) for q in framing))}, indent=2))
    for act in bpy.data.actions:
        for layer in act.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for fc in bag.fcurves:
                        for k in fc.keyframe_points:
                            k.interpolation = 'LINEAR'
    s.frame_set(1)
    export_glb(out / 'exploded.glb', parts)
    render(out / 'assembly.png', 1200, 900, 24)
    bpy.ops.object.select_all(action='DESELECT')
    for o in parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.export_scene.gltf(filepath=str(out / 'motion.glb'), export_format='GLB', use_selection=True, export_apply=True, export_animations=True, export_animation_mode='SCENE', export_frame_range=True, export_force_sampling=True, export_bake_animation=True, export_nla_strips=False)
    path = out / 'motion.glb'
    report = merge_scene_animation(path)
    (out / 'animation-export-check.json').write_text(json.dumps(report, indent=2))
    save(out / 'assembly.blend')
    manifest = {'fps': 12, 'first_frame': 1, 'last_frame': 120, 'duration_seconds': 10, 'sequence': [{'frames': [1, 24], 'action': 'Art card translates behind frame, aligns with rabbet, then seats'}, {'frames': [26, 44], 'action': 'Backboard aligns and enters rear rabbet'}, {'frames': [46, 55], 'action': 'Keepers rotate about actual M3 axes and retain board'}, {'frames': [56, 74], 'action': 'Detachable easel aligns with the two rear mounts and seats'}, {'frames': [76, 84], 'action': 'Two M3 screws enter the real through holes and nominal inserts'}, {'frames': [85, 120], 'action': 'Camera orbits to complete tabletop frame'}], 'video_render_engine': 'Blender EEVEE', 'stills_render_engine': 'Blender Cycles', 'not_simulated': ['hand forces', 'fastener torque', 'FDM shrinkage']}
    (out / 'video-manifest.json').write_text(json.dumps(manifest, indent=2))
    if a.render:
        set_engine(s)
        s.render.resolution_x = 960
        s.render.resolution_y = 720
        s.render.filepath = str(out / 'frames' / 'frame-')
        (out / 'frames').mkdir(exist_ok=True)
        s.render.image_settings.file_format = 'PNG'
        bpy.ops.render.render(animation=True)
    print('ANIMATION_COMPLETE', flush=True)

def main(argv=None):
    return animate_stage(animate, cli_arguments, argv)

if __name__ == "__main__":
    main()
