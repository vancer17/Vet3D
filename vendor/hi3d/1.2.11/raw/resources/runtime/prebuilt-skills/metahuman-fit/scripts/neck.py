"""Extend the fitted head displacement smoothly through an explicitly unobserved neck region."""

import numpy as np


def validate_neck_mask(indices, protected_indices):
    """Reject an unreviewed mask or any overlap with identity-bearing skin."""
    free = np.unique(np.asarray(indices, int))
    protected = np.unique(np.asarray(protected_indices, int))
    if len(free) and not len(protected):
        raise ValueError(
            "Neck repair requires an explicit identity_protected_indices mask"
        )
    overlap = np.intersect1d(free, protected)
    if len(overlap):
        raise ValueError(
            f"Neck repair overlaps {len(overlap)} protected facial vertices; correct the masks"
        )
    return free, protected


def fair_neck(rest, fitted, quads, indices, protected_indices, max_fraction=0.2):
    """Minimize bending of template-relative displacement with every other vertex fixed."""
    from scipy.sparse import eye
    from scipy.sparse.linalg import spsolve
    from brush import adjacency

    free, protected = validate_neck_mask(indices, protected_indices)
    fixed = np.setdiff1d(np.arange(len(rest)), free)
    if len(free) == 0:
        return fitted.copy(), dict(vertices=0, maximum_displacement=0.0)
    if len(fixed) < 4:
        raise ValueError("Neck fairing requires fixed head and lower boundary anchors")
    a, _ = adjacency(quads, len(rest))
    lap = eye(len(rest), format="csr") - a
    energy = (lap.T @ lap).tocsr()
    delta = fitted - rest
    extended = delta.copy()
    extended[free] = spsolve(
        energy[free][:, free].tocsc(), -(energy[free][:, fixed] @ delta[fixed])
    )
    result = fitted.copy()
    result[free] = rest[free] + extended[free]
    maximum = float(np.linalg.norm(result - fitted, axis=1).max())
    if (
        not np.isfinite(result).all()
        or maximum > max_fraction * np.ptp(fitted, axis=0).max()
    ):
        raise ValueError(
            "Neck extension is singular or exceeds its displacement budget"
        )
    return result, dict(
        vertices=len(free),
        protected_vertices=len(protected),
        protected_maximum_displacement=float(
            np.linalg.norm(result[protected] - fitted[protected], axis=1).max()
        ),
        maximum_displacement=maximum,
        max_fraction=max_fraction,
        bending_energy_before=float(np.sum((lap @ delta) ** 2)),
        bending_energy_after=float(np.sum((lap @ extended) ** 2)),
        policy="Template-relative biharmonic extension on the supplied neck mask; all other vertices fixed. Unobserved neck is a template prior, not scan recovery.",
    )
