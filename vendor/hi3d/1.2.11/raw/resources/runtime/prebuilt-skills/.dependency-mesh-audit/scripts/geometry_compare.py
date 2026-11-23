"""Pure baseline comparison; never repairs or writes a mesh. Requires mathutils."""
import numpy as np
from collision import crossing_pairs, triangle_stats


def triangulate_faces(faces):
    """Validate integer triangles/quads; keep all first quad halves before seconds."""
    faces = np.asarray(faces)
    if faces.ndim != 2 or faces.shape[1] not in (3, 4) or not len(faces):
        raise ValueError("faces must be nonempty triangles or quads")
    if not np.issubdtype(faces.dtype, np.integer) or np.any(faces < 0):
        raise ValueError("face indices must be nonnegative integers")
    if faces.shape[1] == 3:
        return faces.copy()
    return np.concatenate([faces[:, [0, 1, 2]], faces[:, [0, 2, 3]]])


def compare_geometry(rest, current, faces):
    """Compare same-topology finite Nx3 arrays in a common coordinate system.

    Strict surface crossings only: tangency, coplanarity, shared vertices and
    containment are excluded. Both arrays remain unchanged. Invalid inputs raise
    ValueError before BVH evaluation; degenerate geometry returns a failed report.
    """
    rest, current = np.asarray(rest, dtype=float), np.asarray(current, dtype=float)
    triangles = triangulate_faces(faces)
    if (rest.ndim != 2 or rest.shape[1] != 3 or not len(rest)
            or current.shape != rest.shape or triangles.max() >= len(rest)):
        raise ValueError("matching Nx3 arrays and in-range face indices required")
    if not np.isfinite(rest).all() or not np.isfinite(current).all():
        raise ValueError("baseline and current coordinates must be finite")
    baseline = set(map(tuple, crossing_pairs(rest, triangles)))
    present = set(map(tuple, crossing_pairs(current, triangles)))
    added = sorted(present - baseline)
    stats = triangle_stats(current, triangles)
    return dict(
        **stats,
        baseline_crossings=len(baseline), current_crossings=len(present),
        new_crossings=len(added), new_pairs=[list(map(int, p)) for p in added],
        new_contact_centers=[current[triangles[list(p)]].mean((0, 1)).tolist() for p in added],
        geometry_passed=not added and stats["finite"] and not stats["degenerate_triangles"],
    )
