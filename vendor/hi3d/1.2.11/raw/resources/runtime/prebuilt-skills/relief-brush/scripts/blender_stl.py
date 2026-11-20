"""Evaluated Blender meshes to millimetre triangles and pure binary STL bytes."""
import struct
import numpy as np
if __package__:
    from .mesh_snapshot import mesh_snapshot
else:
    from mesh_snapshot import mesh_snapshot


def evaluated_triangles(objects, *, scale=1000.0):
    triangles = []
    for obj in objects:
        data = mesh_snapshot(obj, evaluated=True, space='world', scale=scale)
        triangles.append(data['vertices'][data['triangles']])
    return np.concatenate(triangles) if triangles else np.empty((0,3,3), dtype=float)


def stl_bytes(triangles_mm, *, header, padding=b" ", precision="float64", normal_floor=0.0):
    """Serialize triangles without welding, repair or precision filtering."""
    triangles = np.asarray(triangles_mm, dtype=precision)
    if triangles.ndim != 3 or triangles.shape[1:] != (3, 3) or not np.isfinite(triangles).all():
        raise ValueError("finite Nx3x3 millimetre triangles required")
    if len(header) > 80 or len(padding) != 1:
        raise ValueError("STL header max 80 bytes; one padding byte required")
    if precision not in ("float32", "float64") or not np.isfinite(normal_floor) or normal_floor < 0:
        raise ValueError("float32/float64 precision and nonnegative finite normal floor required")
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = np.divide(normals, np.maximum(lengths, normal_floor), out=np.zeros_like(normals), where=(lengths > 0) | (normal_floor > 0))
    rows = [struct.pack("<12fH", *n, *t.ravel(), 0) for n, t in zip(normals, triangles)]
    return header.ljust(80, padding) + struct.pack("<I", len(rows)) + b"".join(rows)

def raw_triangles(obj, *, world, scale=1000.0, triangulation="loop", precision="float64"):
    data = mesh_snapshot(obj, evaluated=False, space='world' if world else 'local',
                         scale=scale, triangulation=triangulation, precision=precision)
    return data['vertices'][data['triangles']]
