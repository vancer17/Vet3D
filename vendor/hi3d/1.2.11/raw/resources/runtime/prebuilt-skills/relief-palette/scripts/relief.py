"""Explicit local-STL adaptation; source files are never edited."""
import bpy
import bmesh
import numpy as np
from geometry import MM


def fit_vertices(vertices, size_mm, center_mm, height_mm, axes, depth_sign):
    """Uniform XY fit, independent relief height, baseline at center_mm[2]."""
    source = np.asarray(vertices, dtype=float)
    target = np.asarray([*size_mm, *center_mm, height_mm], dtype=float)
    if (source.ndim != 2 or source.shape[1] != 3 or len(source) < 3
            or len(size_mm) != 2 or len(center_mm) != 3 or not np.isfinite(target).all()
            or not all(type(a) is int for a in axes) or sorted(axes) != [0, 1, 2]
            or type(depth_sign) is not int or depth_sign not in (-1, 1)):
        raise ValueError('Invalid relief source axes, shape or target dimensions')
    values = source[:, axes].copy()
    values[:, 2] *= depth_sign
    if len(values) < 3 or not np.isfinite(values).all():
        raise ValueError('Relief coordinates must be finite')
    lo, hi = values.min(0), values.max(0)
    span = hi-lo
    if min(span) <= 1e-10 or min(size_mm) <= 0 or height_mm <= 0:
        raise ValueError('Nondegenerate source and positive target dimensions required')
    scale = min(size_mm[0]/span[0], size_mm[1]/span[1])
    values[:, :2] = (values[:, :2]-(lo[:2]+hi[:2])/2)*scale
    values[:, 2] = (values[:, 2]-lo[2])/span[2]*height_mm
    values += np.asarray(center_mm)
    return values*MM, {'source_bounds': [lo.tolist(), hi.tolist()], 'xy_scale': float(scale),
                       'target_height_mm': height_mm, 'target_extent_mm': (np.ptp(values, axis=0)).tolist()}


def import_relief(collection, pan, mat):
    before = set(bpy.data.objects)
    selection = list(bpy.context.selected_objects)
    active = bpy.context.view_layer.objects.active
    try:
        bpy.ops.wm.stl_import(filepath=pan['relief'])
        imported = list(set(bpy.data.objects)-before)
        if len(imported) != 1 or imported[0].type != 'MESH':
            raise ValueError('Expected one STL mesh')
        obj = imported[0]
        source = np.empty(len(obj.data.vertices)*3, dtype=np.float64)
        obj.data.vertices.foreach_get('co', source)
        w, d, thickness = pan['size_mm']
        center = list(pan['center_mm'])
        center[2] += thickness/2-pan['embed_mm']
        vertices, report = fit_vertices(source.reshape(-1,3), [w-2*pan['margin_mm'], d-2*pan['margin_mm']],
                                        center, pan['relief_height_mm'], pan['axes'], pan['depth_sign'])
        obj.data.vertices.foreach_set('co', vertices.ravel())
        obj.data.update()
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
            bm.to_mesh(obj.data)
        finally:
            bm.free()
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        collection.objects.link(obj)
        obj.name = 'Relief '+pan['id']
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        for p in obj.data.polygons:
            p.use_smooth = True
        return obj, report
    except BaseException:
        for obj in set(bpy.data.objects)-before:
            bpy.data.objects.remove(obj, do_unlink=True)
        raise
    finally:
        for o in bpy.context.selected_objects:
            o.select_set(False)
        for o in selection:
            o.select_set(True)
        bpy.context.view_layer.objects.active = active
