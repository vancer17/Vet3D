"""Read-only raw mesh measurements; loading and report policy belong to callers."""
import math
import numpy as np
from mesh_measure import measure_mesh


def object_bounds(obj, *, unit_mm, precision='float64'):
    """World-space min/max in mm, using explicit raw-coordinate read precision.

    NumPy applies matrix_world after foreach_get, preserving the existing
    float32/float64 reader profiles without a mathutils transform round-trip.
    """
    if not math.isfinite(unit_mm) or unit_mm <= 0:
        raise ValueError('Positive finite millimetres per coordinate unit required')
    if precision not in {'float32', 'float64'}:
        raise ValueError('Expected float32 or float64 precision')
    if obj.type != 'MESH' or not len(obj.data.vertices):
        raise ValueError('Nonempty mesh required: ' + obj.name)
    vertices = np.empty(len(obj.data.vertices) * 3, dtype=precision)
    obj.data.vertices.foreach_get('co', vertices)
    vertices = vertices.reshape(-1, 3)
    matrix = np.array(obj.matrix_world)
    points = (vertices @ matrix[:3, :3].T + matrix[:3, 3]) * unit_mm
    return points.min(0), points.max(0)


def measure_objects(objects, *, unit_mm, precision='float64', empty='error', topology_objects=()):
    """Measure selected raw meshes without changing scene, frame, or geometry.

    empty=error/skip/keep controls empty mesh rows; at least one nonempty mesh
    is required. Topology/volume is measured only for explicitly selected meshes,
    in local coordinates. Bounds always use world coordinates. Caller updates
    the dependency graph and chooses the scene frame before calling.
    """
    if empty not in {'error', 'skip', 'keep'}:
        raise ValueError('Expected error, skip or keep empty mesh policy')
    topology_objects = set(topology_objects)
    rows, lows, highs = [], [], []
    for obj in objects:
        if obj.type != 'MESH':
            continue
        if not len(obj.data.vertices) and empty == 'skip':
            continue
        bounds = None
        if len(obj.data.vertices) or empty == 'error':
            lo, hi = object_bounds(obj, unit_mm=unit_mm, precision=precision)
            lows.append(lo)
            highs.append(hi)
            bounds = [lo.tolist(), hi.tolist()]
        row = dict(name=obj.name, vertices=len(obj.data.vertices), faces=len(obj.data.polygons),
                   triangles=sum(len(p.vertices) - 2 for p in obj.data.polygons), bounds_mm=bounds)
        if obj in topology_objects:
            metrics = measure_mesh(obj.data, unit_mm=unit_mm)
            row.update(nonmanifold_edges=metrics['nonmanifold_edges'],
                       volume_mm3=abs(metrics['signed_volume_mm3']))
        rows.append(row)
    if not lows:
        raise ValueError('No nonempty mesh objects')
    low, high = np.min(lows, axis=0), np.max(highs, axis=0)
    return dict(objects=rows, bounds_mm=[low.tolist(), high.tolist()],
                dimensions_mm=(high - low).tolist())
