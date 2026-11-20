"""Bounded ear-fit acceptance against the template and incoming registration."""

import numpy as np
from collision import crossing_pairs, triangle_stats
from contact_repair import repair
from geometry_compare import triangulate_faces


def guard_ears(
    rest, baseline, initial, candidate, quads, ear_indices, protected_indices
):
    arrays = [np.asarray(a, float) for a in (rest, baseline, initial, candidate)]
    rest, baseline, initial, candidate = arrays
    if (
        baseline.ndim != 2
        or baseline.shape[1] != 3
        or any(a.shape != baseline.shape or not np.isfinite(a).all() for a in arrays)
    ):
        raise ValueError("Matching finite vertex arrays required")
    tri = triangulate_faces(quads)
    if tri.min() < 0 or tri.max() >= len(baseline):
        raise ValueError("Topology references missing vertices")
    protected = np.asarray(protected_indices, int)
    earids = set(ear_indices)
    if (
        not len(protected)
        or not earids
        or min(*earids, int(protected.min())) < 0
        or max(*earids, int(protected.max())) >= len(baseline)
    ):
        raise ValueError("Valid protected and ear indices required")
    pairs = lambda v: set(map(tuple, crossing_pairs(v, tri)))
    template_pairs = pairs(rest)
    allowed = template_pairs | pairs(baseline)
    if pairs(initial) - allowed or triangle_stats(initial, tri)["degenerate_triangles"]:
        raise ValueError("Unsafe ear initializer")
    candidate_new = len(pairs(candidate) - allowed)
    corrected, _ = repair(candidate, tri, allowed, budget_fraction=1e-4, max_trials=120)
    fraction = 1.0
    if not pairs(corrected) - allowed:
        vertices = corrected
    else:
        for fraction in np.arange(0.95, -0.01, -0.05):
            vertices = initial + max(0.0, float(fraction)) * (candidate - initial)
            if not pairs(vertices) - allowed:
                break
    # A bounded repair may also reduce old contacts, but may never move anchors.
    repaired, _ = repair(
        vertices, tri, template_pairs, budget_fraction=1e-4, max_trials=120
    )
    if not pairs(repaired) - allowed and np.array_equal(
        repaired[protected], baseline[protected]
    ):
        vertices = repaired
    final_pairs = pairs(vertices)
    anchor_delta = float(
        np.linalg.norm(vertices[protected] - baseline[protected], axis=1).max()
    )
    report = dict(
        candidate_added_crossings=candidate_new,
        volume_fraction=max(0.0, float(fraction)),
        new_crossings_vs_template=len(final_pairs - template_pairs),
        new_crossings_vs_baseline=len(final_pairs - allowed),
        ear_crossings=sum(
            bool(set(tri[list(p)].ravel()) & earids)
            for p in final_pairs - template_pairs
        ),
        eye_lip_anchor_max_displacement=anchor_delta,
        **triangle_stats(vertices, tri)
    )
    report["ear_geometry_passed"] = bool(
        report["finite"]
        and not report["ear_crossings"]
        and not report["new_crossings_vs_baseline"]
        and not report["degenerate_triangles"]
        and anchor_delta < 1e-8
    )
    report["whole_geometry_passed"] = bool(
        report["finite"]
        and not (final_pairs - template_pairs)
        and not report["degenerate_triangles"]
    )
    if not report["ear_geometry_passed"]:
        raise ValueError("Ear geometry rejected: " + str(report))
    return vertices, report
