"""Frozen-landmark ear initialization and bounded shared-volume surface fitting.

Pure NumPy/SciPy operations. Coordinates use X horizontal, Y depth, Z up in
one common source frame. Thresholds are fractions of target maximum extent.
"""

import itertools
import numpy as np
from scipy.spatial import cKDTree, ConvexHull
from scipy.sparse import coo_matrix, diags, eye
from scipy.sparse.linalg import spsolve
from brush import adjacency, vertex_normals
from surface import smooth_samples


def validate_inputs(
    original, face, records, regions, target_vertices, target_normals, protected_indices
):
    vertices = np.asarray(original["vertices"])
    for value in (vertices, original["rest"], face, target_vertices, target_normals):
        a = np.asarray(value)
        if a.ndim != 2 or a.shape[1] != 3 or not np.isfinite(a).all():
            raise ValueError("Expected finite N x 3 coordinates/normals")
    if (
        vertices.shape != np.asarray(face).shape
        or vertices.shape != np.asarray(original["rest"]).shape
    ):
        raise ValueError("Registered/rest/face vertex counts differ")
    if (
        len(target_vertices) < 24
        or np.asarray(target_normals).shape != np.asarray(target_vertices).shape
        or np.ptp(target_vertices, axis=0).max() <= 0
    ):
        raise ValueError("Invalid target surface")
    q = np.asarray(original["quads"])
    if (
        q.ndim != 2
        or q.shape[1] != 4
        or q.dtype.kind not in "iu"
        or q.min() < 0
        or q.max() >= len(vertices)
    ):
        raise ValueError("Expected indexed MetaHuman quads")
    if [e["name"] for e in regions["ear_regions"]] != ["right", "left"]:
        raise ValueError("Ear regions must be ordered right, left")
    all_ids = list(protected_indices)
    for ear in regions["ear_regions"]:
        all_ids.extend(ear["core_indices"])
    if not all_ids or any(
        not isinstance(i, (int, np.integer)) or i < 0 or i >= len(vertices)
        for i in all_ids
    ):
        raise ValueError("Invalid region or protected vertex index")
    core_sets = [set(e["core_indices"]) for e in regions["ear_regions"]]
    if core_sets[0] & core_sets[1]:
        raise ValueError("Ear cores overlap")
    seen = set()
    for r in records:
        ids = np.asarray(r["triangle"])
        bc = np.asarray(r["barycentric"], float)
        if r["id"] in seen or r["ear"] not in ("left", "right"):
            raise ValueError("Duplicate landmark ID or invalid ear")
        seen.add(r["id"])
        if (
            ids.shape != (3,)
            or ids.dtype.kind not in "iu"
            or (ids < 0).any()
            or (ids >= len(vertices)).any()
        ):
            raise ValueError("Invalid barycentric triangle")
        if (
            bc.shape != (3,)
            or not np.isfinite(bc).all()
            or (bc < 0).any()
            or not np.isclose(bc.sum(), 1)
        ):
            raise ValueError("Invalid barycentric weights")
        if (
            np.asarray(r["target"]).shape != (3,)
            or not np.isfinite(r["target"]).all()
            or not np.isfinite(r.get("weight", 1))
            or r.get("weight", 1) <= 0
        ):
            raise ValueError("Invalid target landmark/confidence")


