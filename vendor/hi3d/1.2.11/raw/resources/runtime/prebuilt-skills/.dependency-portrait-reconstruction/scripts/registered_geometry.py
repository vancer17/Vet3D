"""Array-only registered-surface correction; no archive or scene writes."""
import numpy as np
from collision import crossing_pairs
from geometry_compare import triangulate_faces
from contact_repair import repair


def native_coordinates(vertices, linear, offset):
    """Invert x_world = x_native @ linear.T + offset without modifying inputs."""
    vertices, linear, offset = (np.asarray(x, dtype=float) for x in (vertices, linear, offset))
    if (vertices.ndim != 2 or vertices.shape[1] != 3 or not len(vertices)
            or linear.shape != (3, 3) or offset.shape != (3,)
            or not all(np.isfinite(x).all() for x in (vertices, linear, offset))):
        raise ValueError('Finite Nx3 vertices, 3x3 linear and length-3 offset required')
    try:
        inverse = np.linalg.inv(linear)
    except np.linalg.LinAlgError as exc:
        raise ValueError('Registration transform must be invertible') from exc
    return (vertices - offset) @ inverse.T


def repair_registered_geometry(rest, vertices, faces, linear, offset, *, budget_fraction=1e-4, max_trials=1000):
    """Return corrected world/native vertices and bounded-repair diagnostics.

    Original arrays and topology remain unchanged. Baseline contacts are allowed;
    this does not prove eyelid closure, coplanar clearance or physical validity.
    """
    rest, vertices = np.asarray(rest, dtype=float), np.asarray(vertices, dtype=float)
    native_coordinates(vertices, linear, offset)  # Fail before repair on invalid transforms.
    triangles = triangulate_faces(faces)
    if rest.shape != vertices.shape or not np.isfinite(rest).all() or triangles.max() >= len(vertices):
        raise ValueError('Matching finite rest/current arrays and in-range faces required')
    if not np.isfinite(budget_fraction) or budget_fraction < 0 or not isinstance(max_trials, int) or max_trials < 0:
        raise ValueError('Nonnegative finite budget and integer trial limit required')
    baseline = set(map(tuple, crossing_pairs(rest, triangles)))
    corrected, report = repair(vertices, triangles, baseline, budget_fraction=budget_fraction, max_trials=max_trials)
    return corrected, native_coordinates(corrected, linear, offset), report
