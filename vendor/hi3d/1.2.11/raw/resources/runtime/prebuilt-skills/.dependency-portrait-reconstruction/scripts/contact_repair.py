"""Bounded corrections of tiny newly introduced neutral contacts; not a global untangler."""

import numpy as np
from collision import crossing_pairs


def repair(vertices, triangles, baseline, budget_fraction=1e-4, max_trials=1000):
    """Accept only fewer new pairs, finite coordinates and retained local orientation."""
    original = vertices.copy()
    v = vertices.copy()
    extent = np.ptp(v, axis=0).max()
    current = set(map(tuple, crossing_pairs(v, triangles))) - baseline
    history = []
    trials = 0
    initial = len(current)
    while current and trials < max_trials:
        improved = False
        for pair in sorted(current):
            ids = np.unique(triangles[list(pair)])
            p = v[triangles[list(pair)]]
            normals = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
            normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-12)
            directions = np.r_[normals, np.eye(3)]
            for scale in [1e-6, 5e-6, 2e-5, 1e-4]:
                if scale > budget_fraction:
                    continue
                for vertex in ids:
                    affected = triangles[np.any(triangles == vertex, axis=1)]
                    before = v[affected]
                    n = np.cross(
                        before[:, 1] - before[:, 0], before[:, 2] - before[:, 0]
                    )
                    for direction in directions:
                        for sign in [-1, 1]:
                            if trials >= max_trials:
                                break
                            trials += 1
                            candidate = v.copy()
                            candidate[vertex] += direction * extent * scale * sign
                            if (
                                np.linalg.norm(candidate[vertex] - original[vertex])
                                > extent * budget_fraction
                            ):
                                continue
                            p = candidate[affected]
                            new_n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
                            if np.any(
                                np.einsum("ij,ij->i", n, new_n)
                                < 0.5 * np.einsum("ij,ij->i", n, n)
                            ):
                                continue
                            found = (
                                set(map(tuple, crossing_pairs(candidate, triangles)))
                                - baseline
                            )
                            if len(found) < len(current):
                                v = candidate
                                current = found
                                improved = True
                                history.append(
                                    dict(
                                        vertex=int(vertex),
                                        displacement=(
                                            direction * extent * scale * sign
                                        ).tolist(),
                                        remaining=len(current),
                                    )
                                )
                                break
                        if improved or trials >= max_trials:
                            break
                    if improved or trials >= max_trials:
                        break
                if improved or trials >= max_trials:
                    break
            if improved or trials >= max_trials:
                break
        if not improved:
            break
    return v, dict(
        initial_new_crossings=initial,
        new_crossings=len(current),
        trials=trials,
        history=history,
        budget_fraction=budget_fraction,
        maximum_displacement=float(np.linalg.norm(v - original, axis=1).max()),
    )