def initialize(
    original, face, records, regions, target_vertices, target_normals, protected_indices
):
    validate_inputs(
        original,
        face,
        records,
        regions,
        target_vertices,
        target_normals,
        protected_indices,
    )
    face = np.asarray(face, dtype=float)
    q = original["quads"]
    n = len(face)
    adjacency_matrix, edges = adjacency(q, n)
    degrees = np.bincount(edges.ravel(), minlength=n)
    lap = diags(degrees) @ (eye(n, format="csr") - adjacency_matrix)
    extent = np.ptp(target_vertices, axis=0).max()
    t, tn = smooth_samples(target_vertices, target_normals, 0.0015)
    energy = (lap.T @ lap).tocsr()
    v = face.copy()
    active = np.zeros(n, bool)
    core_label = np.zeros(n, int)
    reports = []
    pools = {}
    # Keep eye/lip anchors and their two-ring neighbourhood fixed.
    protected = np.zeros(n, bool)
    protected[protected_indices] = True
    for _ in range(2):
        protected[edges[protected[edges].any(1)].ravel()] = True
    for j, ear in enumerate(regions["ear_regions"], 1):
        ids = np.array(ear["core_indices"])
        core_label[ids] = j
        rr = [r for r in records if r["ear"] == ear["name"]]
        if len(rr) < 4:
            raise ValueError("At least four ear landmarks per side are required")
        idx = np.array([r["triangle"] for r in rr])
        bc = np.array([r["barycentric"] for r in rr])
        goals = np.array([r["target"] for r in rr])
        src = np.einsum("ij,ijk->ik", bc, original["rest"][idx])
        if (
            np.linalg.matrix_rank(src - src.mean(0)) < 2
            or np.linalg.matrix_rank(goals[:, [0, 2]] - goals[:, [0, 2]].mean(0)) < 2
        ):
            raise ValueError("Degenerate ear landmark configuration")
        if protected[ids].any():
            raise ValueError("Ear core overlaps protected anchors")
        base_weights = np.array([r.get("weight", 1.0) for r in rr])
        weights = base_weights.copy()
        # The depth direction is observable in actual ray hits; a weak identity prior
        # stabilizes nearly planar ears without forcing uniform scale.
        for _ in range(6):
            s0 = np.average(src, axis=0, weights=weights)
            g0 = np.average(goals, axis=0, weights=weights)
            a = src - s0
            b = goals - g0
            cov = a.T @ (a * weights[:, None])
            ridge = 0.015 * np.trace(cov)
            linear = np.linalg.solve(
                cov + ridge * np.eye(3),
                a.T @ (b * weights[:, None]) + ridge * np.eye(3),
            )
            u, s, vt = np.linalg.svd(linear)
            if np.linalg.det(u @ vt) < 0:
                u[:, -1] *= -1
            linear = u @ np.diag(np.clip(s, 0.5, 2.0)) @ vt
            error = np.linalg.norm(
                np.einsum("ij,jk->ik", a, linear) + g0 - goals, axis=1
            )
            weights = base_weights * np.minimum(
                1, 0.015 * extent / np.maximum(error, 1e-12)
            )
        core_goal = np.einsum("ij,jk->ik", original["rest"][ids] - s0, linear) + g0
        affected = np.zeros(n, bool)
        affected[ids] = True
        for _ in range(18):
            affected[edges[affected[edges].any(1)].ravel()] = True
        affected[protected] = False
        active |= affected
        unknown = np.setdiff1d(np.flatnonzero(affected), ids)
        fixed = np.setdiff1d(np.arange(n), unknown)
        delta = np.zeros_like(v)
        delta[ids] = core_goal - face[ids]
        delta[unknown] = spsolve(
            (energy[unknown][:, unknown] + diags(np.full(len(unknown), 0.015))).tocsc(),
            -(energy[unknown][:, fixed] @ delta[fixed]),
        )
        v += delta
        # Anatomical points define a source-space search domain independently of
        # the old template size. Its generous hull padding includes the outer rim.
        hull = ConvexHull(goals[:, [0, 2]])
        eq = hull.equations
        plane = np.einsum("ij,kj->ik", t[:, [0, 2]], eq[:, :2]) + eq[:, 2]
        mask = (
            (plane.max(1) < 0.028 * extent)
            & (t[:, 1] > goals[:, 1].min() - 0.035 * extent)
            & (t[:, 1] < goals[:, 1].max() + 0.035 * extent)
        )
        pools[j] = np.flatnonzero(mask)
        if len(pools[j]) < 24 or len(ids) < 12:
            raise ValueError("Insufficient ear surface samples")
        reports.append(
            {
                "ear": ear["name"],
                "landmarks": len(rr),
                "affine_singular_values": np.linalg.svd(
                    linear, compute_uv=False
                ).tolist(),
                "source_pool": len(pools[j]),
            }
        )
    return dict(
        original=original,
        face=face,
        records=records,
        v=v,
        active=active,
        pools=pools,
        t=t,
        tn=tn,
        reports=reports,
        core_label=core_label,
        protected=protected,
    )


