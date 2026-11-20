"""First-hit height sampling from explicit geometry; Blender BVH backend."""
import numpy as np


def sample_mesh(vertices, faces, *, resolution, axes=(0, 1, 2), front_sign=1,
                ray_margin=1.0, all_triangles=False):
    """Return float32 signed depth, valid mask and original-coordinate bounds.

    No imports, unit conversion or scene/file changes. NaN denotes missed rays.
    Caller chooses physical units, baseline, aspect and normalization policy.
    """
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    vertices = np.asarray(vertices, dtype=float)
    if (vertices.ndim != 2 or vertices.shape[1] != 3 or not len(vertices)
            or not np.isfinite(vertices).all() or not len(faces)):
        raise ValueError("finite nonempty vertices and faces required")
    if (len(resolution) != 2 or any(type(n) is not int or n < 8 for n in resolution)
            or len(axes) != 3 or set(axes) != {0, 1, 2} or front_sign not in (-1, 1)
            or not np.isfinite(ray_margin) or ray_margin <= 0):
        raise ValueError("Invalid resolution, axes, front sign or ray margin")
    for face in faces:
        if len(face) < 3 or any(not isinstance(i, (int, np.integer)) or i < 0 or i >= len(vertices) for i in face):
            raise ValueError("face indices must be valid polygons")
    wa, ha, da = axes
    lo, hi = vertices.min(0), vertices.max(0)
    if hi[wa] <= lo[wa] or hi[ha] <= lo[ha]:
        raise ValueError("Source has no projected area")
    tree = BVHTree.FromPolygons(vertices.tolist(), [list(f) for f in faces], all_triangles=all_triangles)
    nx, ny = resolution
    raw = np.full((ny, nx), np.nan, np.float32)
    direction = np.zeros(3); direction[da] = -front_sign
    start = lo[da] - ray_margin if front_sign < 0 else hi[da] + ray_margin
    for j, y in enumerate(np.linspace(lo[ha], hi[ha], ny)):
        for i, x in enumerate(np.linspace(lo[wa], hi[wa], nx)):
            point = np.zeros(3); point[wa] = x; point[ha] = y; point[da] = start
            hit = tree.ray_cast(Vector(point), Vector(direction), float(hi[da]-lo[da]+2*ray_margin))[0]
            if hit is not None:
                raw[j, i] = front_sign * hit[da]
    return raw, np.isfinite(raw), np.stack([lo, hi])
