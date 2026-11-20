"""Explicit-input business stage and thin command-line adapter."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sys, argparse, json, math
from pathlib import Path
import bpy
from glb_clips import merge_file
import numpy as np
from mathutils import Vector
from planar_audit import bounds
from planar_core import MM
from planar_preview import save
from types import SimpleNamespace
from functools import partial
from box_runtime import cli_arguments, validate_paths
from planar_render import render as _render_base

def merge_scene_animation(path):
    """Keep the travel recipe's motion name and report around the shared merger."""
    report = merge_file(path, path, clips='all', name='Complete unlocking access and relocking', in_place=True)
    return {'source_actions': report['before_clip_count'], 'final_actions': report['after_clip_count'],
            'channels': report['channel_count'], 'disjoint_node_properties': report['channel_count']}


def animate(*, scene, output):
    """Run this named business stage. Inputs and all output paths are explicit.

    Mutates the active Blender scene when applicable; never runs on import.
    Files are generated only under the explicit destination. See code-contract.md.
    """
    a=SimpleNamespace(scene=scene, output=output)
    validate_paths(a)
    render=partial(_render_base, enabled=not getattr(a, "no_render", False))
    out = Path(a.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(Path(a.scene).resolve()))
    s = bpy.context.scene
    parts = list(bpy.data.collections['CORAL TRAVEL ASSEMBLY'].objects)
    groups = {}
    for o in parts:
        groups.setdefault(o['assembly_role'], []).append(o)
    home = {o.name: Vector(o['home_location']) for o in parts}
    rot = {o.name: Vector(o['home_rotation']) for o in parts}
    lowest = bounds(groups['lid'])['min_mm'][2]
    lidrest = -lowest
    s.frame_start = 1
    s.frame_end = 160
    s.render.fps = 16
    def interp(f, keys):
        for i in range(len(keys) - 1):
            f0, v0 = keys[i]
            f1, v1 = keys[i + 1]
            if f <= f1:
                u = np.clip((f - f0) / (f1 - f0), 0, 1)
                u = u * u * (3 - 2 * u)
                return np.asarray(v0) * (1 - u) + np.asarray(v1) * u
        return np.asarray(keys[-1][1])
    lidkeys = [(1, [0, 0, 0]), (24, [0, 0, 0]), (40, [0, 0, 68]), (50, [0, 132, 68]), (60, [0, 132, lidrest]), (110, [0, 132, lidrest]), (120, [0, 132, 68]), (131, [0, 0, 68]), (142, [0, 0, 0]), (160, [0, 0, 0])]
    traykeys = [(1, 0), (61, 0), (75, 45), (98, 45), (110, 0), (160, 0)]
    insertkeys = [(1, [0, 0, 0]), (76, [0, 0, 0]), (82, [0, 0, 23]), (88, [0, 0, 23]), (97, [0, 0, 0]), (160, [0, 0, 0])]
    frames = []
    cam = s.camera
    cam.rotation_mode = 'QUATERNION'
    for f in range(1, 161):
        dz = float(interp(f, traykeys))
        ins = interp(f, insertkeys)
        for group, objs in groups.items():
            delta = interp(f, lidkeys) if group == 'lid' else np.array([0, 0, dz]) if group in ['tray', 'earcard', 'spool'] else np.zeros(3)
            if group in ['earcard', 'spool']:
                delta = delta + ins
            for o in objs:
                o.location = home[o.name] + Vector(delta * MM)
                o.rotation_euler = rot[o.name]
                if group.startswith('screw'):
                    side = -1 if group == 'screw0' else 1
                    park = np.array([side * 109, -65, 4.5])
                    home_mm = np.array(home[o.name]) / MM
                    pose = interp(f, [(1, home_mm), (14, home_mm + [0, 0, 15]), (24, park), (142, park), (150, home_mm + [0, 0, 15]), (160, home_mm)])
                    angle = float(interp(f, [(1, 0), (14, 4 * math.pi), (24, 0), (142, 0), (150, 4 * math.pi), (160, 0)]))
                    lay = float(interp(f, [(1, 0), (14, 0), (24, math.pi / 2), (142, math.pi / 2), (150, 0), (160, 0)]))
                    o.location = Vector(pose * MM)
                    o.rotation_euler = (0, lay, angle)
                o.keyframe_insert(data_path='location', frame=f)
                o.keyframe_insert(data_path='rotation_euler', frame=f)
        s.frame_set(f)
        bpy.context.view_layer.update()
        u = float(interp(f, [(1, 0), (24, 0.25), (50, 1), (120, 1), (150, 0), (160, 0)]))
        target = np.array([0, 57 * u, 22 + dz * 0.35]) * MM
        delta = np.array([160 - 60 * u, -235, 235 + 100 * u]) * MM
        cam.location = Vector(target + delta)
        cam.rotation_quaternion = (Vector(target) - cam.location).to_track_quat('-Z', 'Y')
        bpy.context.view_layer.update()
        inv = cam.matrix_world.inverted()
        vv = np.array([inv @ (o.matrix_world @ Vector(c)) for o in parts for c in o.bound_box])
        scale = max(0.24, 2 * abs(vv[:, 0]).max() * 1.12, 2 * abs(vv[:, 1]).max() * 4 / 3 * 1.12)
        cam.data.ortho_scale = scale
        cam.keyframe_insert(data_path='location', frame=f)
        cam.keyframe_insert(data_path='rotation_quaternion', frame=f)
        cam.data.keyframe_insert(data_path='ortho_scale', frame=f)
        frames.append({'frame': f, 'fill_x': float(2 * abs(vv[:, 0]).max() / scale), 'fill_y': float(2 * abs(vv[:, 1]).max() * 4 / 3 / scale)})
    for act in bpy.data.actions:
        for layer in act.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for fc in bag.fcurves:
                        for k in fc.keyframe_points:
                            k.interpolation = 'LINEAR'
    s.frame_set(1)
    bpy.ops.object.select_all(action='DESELECT')
    for o in parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    path = out / 'motion.glb'
    bpy.ops.export_scene.gltf(filepath=str(path), export_format='GLB', use_selection=True, export_apply=True, export_animations=True, export_animation_mode='SCENE', export_frame_range=True, export_force_sampling=True, export_bake_animation=True, export_nla_strips=False)
    report = merge_scene_animation(path)
    (out / 'animation-export-check.json').write_text(json.dumps(report, indent=2))
    (out / 'camera-framing-check.json').write_text(json.dumps(frames, indent=2))
    (out / 'video-manifest.json').write_text(json.dumps({'fps': 16, 'frames': 160, 'duration_seconds': 10, 'lid_rest_translation_z_mm': lidrest, 'phases': ['M3 thumb screws unscrew then rest on table', 'Lid lifts clear, translates back and rests on actual lowest foam surface', 'Tray lifts with supported jewelry', 'Earring card and necklace core lift for access', 'Inserts and tray return', 'Lid returns and screws tighten'], 'not_simulated': ['hands', 'thread friction and torque', 'foam compression', 'transport shock']}, indent=2))
    save(out / 'motion.blend')
    print('MOTION_COMPLETE', flush=True)

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--scene', required=True)
    p.add_argument('--output', required=True)
    options=p.parse_args(cli_arguments(argv))
    return animate(**vars(options))

if __name__ == "__main__":
    main()
