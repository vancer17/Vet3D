"""Pure, local skin-weight repair. Bone semantics and regions are caller supplied."""

import numpy as np


def check_weights(weights, vertices=None):
    """Return a float array; reject malformed, negative or unnormalized input."""
    w = np.asarray(weights)
    if (
        w.ndim != 2
        or not w.shape[0]
        or not w.shape[1]
        or w.dtype.kind != "f"
        or not np.isfinite(w).all()
        or np.any(w < 0)
        or not np.allclose(w.sum(1), 1, atol=2e-4, rtol=0)
    ):
        raise ValueError("Expected finite nonnegative normalized N x B weights")
    if vertices is not None:
        v = np.asarray(vertices)
        if v.shape != (len(w), 3) or not np.isfinite(v).all():
            raise ValueError("Expected finite N x 3 rest vertices")
    return w


def repair_regions(vertices, weights, bone_names, rules):
    """Remove forbidden influences inside calibrated local-space boxes, then normalize.

    rules: [{bounds: [[x,y,z],[x,y,z]], forbidden_bones: [name,...]}].
    Only affected rows change; exact shared positions inside the selected domain
    receive equal weights. No bone-name inference, smoothing, top-k or geometry edits.
    Refuse empty regions, unknown bones and removal of every influence.
    """
    old = check_weights(weights, vertices)
    v = np.asarray(vertices)
    names = list(bone_names)
    if len(names) != old.shape[1] or len(set(names)) != len(names) or not rules:
        raise ValueError("Unique ordered bone names and nonempty rules required")
    result = old.copy()
    selected = np.zeros(len(v), dtype=bool)
    reports = []
    for rule in rules:
        if set(rule) != {"bounds", "forbidden_bones"}:
            raise ValueError("Each rule requires only bounds and forbidden_bones")
        bounds = np.asarray(rule["bounds"], dtype=float)
        forbidden = rule["forbidden_bones"]
        if (
            bounds.shape != (2, 3)
            or not np.isfinite(bounds).all()
            or np.any(bounds[0] > bounds[1])
            or not forbidden
            or not isinstance(forbidden, list)
            or len(set(forbidden)) != len(forbidden)
        ):
            raise ValueError("Invalid region or forbidden bones")
        columns = [names.index(name) for name in forbidden]
        ids = np.flatnonzero(np.all((v >= bounds[0]) & (v <= bounds[1]), axis=1))
        if not len(ids):
            raise ValueError("Region contains no vertices; check the coordinate space")
        selected[ids] = True
        removed = result[ids][:, columns].sum(1)
        affected = ids[removed > 0]
        result[np.ix_(affected, columns)] = 0
        totals = result[affected].sum(1, keepdims=True)
        if np.any(totals <= 1e-12):
            raise ValueError(
                "Repair would leave vertices unbound; calibrate retained influences"
            )
        result[affected] /= totals
        reports.append(
            dict(
                vertices=len(ids),
                affected=len(affected),
                max_removed_weight=float(removed.max()),
            )
        )
    ids = np.flatnonzero(selected)
    _, inverse, counts = np.unique(
        v[ids], axis=0, return_inverse=True, return_counts=True
    )
    sums = np.zeros((len(counts), old.shape[1]), dtype=np.float64)
    np.add.at(sums, inverse, result[ids])
    result[ids] = (sums / counts[:, None])[inverse]
    check_weights(result)
    changed = np.flatnonzero(np.any(result != old, axis=1))
    return result, dict(
        changed_vertices=len(changed),
        rules=reports,
        shared_position_duplicates=int((counts - 1).sum()),
    )


def stretch_metrics(rest, posed, faces, height):
    """Ratio AND absolute-growth screening; face ids refer to the supplied triangles."""
    v, p, f = np.asarray(rest), np.asarray(posed), np.asarray(faces)
    if (
        v.ndim != 2
        or v.shape[1] != 3
        or p.shape != v.shape
        or not np.isfinite(v).all()
        or not np.isfinite(p).all()
        or f.ndim != 2
        or f.shape[1] != 3
        or f.dtype.kind not in "iu"
        or not len(f)
        or f.min() < 0
        or f.max() >= len(v)
        or not np.isfinite(height)
        or height <= 0
    ):
        raise ValueError(
            "Expected matching finite surfaces, valid triangles and positive height"
        )
    lengths = []
    areas = []
    for points in (v, p):
        lengths.append(
            np.stack(
                [
                    np.linalg.norm(points[f[:, a]] - points[f[:, b]], axis=1)
                    for a, b in [(0, 1), (1, 2), (2, 0)]
                ],
                axis=1,
            )
        )
        areas.append(
            np.linalg.norm(
                np.cross(
                    points[f[:, 1]] - points[f[:, 0]], points[f[:, 2]] - points[f[:, 0]]
                ),
                axis=1,
            )
        )
    ratio = lengths[1] / np.maximum(lengths[0], height * 5.56e-8)
    area_ratio = areas[1] / np.maximum(areas[0], height**2 * 3.1e-11)
    significant = ((ratio > 3) & (lengths[1] - lengths[0] > height / 120)).any(1)
    area_bad = (area_ratio > 8) & (areas[1] - areas[0] > height**2 / 81000)
    ids = np.flatnonzero(significant | area_bad)
    worst = ids[np.argsort(ratio[ids].max(1))[::-1]][:20]
    return dict(
        significant_faces=int(significant.sum()),
        large_area_faces=int(area_bad.sum()),
        bad_face_count=len(ids),
        max_edge_ratio=float(ratio.max()),
        max_area_ratio=float(area_ratio.max()),
        max_edge_growth=float((lengths[1] - lengths[0]).max()),
        worst_faces=worst.tolist(),
        worst_face_metrics=[
            dict(
                face=int(i),
                edge_ratio=float(ratio[i].max()),
                area_ratio=float(area_ratio[i]),
            )
            for i in worst
        ],
    )
