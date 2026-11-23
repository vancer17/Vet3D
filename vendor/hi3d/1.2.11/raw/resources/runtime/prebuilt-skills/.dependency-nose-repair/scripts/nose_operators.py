"""Local mesh operators. All coordinates are caller-supplied; no model assets."""

import numpy as np
import trimesh
from scipy.sparse import coo_matrix, diags
from scipy.sparse.linalg import spsolve


def loops(f):
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    e = np.sort(e, axis=1)
    e, c = np.unique(e, axis=0, return_counts=True)
    edges = e[c == 1]
    adj = {}
    for a, b in edges:
        adj.setdefault(int(a), []).append(int(b))
        adj.setdefault(int(b), []).append(int(a))
    if any(len(v) != 2 for v in adj.values()):
        raise ValueError("Cut boundary is not a collection of loops")
    result = []
    unseen = set(adj)
    while unseen:
        start = min(unseen)
        a = start
        prev = -1
        order = []
        while a in unseen:
            order.append(a)
            unseen.remove(a)
            nn = adj[a]
            prev, a = a, nn[0] if nn[0] != prev else nn[1]
        if a != start:
            raise ValueError("Open boundary")
        result.append(np.asarray(order))
    return sorted(result, key=len, reverse=True)


def rho(v, c, r):
    return np.sqrt(np.sum(((v[:, :2] - c) / r) ** 2, axis=1))


def order_loop(ids, v, c):
    # Preserve topology even where a noisy boundary doubles back in projection.
    p = v[ids, :2] - c
    if np.sum(p[:, 0] * np.roll(p[:, 1], -1) - p[:, 1] * np.roll(p[:, 0], -1)) < 0:
        ids = ids[::-1]
    ang = np.mod(np.arctan2(v[ids, 1] - c[1], v[ids, 0] - c[0]), 2 * np.pi)
    return np.roll(ids, -int(np.argmin(ang)))


def monotonic_angles(a):
    # Pool-adjacent-violators with strictly positive angular separation.
    eps = 1e-5
    y = a - np.arange(len(a)) * eps
    blocks = []
    for i, x in enumerate(y):
        blocks.append([i, i + 1, float(x), 1])
        while len(blocks) > 1 and blocks[-2][2] > blocks[-1][2]:
            b = blocks.pop()
            aa = blocks.pop()
            n = aa[3] + b[3]
            blocks.append([aa[0], b[1], (aa[2] * aa[3] + b[2] * b[3]) / n, n])
    out = np.empty(len(a))
    for start, end, x, n in blocks:
        out[start:end] = x
    return out + np.arange(len(a)) * eps


def gray_mesh(v, f, name):
    m = trimesh.Trimesh(vertices=v, faces=f, process=False)
    m.visual = trimesh.visual.TextureVisuals(
        material=trimesh.visual.material.PBRMaterial(
            name=name,
            baseColorFactor=[145, 145, 145, 255],
            metallicFactor=0,
            roughnessFactor=0.82,
        )
    )
    return m


def poisson_reference(v, f, unknown, reference):
    """Integrate a coherent blended height gradient; solve boundary discrepancy."""
    if len(unknown) == 0:
        return dict(unknown_vertices=0, boundary_correction_max=0.0)
    mask = np.zeros(len(v), bool)
    mask[unknown] = True
    ff = f[mask[f].any(1)]
    ids, inv = np.unique(ff, return_inverse=True)
    lf = inv.reshape(-1, 3)
    lv = v[ids]
    u = np.where(mask[ids])[0]
    fixed = np.where(~mask[ids])[0]
    edges = np.unique(
        np.sort(np.concatenate([lf[:, [0, 1]], lf[:, [1, 2]], lf[:, [2, 0]]]), axis=1),
        axis=0,
    )
    a, b = edges.T
    w = 1 / np.maximum(np.linalg.norm(lv[a, :2] - lv[b, :2], axis=1), 0.0001)
    A = coo_matrix(
        (np.r_[w, w], (np.r_[a, b], np.r_[b, a])), shape=(len(ids), len(ids))
    ).tocsr()
    L = diags(np.asarray(A.sum(1)).ravel()) - A
    from scipy.sparse.csgraph import connected_components

    count, labels = connected_components(A, directed=False)
    if set(labels[u]) - set(labels[fixed]):
        raise ValueError("Every Poisson component must have a fixed Dirichlet boundary")
    h = reference(lv)
    delta_fixed = lv[fixed, 2] - h[fixed]
    delta = spsolve(L[u][:, u], -L[u][:, fixed] @ delta_fixed)
    if not np.isfinite(delta).all():
        raise ValueError("Nonfinite Poisson solution")
    v[ids[u], 2] = h[u] + delta
    return dict(
        unknown_vertices=len(u),
        boundary_correction_max=float(abs(delta).max()),
        method="Poisson integration of blended surface-height gradient with exact Dirichlet anatomical/source boundaries",
    )


def regularize_band_xy(v, f, unknown):
    """Unfold dense, formerly multi-layer boundary triangles in the seam chart."""
    mask = np.zeros(len(v), bool)
    mask[unknown] = True
    ff = f[mask[f].any(1)]
    ids, inv = np.unique(ff, return_inverse=True)
    lf = inv.reshape(-1, 3)
    p = v[ids, :2].copy()
    u = np.where(mask[ids])[0]
    e = np.unique(
        np.sort(np.concatenate([lf[:, [0, 1]], lf[:, [1, 2]], lf[:, [2, 0]]]), axis=1),
        axis=0,
    )
    a, b = e.T
    A = coo_matrix(
        (np.ones(2 * len(e)), (np.r_[a, b], np.r_[b, a])), shape=(len(ids), len(ids))
    ).tocsr()
    A = diags(1 / np.maximum(np.asarray(A.sum(1)).ravel(), 1)) @ A
    old = p[u].copy()
    for _ in range(70):
        p[u] = 0.5 * p[u] + 0.5 * (A @ p)[u]
    v[ids[u], :2] = p[u]
    return dict(
        vertices=len(u), max_xy_shift=float(np.linalg.norm(p[u] - old, axis=1).max())
    )


def triangulate_annulus(vertices, outer, inner, interior, center):
    """Triangulate an XY annulus preserving the actual source/donor edge chains.

    Boundaries must be simple, nested, disjoint loops. `center` is a point inside
    the inner hole, not a coordinate used to reorder the boundary vertices.
    Returns global vertex-index triangles with +Z winding; does not modify inputs.
    """
    import triangle

    ids = np.r_[outer, inner, interior]
    n0, n1 = len(outer), len(inner)
    s0 = np.c_[np.arange(n0), np.roll(np.arange(n0), -1)]
    s1 = np.c_[np.arange(n1), np.roll(np.arange(n1), -1)] + n0
    data = triangle.triangulate(
        dict(
            vertices=vertices[ids, :2],
            segments=np.vstack([s0, s1]),
            holes=[list(center)],
        ),
        "pYQ",
    )
    if len(data["vertices"]) != len(ids) or "triangles" not in data:
        raise ValueError("Invalid intersecting/empty annulus")
    faces = ids[data["triangles"]]
    t = vertices[faces]
    negative = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])[:, 2] < 0
    faces[negative] = faces[negative][:, [0, 2, 1]]
    return faces
