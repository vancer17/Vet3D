import bpy, sys, numpy as np, math
from pathlib import Path
from web_derivative import export_derivative
from glb_clips import merge_file, read_glb
from mathutils import Vector
import os
from studio_core import apply, mat
from studio_preview import camera, export, stage
from render_engine import set_engine

def loadmesh(path, name, mat0=None, original=False, *, cream, original_materials):
    """Independently callable loadmesh operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    d = np.load(path)
    v = d['vertices']
    f = d['faces']
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(v))
    me.vertices.foreach_set('co', (v * 0.001).ravel())
    me.loops.add(f.size)
    me.loops.foreach_set('vertex_index', f.ravel())
    me.polygons.add(len(f))
    me.polygons.foreach_set('loop_start', np.arange(len(f), dtype=np.int32) * 3)
    me.polygons.foreach_set('loop_total', np.full(len(f), 3, np.int32))
    me.update()
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    o['asset'] = True
    o['art'] = original
    if original:
        for m in original_materials:
            me.materials.append(m)
        me.materials.append(cream)
        mi = d['material_index'].copy()
        mi[mi < 0] = len(original_materials)
        me.polygons.foreach_set('material_index', mi)
        uv = me.uv_layers.new(name='Source UV')
        uv.data.foreach_set('uv', d['uv'].ravel())
        me.polygons.foreach_set('use_smooth', d['material_index'] >= 0)
    else:
        me.materials.append(mat0)
        me.polygons.foreach_set('use_smooth', np.full(len(f), False))
    return o

def prep(*, srcdir):
    """Independently callable prep operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    bpy.ops.wm.open_mainfile(filepath=str(srcdir / 'source.blend'))
    original_materials = list(next((o for o in bpy.context.scene.objects if o.type == 'MESH')).data.materials)
    for o in list(bpy.context.scene.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    cream = mat('Warm unpainted interface resin', (0.72, 0.58, 0.39), 0, 0.52)
    metal = mat('Brushed metal axles', (0.38, 0.4, 0.39), 0.7, 0.35)
    white = mat('Nominal device ivory', (0.87, 0.88, 0.84), 0.05, 0.29)
    dark = mat('Cable graphite', (0.045, 0.042, 0.037), 0, 0.55)
    bpy.context.scene.unit_settings.system = 'METRIC'
    return (original_materials, cream, metal, white, dark)

def setup(direction=(1.25, -2, 0.9), extra=1.0):
    """Independently callable setup operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    target, extent = stage()
    bpy.context.scene.render.threads = 2
    bpy.context.scene.cycles.samples = 32
    floor = bpy.data.materials.get('Stage | midnight')
    floor.diffuse_color = (0.61, 0.67, 0.57, 1)
    floor.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.61, 0.67, 0.57, 1)
    bpy.context.scene.world.node_tree.nodes['Background'].inputs[0].default_value = (0.65, 0.67, 0.6, 1)
    bpy.context.scene.world.node_tree.nodes['Background'].inputs[1].default_value = 0.35
    camera(direction, target, extent * extra)
    return (target, extent)

def web_export(path, animated=False, *, _web_mesh_cache):
    """Independently callable web_export operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    originals = [o for o in bpy.context.scene.objects if o.get('art')]
    export_derivative(path, [o for o in bpy.context.scene.objects if o.get('asset') or o in originals],
                      derivatives=originals, collection=bpy.context.collection,
                      polygon_budget=300000, texture_limit=2048, mesh_cache=_web_mesh_cache,
                      export_animations=animated, export_current_frame=not animated,
                      export_animation_mode='ACTIONS', export_frame_range=True,
                      export_force_sampling=True, export_materials='EXPORT', export_yup=True)
    if animated and len(read_glb(Path(path).read_bytes())[0].get('animations', [])) > 1:
        merge_file(path, path, clips='all', name='Complete synchronized motion', in_place=True)

def frames(d, tag, limit, *, work):
    """Independently callable frames operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    if os.environ.get('ASTRA_SKIP_VIDEO', '1') != '0':
        return
    sc = bpy.context.scene
    set_engine(sc)
    sc.render.resolution_x = 864
    sc.render.resolution_y = 768
    sc.render.fps = 24
    sc.frame_end = limit
    p = work / d.name / (tag + '-frames')
    p.mkdir(parents=True, exist_ok=True)
    for f in range(1, limit + 1):
        sc.frame_set(f)
        sc.render.filepath = str(p / f'{f:04d}.png')
        bpy.ops.render.render(write_still=True)
