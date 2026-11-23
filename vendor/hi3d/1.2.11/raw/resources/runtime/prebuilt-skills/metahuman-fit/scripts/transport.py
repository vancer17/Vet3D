"""Geometry transport for DNA neutral joints, lower LODs and corrective deltas."""

import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation
from brush import vertex_normals


def local_jacobians(rest, registered, quads):
    e = np.concatenate([quads[:, [i, (i + 1) % 4]] for i in range(4)])
    e = np.unique(np.sort(e, axis=1), axis=0)
    a = np.r_[e[:, 0], e[:, 1]]
    b = np.r_[e[:, 1], e[:, 0]]
    x = rest[b] - rest[a]
    y = registered[b] - registered[a]
    cov = np.zeros((len(rest), 3, 3))
    cross = np.zeros_like(cov)
    for i in range(3):
        for j in range(3):
            cov[:, i, j] = np.bincount(
                a, weights=x[:, i] * x[:, j], minlength=len(rest)
            )
            cross[:, i, j] = np.bincount(
                a, weights=y[:, i] * x[:, j], minlength=len(rest)
            )
    tri = np.concatenate([quads[:, [0, 1, 2]], quads[:, [0, 2, 3]]])
    n0 = vertex_normals(rest, tri)
    n1 = vertex_normals(registered, tri)
    scale = np.maximum(np.trace(cov, axis1=1, axis2=2), 1e-10)
    cov += scale[:, None, None] * np.einsum("ni,nj->nij", n0, n0)
    cross += scale[:, None, None] * np.einsum("ni,nj->nij", n1, n0)
    cov += np.eye(3)[None] * scale[:, None, None] * 1e-6
    return cross @ np.linalg.inv(cov)


class Transport:
    def __init__(self, rest, registered):
        self.rest = np.asarray(rest)
        self.delta = np.asarray(registered) - rest
        self.tree = cKDTree(rest)

    def offsets(self, points):
        distance, ids = self.tree.query(points, k=min(12, len(self.rest)), workers=-1)
        weight = 1 / np.maximum(distance, 1e-5) ** 2
        weight /= weight.sum(1, keepdims=True)
        # Keep body data outside the head region unchanged.
        fade = np.clip(
            1 - distance[:, 0] / (np.ptp(self.rest, axis=0).max() * 0.15), 0, 1
        )
        return np.einsum("nk,nkc->nc", weight, self.delta[ids]) * fade[:, None]

    def __call__(self, points):
        return np.asarray(points) + self.offsets(points)


def joint_world(translations, rotations, parents):
    local = Rotation.from_euler("xyz", rotations, degrees=True).as_matrix()
    world = np.empty_like(local)
    positions = np.empty_like(translations)
    for i, p in enumerate(parents):
        if p == i or p < 0:
            world[i] = local[i]
            positions[i] = translations[i]
        else:
            if p >= i:
                raise ValueError("DNA joints must be ordered parent before child")
            world[i] = world[p] @ local[i]
            positions[i] = positions[p] + world[p] @ translations[i]
    return positions, world


def joint_local(positions, world, parents):
    return np.array(
        [
            (
                positions[i]
                if p == i or p < 0
                else world[p].T @ (positions[i] - positions[p])
            )
            for i, p in enumerate(parents)
        ]
    )
