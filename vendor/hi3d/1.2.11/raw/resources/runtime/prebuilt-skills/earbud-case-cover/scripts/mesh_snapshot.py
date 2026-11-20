"""Detached mesh snapshots. No file I/O, topology repair, or product policy."""
from contextlib import contextmanager
import numpy as np


@contextmanager
def mesh_source(obj, *, evaluated, depsgraph=None):
    """Yield (source object, mesh); own and release only temporary conversions."""
    import bpy
    if obj.type not in {'MESH','CURVE','SURFACE','FONT','META'}:
        raise ValueError('Mesh-convertible object required')
    source = obj.evaluated_get(depsgraph or bpy.context.evaluated_depsgraph_get()) if evaluated else obj
    temporary = evaluated or obj.type != 'MESH'
    mesh = None
    try:
        mesh = source.to_mesh() if temporary else source.data
        if mesh is None: raise ValueError('Object produced no mesh')
        yield source, mesh
    finally:
        if temporary: source.to_mesh_clear()


def mesh_data_snapshot(mesh, *, transform=None, scale=1.0, triangulation='loop', precision='float64', fields=()):
    """Copy coordinates and indices; optional loop UVs/material names are detached."""
    fields = set(fields)
    if triangulation not in {'loop','require_triangles','bmesh'} or precision not in {'float32','float64'}:
        raise ValueError('Invalid triangulation or coordinate precision')
    if not np.isfinite(scale) or scale <= 0 or fields - {'loops','uv','materials'}:
        raise ValueError('Positive finite scale and supported fields required')
    if triangulation == 'require_triangles' and any(len(p.vertices)!=3 for p in mesh.polygons):
        raise ValueError('Triangulated mesh required')
    if triangulation == 'bmesh':
        if fields: raise ValueError('Attribute snapshots require loop triangulation')
        import bmesh
        bm = bmesh.new()
        try:
            bm.from_mesh(mesh)
            if transform is not None: bm.transform(transform)
            bmesh.ops.triangulate(bm,faces=list(bm.faces)); bm.verts.index_update()
            vertices = np.asarray([v.co[:] for v in bm.verts],dtype=precision).reshape(-1,3)*scale
            triangles = np.asarray([[v.index for v in f.verts] for f in bm.faces],dtype=np.int32).reshape(-1,3)
        finally: bm.free()
    else:
        mesh.calc_loop_triangles()
        vertices = np.asarray([transform @ v.co if transform is not None else v.co[:] for v in mesh.vertices],dtype=precision).reshape(-1,3)*scale
        triangles = np.asarray([tuple(t.vertices) for t in mesh.loop_triangles],dtype=np.int32).reshape(-1,3)
    result = {'vertices':vertices, 'triangles':triangles,
              'bounds':(vertices.min(0),vertices.max(0)) if len(vertices) else None}
    if 'loops' in fields or 'uv' in fields:
        result['triangle_loops'] = np.asarray([tuple(t.loops) for t in mesh.loop_triangles],dtype=np.int32).reshape(-1,3)
    if 'uv' in fields:
        result['uv'] = {layer.name:np.asarray([tuple(v.uv) for v in layer.data],dtype=np.float32).reshape(-1,2) for layer in mesh.uv_layers}
    if 'materials' in fields:
        result['materials'] = tuple(m.name if m else None for m in mesh.materials)
        result['triangle_materials'] = np.asarray([t.material_index for t in mesh.loop_triangles],dtype=np.int32)
    return result


def mesh_snapshot(obj, *, evaluated, space, scale=1.0, triangulation='loop', precision='float64', fields=(), depsgraph=None):
    """Explicit raw/evaluated, local/world snapshot, releasing converted meshes."""
    if space not in {'local','world'}: raise ValueError('Explicit local/world space required')
    with mesh_source(obj,evaluated=evaluated,depsgraph=depsgraph) as (source,mesh):
        return mesh_data_snapshot(mesh,transform=source.matrix_world if space=='world' else None,
                                  scale=scale,triangulation=triangulation,precision=precision,fields=fields)
