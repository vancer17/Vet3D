"""Crossing tests after a BVH broad phase; tangency/coplanarity are not crossings."""

import numpy as np
if __package__:
    from .triangle_arrays import triangle_double_areas
else:
    from triangle_arrays import triangle_double_areas


def segment_hits_triangle(start, end, triangle, eps=1e-9):
    direction = end - start
    e1 = triangle[:, 1] - triangle[:, 0]
    e2 = triangle[:, 2] - triangle[:, 0]
    p = np.cross(direction, e2)
    det = np.einsum("ni,ni->n", e1, p)
    valid = np.abs(det) > eps
    inverse = np.divide(1, det, out=np.zeros_like(det), where=valid)
    tvec = start - triangle[:, 0]
    u = np.einsum("ni,ni->n", tvec, p) * inverse
    q = np.cross(tvec, e1)
    v = np.einsum("ni,ni->n", direction, q) * inverse
    t = np.einsum("ni,ni->n", e2, q) * inverse
    return valid & (u > eps) & (v > eps) & (u + v < 1 - eps) & (t > eps) & (t < 1 - eps)


def crossing_pairs(vertices, triangles):
    from mathutils.bvhtree import BVHTree

    bvh = BVHTree.FromPolygons(
        vertices.tolist(), triangles.tolist(), all_triangles=True
    )
    pairs = np.array([(a, b) for a, b in bvh.overlap(bvh) if a < b], dtype=int).reshape(
        -1, 2
    )
    if not len(pairs):
        return pairs
    a, b = triangles[pairs[:, 0]], triangles[pairs[:, 1]]
    pairs = pairs[~np.any(a[:, :, None] == b[:, None, :], axis=(1, 2))]
    if not len(pairs):
        return pairs
    ta, tb = vertices[triangles[pairs[:, 0]]], vertices[triangles[pairs[:, 1]]]
    crossed = np.zeros(len(pairs), bool)
    # Scale to a unit extent so numerical tolerance does not encode the source units.
    extent = np.ptp(vertices, axis=0).max()
    ta = ta / extent
    tb = tb / extent
    for i in range(3):
        crossed |= segment_hits_triangle(ta[:, i], ta[:, (i + 1) % 3], tb)
        crossed |= segment_hits_triangle(tb[:, i], tb[:, (i + 1) % 3], ta)
    return pairs[crossed]


def triangle_stats(vertices, triangles):
    area2 = triangle_double_areas(vertices, triangles)
    scale = np.ptp(vertices, axis=0).max()
    return {
        "finite": bool(np.isfinite(vertices).all()),
        "degenerate_triangles": int(np.sum(area2 <= max(scale * scale * 1e-12, np.finfo(float).tiny))),
        "area2_min": float(area2.min()),
    }
