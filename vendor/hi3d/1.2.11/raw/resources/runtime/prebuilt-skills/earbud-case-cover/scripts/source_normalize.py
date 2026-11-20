"""Normalize one explicit source to millimetre geometry and traceable local files."""
import bpy
import bmesh
import numpy as np
import json
import hashlib
import math
from pathlib import Path
from scene_io import import_objects


def normalize_source(source, out, height_mm, *, yaw_deg=None, weld_tolerance_mm=0.0001):
    """Reset scene, join/normalize meshes, preserve corner UV/materials and write source files.

    Returns (Blender mesh object, inspection report). Height/weld are millimetres;
    Blender geometry remains metres. No rendering or command-line/environment reads.
    """
    source = Path(source).resolve()
    out = Path(out).resolve()
    height = float(height_mm)
    if not np.isfinite(height) or height <= 0:
        raise ValueError('height_mm must be finite and positive')
    if yaw_deg is not None and not np.isfinite(yaw_deg):
        raise ValueError('yaw_deg must be finite')
    if not np.isfinite(weld_tolerance_mm) or weld_tolerance_mm < 0:
        raise ValueError('weld_tolerance_mm must be finite and nonnegative')
    if not source.is_file():
        raise FileNotFoundError(source)
    out.mkdir(parents=True, exist_ok=True)
    objects = [o for o in import_objects(source, reset=True) if o.type == 'MESH']
    if not objects:
        raise ValueError('source must contain meshes')
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    if len(objects) > 1:
        bpy.ops.object.join()
    o = bpy.context.object
    mw = o.matrix_world.copy()
    o.parent = None
    o.matrix_world = mw
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if yaw_deg is not None:
        # glTF imports may use quaternion rotation; Euler edits then have no effect.
        o.rotation_mode = 'XYZ'
        o.rotation_euler.z = math.radians(yaw_deg)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    if o.dimensions.z <= 0:
        raise ValueError('source must have a positive Z extent')
    scale = height / 1000 / o.dimensions.z
    o.scale *= scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    co = np.empty(len(o.data.vertices) * 3, np.float32)
    o.data.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    shift = np.array([(co[:, 0].min() + co[:, 0].max()) / 2, (co[:, 1].min() + co[:, 1].max()) / 2, co[:, 2].min()])
    co -= shift
    o.data.vertices.foreach_set('co', co.ravel())
    bm = bmesh.new()
    bm.from_mesh(o.data)
    before = {'vertices': len(bm.verts), 'faces': len(bm.faces), 'nonmanifold_edges': sum((not e.is_manifold for e in bm.edges))}
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=weld_tolerance_mm / 1000)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    after = {'vertices': len(bm.verts), 'faces': len(bm.faces), 'nonmanifold_edges': sum((not e.is_manifold for e in bm.edges)), 'volume_mm3': bm.calc_volume() * 1000000000.0}
    bm.to_mesh(o.data)
    bm.free()
    o.name = 'Original textured Hi3D surface'
    o.data.calc_loop_triangles()
    v = np.empty(len(o.data.vertices) * 3, np.float32)
    o.data.vertices.foreach_get('co', v)
    f = np.empty(len(o.data.loop_triangles) * 3, np.int32)
    o.data.loop_triangles.foreach_get('vertices', f)
    loop = np.empty(len(o.data.loop_triangles) * 3, np.int32)
    o.data.loop_triangles.foreach_get('loops', loop)
    uv = np.zeros((len(o.data.loops), 2), np.float32)
    if o.data.uv_layers.active:
        o.data.uv_layers.active.data.foreach_get('uv', uv.ravel())
    mi = np.empty(len(o.data.loop_triangles), np.int32)
    o.data.loop_triangles.foreach_get('material_index', mi)
    np.savez(out / 'source.npz', vertices=v.reshape(-1, 3) * 1000, faces=f.reshape(-1, 3), uv=uv[loop.reshape(-1, 3)], material_index=mi)
    for im in bpy.data.images:
        if im.source == 'FILE' and (not im.packed_file):
            im.pack()
    bpy.ops.wm.save_as_mainfile(filepath=str(out / 'source.blend'))
    report = {'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'source_file': source.name, 'height_mm': height, 'seam_weld_tolerance_mm': weld_tolerance_mm, 'before': before, 'after': after, 'global_remesh': False, 'source_decimation': False, 'bounds_mm': [(v.reshape(-1, 3).min(0) * 1000).tolist(), (v.reshape(-1, 3).max(0) * 1000).tolist()]}
    if yaw_deg is not None:
        report['source_yaw_deg'] = yaw_deg
    (out / 'source-inspection.json').write_text(json.dumps(report, indent=2))
    return o, report
