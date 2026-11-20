"""Explicit-input business stage and thin command-line adapter."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import argparse, sys, os
from pathlib import Path
import bpy
import json
import numpy as np
from planar_core import height_mesh
from planar_preview import camera, save
from field_ops import warp_surface
from synchronize_morph_clips import synchronize
from types import SimpleNamespace
from functools import partial
from brush_runtime import cli_arguments, validate_paths
from brush_preview import render as _render_base

def animate(*, scene, heightfields, config, output, frames=None, no_render=False, render_animation=False):
    """Run this named business stage. Inputs and all output paths are explicit.

    Mutates the active Blender scene when applicable; never runs on import.
    Files are generated only under the explicit destination. See code-contract.md.
    """
    a=SimpleNamespace(scene=scene, heightfields=heightfields, config=config, output=output, frames=frames, no_render=no_render, render_animation=render_animation)
    validate_paths(a)
    if render_animation and no_render:
        raise ValueError("--render-animation and --no-render are mutually exclusive")
    if render_animation and frames is None:
        raise ValueError("Explicit --frames directory required for video rendering")
    if render_animation:
        a.frames = Path(a.frames).resolve()
        validate_paths(SimpleNamespace(output=a.frames))
    render=partial(_render_base, enabled=not getattr(a, "no_render", False))
    c = json.load(open(a.config))
    D = np.load(a.heightfields)
    out = a.output
    out.mkdir(parents=True, exist_ok=True)
    if render_animation:
        a.frames.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(a.scene))
    role = c['brush_roles']['main']
    selected = []
    for o in bpy.context.scene.objects:
        if o.type == 'MESH' and o.name != 'Studio floor':
            o.hide_render = True
    for kind in ['plane', 'cylinder', 'double-curvature']:
        o = bpy.data.objects[role + ' on ' + kind]
        o.hide_render = False
        w, h = c['coverage_mm']
        base = float(c['base_thickness_mm'])

        def warp(v):
            radius = float(c.get('cylinder_radius_mm',65) if kind=='cylinder' else c.get('sphere_radius_mm',80))
            return warp_surface(v,kind,radius)
        b = height_mesh('Temporary exact baseline', D[role], w, h, 0, base, None, nx=360, ny=144, warp=warp)
        assert len(o.data.vertices) == len(b.data.vertices)
        o.shape_key_add(name='Measured relief')
        smooth = o.shape_key_add(name='Smooth receiving surface')
        co = np.empty(len(b.data.vertices) * 3, np.float32)
        b.data.vertices.foreach_get('co', co)
        smooth.data.foreach_set('co', co)
        bpy.data.objects.remove(b, do_unlink=True)
        for frame, value in [(1, 1), (25, 1), (97, 0), (144, 0)]:
            smooth.value = value
            smooth.keyframe_insert('value', frame=frame)
        selected.append(o)
    s = bpy.context.scene
    s.frame_start = 1
    s.frame_end = 144
    s.render.fps = 24
    s.render.resolution_x = 1200
    s.render.resolution_y = 580
    s.cycles.samples = 24
    camera(s.camera, (0, -10, 0), (38, -140, 205), 300)
    s.frame_set(1)
    render(out / 'application-before.png', 1200, 580, 24)
    s.frame_set(144)
    render(out / 'application-after.png', 1200, 580, 24)
    bpy.ops.object.select_all(action='DESELECT')
    for o in selected:
        o.select_set(True)
    bpy.context.view_layer.objects.active = selected[0]
    bpy.ops.export_scene.gltf(filepath=str(out / 'application.glb'), export_format='GLB', use_selection=True, export_animations=True, export_morph=True, export_force_sampling=True)
    json.dump(synchronize(out / 'application.glb'), open(out / 'application-sync.json', 'w'), indent=2)
    s.frame_set(1)
    save(out / 'application.blend')
    if render_animation:
        s.render.resolution_x = 960
        s.render.resolution_y = 464
        s.cycles.samples = 10
        s.render.filepath = str(a.frames / 'frame-')
        bpy.ops.render.render(animation=True)
    json.dump({'frames': 144, 'fps': 24, 'video_rendered': render_animation, 'method': 'Exact receiving-surface vertices morph from smooth base to geometry-derived displacement. This is rendered application interpolation, not a recorded interactive sculpt stroke.', 'objects': [o.name for o in selected]}, open(out / 'application-metadata.json', 'w'), indent=2)

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--scene', type=Path, required=True)
    p.add_argument('--heightfields', type=Path, required=True)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--frames', type=Path)
    p.add_argument('--no-render', action='store_true', help='Skip still images')
    p.add_argument('--render-animation', action='store_true', help='Render video frames only when explicitly requested')
    options=p.parse_args(cli_arguments(argv))
    return animate(**vars(options))

if __name__ == "__main__":
    main()