def grid_matrix(points, lo, spacing, shape):
    coords = (points - lo) / spacing
    cell = np.floor(coords).astype(int)
    valid = np.all((cell >= 0) & (cell < np.array(shape) - 1), axis=1)
    ids = np.flatnonzero(valid)
    f = coords[ids] - cell[ids]
    rows = []
    cols = []
    values = []
    for bits in itertools.product([0, 1], repeat=3):
        xyz = cell[ids] + bits
        index = np.ravel_multi_index(xyz.T, shape)
        weight = np.prod(np.where(np.array(bits), f, 1 - f), axis=1)
        rows.extend(ids)
        cols.extend(index)
        values.extend(weight)
    return coo_matrix(
        (values, (rows, cols)), shape=(len(points), int(np.prod(shape)))
    ).tocsr()


def grid_lap(shape):
    ijk = np.indices(shape).reshape(3, -1).T
    n = len(ijk)
    grid = np.arange(n).reshape(shape)
    edges = []
    for axis in range(3):
        a = [slice(None)] * 3
        b = a.copy()
        a[axis] = slice(None, -1)
        b[axis] = slice(1, None)
        edges.append(np.column_stack([grid[tuple(a)].ravel(), grid[tuple(b)].ravel()]))
    e = np.concatenate(edges)
    rows = np.repeat(np.arange(len(e)), 2)
    D = coo_matrix(
        (np.tile([1.0, -1.0], len(e)), (rows, e.ravel())), shape=(len(e), n)
    ).tocsr()
    boundary = np.any((ijk == 0) | (ijk == np.array(shape) - 1), axis=1)
    return D.T @ D, boundary


