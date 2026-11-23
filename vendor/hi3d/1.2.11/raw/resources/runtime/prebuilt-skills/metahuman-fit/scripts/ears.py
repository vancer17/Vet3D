"""Rigid template ear restoration with a bounded transition at the ear root."""

import numpy as np
from scipy.sparse import eye
from scipy.sparse.linalg import spsolve
from brush import adjacency


def rigid_alignment(source, target):
    a, b = source.mean(0), target.mean(0)
    if len(source) < 4 or np.linalg.matrix_rank(source - a) < 2:
        raise ValueError("Ear alignment needs at least four non-collinear root anchors")
    u, _, vt = np.linalg.svd((source - a).T @ (target - b))
    signs = np.ones(3)
    signs[-1] = np.linalg.det(vt.T @ u.T)
    rotation = vt.T @ np.diag(signs) @ u.T
    return rotation, b - a @ rotation.T


def restore_ears(rest, fitted, quads, regions, max_fraction=0.05):
    """Preserve each complete template ear up to a rigid transform; only root bands blend."""
    a, _ = adjacency(quads, len(rest))
    lap = eye(len(rest), format="csr") - a
    energy = (lap.T @ lap).tocsr()
    result = fitted.copy()
    reports = []
    touched = set()
    for region in regions:
        core = np.asarray(region["core_indices"], int)
        band = np.asarray(region["blend_indices"], int)
        anchors = np.asarray(region["anchor_indices"], int)
        if not len(core) or not len(band) or len(anchors) < 4:
            raise ValueError(
                "Ear regions need a core, transition band and root anchors"
            )
        if (
            np.intersect1d(core, band).size
            or np.intersect1d(np.r_[core, band], anchors).size
        ):
            raise ValueError("Ear core, transition and anchors must be disjoint")
        active = set(np.r_[core, band].tolist())
        if active & touched:
            raise ValueError("Ear transition regions overlap")
        touched |= active
        rotation, offset = rigid_alignment(rest[anchors], fitted[anchors])
        goal = rest @ rotation.T + offset
        delta = np.zeros_like(rest)
        delta[core] = goal[core] - fitted[core]
        fixed = np.setdiff1d(np.arange(len(rest)), band)
        delta[band] = spsolve(
            energy[band][:, band].tocsc(), -(energy[band][:, fixed] @ delta[fixed])
        )
        if (
            not np.isfinite(delta).all()
            or np.linalg.norm(delta, axis=1).max()
            > max_fraction * np.ptp(fitted, axis=0).max()
        ):
            raise ValueError("Template ear correction exceeds its distance budget")
        result[core] = goal[core]
        result[band] = fitted[band] + delta[band]
        reports.append(
            dict(
                name=region.get("name", "ear"),
                core_vertices=len(core),
                transition_vertices=len(band),
                rotation=rotation.tolist(),
                translation=offset.tolist(),
                maximum_displacement=float(np.linalg.norm(delta, axis=1).max()),
                rigid_core_error=float(np.abs(result[core] - goal[core]).max()),
            )
        )
    return result, reports
