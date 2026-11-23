if __package__:
    from .blender_stl import evaluated_triangles, stl_bytes
else:
    from blender_stl import evaluated_triangles, stl_bytes
import bpy, bmesh, numpy as np, math, json, struct, os, pathlib
from pathlib import Path
from mathutils import Vector, Matrix
from math import sin, cos, pi
MM = S = .001
def prepare_stl_triangles(triangles_mm):
 """Quantize to STL float32, removing only exact zero-area serialized triangles.

 The removal handles vertices that become exactly coincident at file precision.
 Nonzero tiny faces are retained. Returns array and count; no mesh/file changes.
 """
 t=np.asarray(triangles_mm,dtype=np.float32).reshape(-1,3,3)
 if not len(t) or not np.isfinite(t).all():raise ValueError('Nonempty finite triangles required')
 q=t.astype(np.float64);area2=np.linalg.norm(np.cross(q[:,1]-q[:,0],q[:,2]-q[:,0]),axis=1)
 keep=area2>0
 if not keep.any():raise ValueError('No positive-area triangles remain at STL precision')
 return t[keep],int((~keep).sum())


def export_stl(path, objects):
    """Only remove exact zero-area triangles after float32 mm quantization."""
    array, removed = prepare_stl_triangles(evaluated_triangles(objects))
    Path(path).write_bytes(stl_bytes(array, header=b'Millimetres | evaluated independent printable part'))
    if len(objects) == 1:
        objects[0]['stl_exact_zero_area_faces_removed'] = removed
    return {'triangles': len(array), 'exact_zero_area_faces_removed_at_float32_mm': removed}