def deform(data):
    old = data["original"]
    v = data["v"].copy()
    init = v.copy()
    face = data["face"]
    records = data["records"]
    t = data["t"]
    tn = data["tn"]
    labels = data["core_label"]
    pools = data["pools"]
    extent = np.ptp(t, axis=0).max()
    q = old["quads"]
    tri = np.concatenate([q[:, [0, 1, 2]], q[:, [0, 2, 3]]])
    n = len(v)
    cols = np.array([r["triangle"] for r in records]).ravel()
    vals = np.array([r["barycentric"] for r in records]).ravel()
    C = coo_matrix(
        (vals, (np.repeat(np.arange(len(records)), 3), cols)), shape=(len(records), n)
    ).tocsr()
    goals = np.array([r["target"] for r in records])
    lw = np.array([r.get("weight", 1.0) for r in records])
    trees = {j: cKDTree(t[pools[j]]) for j in [1, 2]}
    fulltree = cKDTree(t)
    history = []
    for side, j in [("right", 1), ("left", 2)]:
        ids = np.flatnonzero(labels == j)
        lo = v[ids].min(0) - extent * 0.07
        hi = v[ids].max(0) + extent * 0.07
        for spacing in [0.04 * extent, 0.025 * extent]:
            shape = tuple(np.ceil((hi - lo) / spacing).astype(int) + 1)
            lap, boundary = grid_lap(shape)
            # Boundary controls are eliminated exactly, keeping the deformation
            # continuously zero outside the ear/root volume.
            free = np.flatnonzero(~boundary)
            reg = (lap.T @ lap)[free][:, free]
            earrows = np.array([r["ear"] == side for r in records])
            Cs = C[earrows]
            gs = goals[earrows]
            ls = lw[earrows]
            for iteration in range(24):
                B = grid_matrix(v, lo, spacing, shape)[:, free]
                affected = np.flatnonzero(np.asarray(B.sum(1)).ravel() > 0)
                vn = vertex_normals(v, tri)
                residual = np.zeros_like(v)
                weight = np.zeros(n)
                for kind in ["core", "root"]:
                    vi = affected[
                        (
                            (labels[affected] == j)
                            if kind == "core"
                            else (labels[affected] == 0)
                        )
                    ]
                    pool = pools[j] if kind == "core" else np.arange(len(t))
                    tree = trees[j] if kind == "core" else fulltree
                    dd, ix = tree.query(v[vi], k=24)
                    dot = np.einsum("ik,ijk->ij", vn[vi], tn[pool[ix]])
                    score = np.where(dot > 0.45, dd, np.inf)
                    best = score.argmin(1)
                    chosen = pool[ix[np.arange(len(vi)), best]]
                    good = score[np.arange(len(vi)), best] < extent * 0.035
                    delta = t[chosen] - v[vi]
                    plane = np.sum(delta * tn[chosen], axis=1)[:, None] * tn[chosen]
                    residual[vi] = 0.35 * delta + 0.65 * plane
                    weight[vi] = good * (1.0 if kind == "core" else 1.5)
                reverse_weight = np.zeros(n)
                reverse_rhs = np.zeros_like(v)
                pool = pools[j]
                dd, ix = cKDTree(v[ids]).query(t[pool], k=12)
                dot = np.einsum("ik,ijk->ij", tn[pool], vn[ids[ix]])
                score = np.where(dot > 0.5, dd, np.inf)
                best = score.argmin(1)
                dist = score[np.arange(len(pool)), best]
                chosen = ids[ix[np.arange(len(pool)), best]]
                good = dist < 0.025 * extent
                rw = 0.35 * len(ids) / len(pool)
                np.add.at(reverse_weight, chosen[good], rw)
                np.add.at(
                    reverse_rhs, chosen[good], rw * (t[pool[good]] - v[chosen[good]])
                )
                CB = Cs @ B
                lr = gs - Cs @ v
                robust = ls * np.minimum(
                    1, 0.012 * extent / np.maximum(np.linalg.norm(lr, axis=1), 1e-12)
                )
                cw = 20.0
                mat = (
                    B.T @ diags(weight + reverse_weight) @ B
                    + cw * CB.T @ diags(robust) @ CB
                    + 2.0 * reg
                    + diags(np.full(len(free), 0.08))
                )
                rhs = B.T @ (weight[:, None] * residual + reverse_rhs) + cw * CB.T @ (
                    robust[:, None] * lr
                )
                coefficients = spsolve(mat.tocsc(), rhs)
                field = np.zeros((int(np.prod(shape)), 3))
                field[free] = coefficients
                grid = field.reshape(*shape, 3)
                # A conservative global Lipschitz bound from every control edge:
                # each trilinear derivative is a convex blend of these edges.
                bound = np.sqrt(
                    sum(
                        np.max(
                            np.linalg.norm(np.diff(grid, axis=ax), axis=-1) / spacing
                        )
                        ** 2
                        for ax in range(3)
                    )
                )
                step = B @ coefficients
                factor = min(
                    1.0,
                    0.25 / max(bound, 1e-12),
                    0.0025 * extent / max(np.linalg.norm(step, axis=1).max(), 1e-12),
                )
                proposal = v + factor * step
                if not np.isfinite(proposal).all():
                    raise ValueError("Non-finite ear deformation")
                if np.any(proposal[data["protected"]] != face[data["protected"]]):
                    raise ValueError(
                        "Ear volume overlaps protected eye/lip neighbourhood"
                    )
                v = proposal
                if iteration % 8 == 0:
                    history.append(
                        {
                            "ear": side,
                            "spacing": spacing,
                            "iteration": iteration,
                            "factor": factor,
                            "lipschitz_bound_after_scaling": bound * factor,
                            "landmark_rms": float(
                                np.sqrt(np.mean(np.sum((Cs @ v - gs) ** 2, axis=1)))
                            ),
                        }
                    )
    report = {
        "ears": data["reports"],
        "history": history,
        "landmark_rms_before": float(
            np.sqrt(np.mean(np.sum((C @ face - goals) ** 2, axis=1)))
        ),
        "landmark_rms_initial": float(
            np.sqrt(np.mean(np.sum((C @ init - goals) ** 2, axis=1)))
        ),
        "landmark_rms_after": float(
            np.sqrt(np.mean(np.sum((C @ v - goals) ** 2, axis=1)))
        ),
    }
    return v, report
