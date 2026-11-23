"""Spatial Gaussian brush registration in 3D; topology and vertex order are fixed."""

import numpy as np
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix, diags


def similarity(source, target, weights=None):
    source, target = np.asarray(source, float), np.asarray(target, float)
    w = np.ones(len(source)) if weights is None else np.asarray(weights, float)
    if (
        len(source) < 4
        or np.linalg.matrix_rank(source - source.mean(0)) < 2
        or (w <= 0).any()
    ):
        raise ValueError(
            "At least four non-collinear, positively weighted landmarks are required"
        )
    w = w / w.sum()
    a = w @ source
    b = w @ target
    x = source - a
    y = target - b
    u, s, vt = np.linalg.svd((x * w[:, None]).T @ y)
    signs = np.ones(3)
    signs[-1] = np.linalg.det(vt.T @ u.T)
    rotation = vt.T @ np.diag(signs) @ u.T
    scale = (s * signs).sum() / np.sum(w[:, None] * x * x)
    if scale <= 0:
        raise ValueError("Invalid similarity scale")
    linear = scale * rotation
    return linear, b - a @ linear.T


def adjacency(quads, count):
    e = np.concatenate([quads[:, [i, (i + 1) % 4]] for i in range(4)])
    e = np.unique(np.sort(e, axis=1), axis=0)
    a = coo_matrix(
        (np.ones(len(e) * 2), (np.r_[e[:, 0], e[:, 1]], np.r_[e[:, 1], e[:, 0]])),
        shape=(count, count),
    ).tocsr()
    return diags(1 / np.maximum(np.asarray(a.sum(1)).ravel(), 1)) @ a, e


def vertex_normals(vertices, triangles):
    p = vertices[triangles]
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    out = np.zeros_like(vertices, dtype=float)
    for axis in range(3):
        for corner in range(3):
            out[:, axis] += np.bincount(
                triangles[:, corner], weights=n[:, axis], minlength=len(vertices)
            )
    return out / np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-12)


def smooth_target(vertices, quads, iterations=12):
    a, _ = adjacency(quads, len(vertices))
    v = vertices.copy()
    for _ in range(iterations):
        v += 0.5 * (a @ v - v)
        v -= 0.53 * (a @ v - v)
    return v


def target_surface(vertices, quads=None, iterations=12, normals=None):
    if normals is not None:
        return vertices.copy(), normals.copy()
    target = smooth_target(vertices, quads, iterations)
    triangles = np.concatenate([quads[:, [0, 1, 2]], quads[:, [0, 2, 3]]])
    return target, vertex_normals(target, triangles)


def gaussian_brush(rest, sigma):
    _, chosen = np.unique(
        np.floor(rest / (sigma * 0.8)).astype(np.int64), axis=0, return_index=True
    )
    centers = rest[chosen]
    d = cKDTree(rest).sparse_distance_matrix(
        cKDTree(centers), 3 * sigma, output_type="coo_matrix"
    )
    weights = np.maximum(np.exp(-0.5 * (d.data / sigma) ** 2) - np.exp(-4.5), 0)
    w = coo_matrix((weights, (d.row, d.col)), shape=d.shape).tocsr()
    return diags(1 / np.maximum(np.asarray(w.sum(1)).ravel(), 1e-12)) @ w


def closest_compatible(points, normals, target, target_normals, tree, max_distance):
    distances, ids = tree.query(points, k=min(12, len(target)), workers=-1)
    dots = np.einsum("nc,nkc->nk", normals, target_normals[ids])
    scores = distances + max_distance * (dots < 0.25)
    best = scores.argmin(1)
    chosen = ids[np.arange(len(points)), best]
    valid = (distances[np.arange(len(points)), best] < max_distance) & (
        dots[np.arange(len(points)), best] > 0.25
    )
    return target[chosen], target_normals[chosen], valid


def signed_areas(vertices, triangles, normals):
    p = vertices[triangles]
    return np.einsum(
        "ij,ij->i", np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), normals
    )


def landmark_weights(anchors, budgets=None):
    """Keep each semantic group's total pull independent of its sampling density."""
    weights = np.asarray([a.get("weight", 1) for a in anchors], float)
    if not np.isfinite(weights).all() or (weights <= 0).any():
        raise ValueError("Invalid landmark weights")
    if budgets is not None:
        groups = np.asarray([a.get("group", "ungrouped") for a in anchors])
        for group in np.unique(groups):
            budget = budgets.get(str(group))
            if budget is None or not np.isfinite(budget) or budget <= 0:
                raise ValueError(f"Missing or invalid landmark budget: {group}")
            selected = groups == group
            weights[selected] *= budget / weights[selected].sum()
    return weights


