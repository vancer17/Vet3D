"""Bounded surface sampling and normal-aware smoothing, independent of Blender."""

import numpy as np


def sample_surface(vertices, triangles, vertex_normals, count=100000, seed=0):
    if not isinstance(count, int) or count < 1000 or count > 1000000:
        raise ValueError("Surface sample count must be 1000..1000000")
    area = np.empty(len(triangles))
    for first in range(0, len(triangles), 200000):
        p = vertices[triangles[first : first + 200000]]
        area[first : first + len(p)] = np.linalg.norm(
            np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1
        )
    if not np.isfinite(area).all() or area.sum() <= 0:
        raise ValueError("Source has no finite nondegenerate surface")
    rng = np.random.default_rng(seed)
    ids = rng.choice(len(triangles), count, p=area / area.sum())
    uv = rng.random((count, 2))
    folded = uv.sum(1) > 1
    uv[folded] = 1 - uv[folded]
    barycentric = np.c_[1 - uv.sum(1), uv]
    points = np.einsum("ni,nij->nj", barycentric, vertices[triangles[ids]])
    normals = np.einsum("ni,nij->nj", barycentric, vertex_normals[triangles[ids]])
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-12)
    return points, normals, ids, barycentric


def smooth_samples(points, normals, radius_fraction=0.006):
    """One normal-aware local plane projection; source assets remain untouched."""
    from scipy.spatial import cKDTree

    if not 0 <= radius_fraction <= 0.03:
        raise ValueError("Surface smoothing fraction must be 0..0.03")
    if radius_fraction == 0:
        return points.copy(), normals.copy()
    radius = np.ptp(points, axis=0).max() * radius_fraction
    distance, ids = cKDTree(points).query(points, k=min(32, len(points)), workers=-1)
    compatible = np.einsum("nc,nkc->nk", normals, normals[ids]) > 0.7
    weights = (
        np.exp(-0.5 * (distance / max(radius, 1e-12)) ** 2)
        * compatible
        * (distance < 3 * radius)
    )
    weights /= np.maximum(weights.sum(1, keepdims=True), 1e-12)
    center = np.einsum("nk,nkc->nc", weights, points[ids])
    average = np.einsum("nk,nkc->nc", weights, normals[ids])
    average /= np.maximum(np.linalg.norm(average, axis=1, keepdims=True), 1e-12)
    offset = np.sum((center - points) * average, axis=1)
    result = points + np.clip(offset, -radius, radius)[:, None] * average
    return result, average