def fit_brush(
    template,
    quads,
    target,
    target_quads,
    settings,
    guard=None,
    observe=None,
    target_normals=None,
):
    """Return registered vertices, exact similarity and auditable stage metrics.

    Landmark indices/targets, exterior mask and protected regions are task inputs.
    Fine wrinkles are suppressed on the fitting target, never on the source used for baking.
    """
    anchors = settings["landmarks"]
    ids = np.array([x["vertex_index"] for x in anchors], int)
    goals = np.array([x["target"] for x in anchors], float)
    weights = landmark_weights(anchors, settings.get("landmark_group_budgets"))
    strength = settings.get("landmark_strength", 25.0)
    huber_fraction = settings.get("landmark_huber_fraction", 0.0)
    if (
        not np.isfinite(strength)
        or strength <= 0
        or not np.isfinite(huber_fraction)
        or huber_fraction < 0
    ):
        raise ValueError("Invalid landmark strength or robust distance")
    linear, offset = similarity(template[ids], goals, weights)
    rest = np.einsum("ij,kj->ik", template, linear) + offset
    v = rest.copy()
    _, edges = adjacency(quads, len(v))
    tri = np.concatenate([quads[:, [0, 1, 2]], quads[:, [0, 2, 3]]])
    target, tn = target_surface(
        target,
        target_quads,
        settings.get("target_smooth_iterations", 12),
        target_normals,
    )
    if "target_fit_indices" in settings:
        target_ids = np.asarray(settings["target_fit_indices"], int)
        target = target[target_ids]
        tn = tn[target_ids]
    tree = cKDTree(target)
    extent = np.ptp(target, axis=0).max()
    edge_length = np.median(
        np.linalg.norm(rest[edges[:, 0]] - rest[edges[:, 1]], axis=1)
    )
    mask = np.zeros(len(v))
    mask[np.asarray(settings["fit_indices"], int)] = 1
    movement = np.ones(len(v))
    if "mobility" in settings:
        movement *= np.asarray(settings["mobility"])
    history = []
    for stage in settings.get(
        "brush_stages",
        [
            {"sigma_edges": 12, "iterations": 30},
            {"sigma_edges": 7, "iterations": 30},
            {"sigma_edges": 4, "iterations": 25},
        ],
    ):
        for iteration in range(stage["iterations"]):
            w = gaussian_brush(v, edge_length * stage["sigma_edges"])
            anchor_residual = goals - v[ids]
            effective = weights * strength
            if huber_fraction:
                effective = effective * np.minimum(
                    1,
                    extent
                    * huber_fraction
                    / np.maximum(np.linalg.norm(anchor_residual, axis=1), 1e-12),
                )
            landmark_mask = np.zeros(len(v))
            np.add.at(landmark_mask, ids, effective)
            denom = np.maximum(w.T @ (mask + landmark_mask), 1e-6)
            vn = vertex_normals(v, tri)
            hit, hn, valid = closest_compatible(v, vn, target, tn, tree, extent * 0.18)
            residual = hit - v
            plane = np.sum(residual * hn, axis=1)[:, None] * hn
            attraction = (0.4 * residual + 0.6 * plane) * (mask * valid)[:, None]
            np.add.at(attraction, ids, anchor_residual * effective[:, None])
            step = w @ ((w.T @ attraction) / denom[:, None])
            # The velocity field is spatially smooth, including across close inner/outer surfaces.
            step *= movement[:, None]
            length = np.linalg.norm(step, axis=1)
            step *= np.minimum(1, extent * 0.012 / np.maximum(length, 1e-12))[:, None]
            # Bound velocity gradients across topological neighbors AND nearby sheets.
            # This limits each flow step before geometry can fold or cross itself.
            dd, nn = cKDTree(v).query(v, k=7, workers=-1)
            dif = step[:, None, :] - step[nn[:, 1:]]
            ratio = np.linalg.norm(dif, axis=2) / np.maximum(dd[:, 1:], extent * 1e-7)
            factor = min(0.7, 0.22 / max(float(ratio.max()), 1e-8))
            p = v[tri]
            normal = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
            area = np.linalg.norm(normal, axis=1)
            normal /= np.maximum(area[:, None], 1e-12)
            for _ in range(12):
                candidate = v + factor * step
                if np.all(signed_areas(candidate, tri, normal) > area * 0.3) and (
                    guard is None or guard(candidate)
                ):
                    break
                factor *= 0.5
            else:
                break
            v = candidate
            if observe is not None and (
                iteration % 10 == 9 or iteration == stage["iterations"] - 1
            ):
                observe(v.copy(), stage["sigma_edges"], iteration + 1)
            if np.max(np.linalg.norm(factor * step, axis=1)) < extent * 1e-5:
                break
        distance = tree.query(v[mask > 0])[0]
        history.append(
            dict(
                sigma_edges=stage["sigma_edges"],
                iterations=iteration + 1,
                surface_rms=float(np.sqrt(np.mean(distance**2))),
                surface_p95=float(np.percentile(distance, 95)),
                landmark_rms=float(
                    np.sqrt(np.mean(np.sum((v[ids] - goals) ** 2, axis=1)))
                ),
                last_step_factor=factor,
            )
        )
        print("BRUSH_STAGE", history[-1], flush=True)
    return v, linear, offset, rest, target, history
