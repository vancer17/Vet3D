"""Concavity-weighted binary face cut and shared threshold-independent graph preparation."""
import time
from types import SimpleNamespace
import numpy as np
from scipy.sparse import csr_matrix, coo_matrix, diags
from scipy.sparse.csgraph import maximum_flow, breadth_first_order, connected_components, dijkstra


def tick(stage):
    print(stage, flush=True)


def prepare_graph(P, Fo, *, kappa0=130., floor=.02, hidden_threshold=.15):
    """Prepare adjacency, weights and shell rules without choosing a cut."""
    if not all(np.isfinite(x) for x in (kappa0, floor, hidden_threshold)):
        raise ValueError("Graph parameters must be finite")
    if kappa0 <= 0 or not 0 < floor <= 1 or not 0 <= hidden_threshold <= 1:
        raise ValueError("Invalid graph parameters")
    V, inv = np.unique(P, axis=0, return_inverse=True); inv = inv.ravel(); V = V.astype(np.float64)
    F = inv[Fo]; nF = len(F)
    E = np.sort(np.vstack([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), axis=1); fid = np.tile(np.arange(nF), 3)
    key = E[:, 0] * len(V) + E[:, 1]; o = np.argsort(key, kind='stable'); key = key[o]
    cnt = np.unique(key, return_counts=True)[1]; hist = np.bincount(cnt)
    if (cnt != 2).any():
        print('edges by number of incident triangles:', {k: int(v) for k, v in enumerate(hist) if v})
    if np.any(cnt > 2): raise ValueError('Nonmanifold welded edges are unsupported')
    same = key[1:] == key[:-1]; fs, Es = fid[o], E[o]
    f0, f1, Eu = fs[:-1][same], fs[1:][same], Es[:-1][same]
    tri = V[F]; fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); area = 0.5 * np.linalg.norm(fn, axis=1)
    if not np.isfinite(area).all() or np.any(area <= 0):
        raise ValueError("Degenerate or nonfinite triangles are unsupported")
    Nf = fn / (2 * area[:, None] + 1e-30); cen = tri.mean(1)
    elen = np.linalg.norm(V[Eu[:, 0]] - V[Eu[:, 1]], axis=1)
    diag = np.linalg.norm(V.max(0) - V.min(0))

    tick('weld and adjacency')
    # ---------- smoothness term: concavity across each edge, measured with slightly smoothed normals ----------
    A = coo_matrix((np.ones(2 * len(f0)), (np.r_[f0, f1], np.r_[f1, f0])), shape=(nF, nF)).tocsr()
    Pavg = (A + diags(np.ones(nF))) / 4.0
    Ns = Nf.copy()
    for _ in range(6): Ns = Pavg @ Ns
    Ns /= np.linalg.norm(Ns, axis=1, keepdims=True) + 1e-30
    dc = cen[f1] - cen[f0]; dcl = np.linalg.norm(dc, axis=1) + 1e-12
    kappa = ((Ns[f1] - Ns[f0]) * dc).sum(1) / dcl ** 2                       # < 0 where the surface is concave across the edge
    w = (elen / elen.mean()) * (floor + (1 - floor) * np.exp(-np.maximum(-kappa, 0) / (kappa0 / diag))) if len(elen) else elen

    nmc, mc = connected_components(A, directed=False)
    mainc = int(np.bincount(mc, weights=area).argmax()); inmain = mc == mainc
    shells = []
    from scipy.spatial import cKDTree
    if nmc > 1:
        Tm = tri[inmain]; v0m = Tm[:, 0]; e1 = Tm[:, 1] - Tm[:, 0]; e2 = Tm[:, 2] - Tm[:, 0]
        k = np.arange(48) + 0.5; ph = np.arccos(1 - 2 * k / 48); th = np.pi * (1 + 5 ** 0.5) * k
        dirs = np.stack([np.cos(th) * np.sin(ph), np.sin(th) * np.sin(ph), np.cos(ph)], 1)
        cm = cen[inmain]; rad = np.sqrt(((Tm - cm[:, None]) ** 2).sum(2).max(1))       # bounding radius of every main triangle
        def escape_fraction(p):
            """fraction of rays leaving p that never meet the main surface; a bounding-sphere test keeps only the
            triangles near each ray, the survivors go through Moller-Trumbore"""
            wv = cm - p; w2 = (wv * wv).sum(1); esc = 0
            for d in dirs:
                along = wv @ d
                k = np.flatnonzero((w2 - along * along <= rad * rad) & (along > -rad))
                if len(k) == 0: esc += 1; continue
                E1, E2 = e1[k], e2[k]; sv = p - v0m[k]
                h = np.cross(d, E2); a = (E1 * h).sum(1); ok = np.abs(a) > 1e-30; fi = np.where(ok, 1.0 / np.where(ok, a, 1.0), 0.0)
                qv = np.cross(sv, E1); u = fi * (sv * h).sum(1); v = fi * (qv @ d); t = fi * (E2 * qv).sum(1)
                esc += not (ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-9)).any()
            return esc / len(dirs)
        main_ids = np.flatnonzero(inmain); tree = cKDTree(cen[inmain])
        for c in range(nmc):
            if c == mainc: continue
            m = mc == c; vs = V[np.unique(F[m])]; ax = np.argmax(vs.max(0) - vs.min(0))
            esc = max(escape_fraction(o) for o in (cen[m].mean(0), vs[vs[:, ax].argmin()], vs[vs[:, ax].argmax()]))
            hidden = bool(esc < hidden_threshold)
            shells.append({"component": c, "hidden": hidden, "faces": np.flatnonzero(m).tolist(),
                           "nearest": main_ids[tree.query(cen[m])[1]].tolist() if hidden else []})
    return dict(a=f0, b=f1, distance=dcl, weight=15*w, area=area,
                component=mc, mainComponent=mainc, shells=shells, diagonal=float(diag))


def solve(P, Fo, lab0, *, black_band=.12, white_band=.005, kappa0=130., floor=.02, hidden_threshold=.15):
    """Return 0/1 labels without deleting or modifying any source triangle."""
    args = SimpleNamespace(black_band=black_band, white_band=white_band, kappa0=kappa0,
                           floor=floor, hidden_threshold=hidden_threshold)
    if not all(np.isfinite(x) for x in (black_band, white_band, kappa0, floor, hidden_threshold)):
        raise ValueError("Cut parameters must be finite")
    if not 0 < white_band <= black_band or kappa0 <= 0 or not 0 < floor <= 1 or not 0 <= hidden_threshold <= 1:
        raise ValueError("Invalid cut parameters")
    if len(lab0) != len(Fo) or set(np.unique(lab0)) != {0, 1}:
        raise ValueError("Initial labels must contain both classes")
    g = prepare_graph(P, Fo, kappa0=kappa0, floor=floor, hidden_threshold=hidden_threshold)
    f0, f1, dcl, area = (g[k] for k in ("a", "b", "distance", "area"))
    diag = g["diagonal"]; nF = len(Fo)
    if not len(f0): return lab0.copy(), {"free_triangles": 0, "cut_value": 0, "flow_value": 0}
    # ---------- data term: the existing labels ----------
    bnd = lab0[f0] != lab0[f1]; src = np.unique(np.r_[f0[bnd], f1[bnd]])
    if not len(src):
        return lab0.copy(), {"free_triangles": 0, "cut_value": 0, "flow_value": 0}
    Gd = csr_matrix((np.r_[dcl, dcl], (np.r_[f0, f1], np.r_[f1, f0])), shape=(nF, nF))
    band_b, band_w = args.black_band * diag, args.white_band * diag
    dist = dijkstra(Gd, directed=False, indices=src, min_only=True, limit=band_b * 1.01)
    seed_w = (lab0 == 1) & ~(dist <= band_w)
    seed_b = (lab0 == 0) & ~(dist <= band_b)
    free = ~(seed_w | seed_b)
    an = area / area.mean()
    unary = np.where(lab0 == 1, 1.0, -1.0) * np.where(free, np.minimum(dist, band_b) / diag, 0) * an   # weak preference for the old label
    print('free triangles: %d (black band %.4f, white band %.4f)' % (free.sum(), band_b, band_w))

    tick('distances and seeds')
    # ---------- s-t minimum cut ----------
    SCALE = 200
    idx = -np.ones(nF, np.int64); nfree = int(free.sum()); idx[free] = np.arange(nfree); S, Tn = nfree, nfree + 1
    cs = np.maximum(unary, 0)[free].copy(); ct = np.maximum(-unary, 0)[free].copy(); wl = g['weight']
    for fa, fb in ((f0, f1), (f1, f0)):
        m = free[fa] & seed_w[fb]; np.add.at(cs, idx[fa[m]], wl[m])
        m = free[fa] & seed_b[fb]; np.add.at(ct, idx[fa[m]], wl[m])
    both = free[f0] & free[f1]; i, j = idx[f0[both]], idx[f1[both]]
    q = lambda x: np.minimum(np.maximum(np.round(x * SCALE), 0), 2 ** 30).astype(np.int64)
    qw = np.maximum(q(wl[both]), 1)
    rows = np.r_[i, j, np.full(nfree, S), np.arange(nfree)]; cols = np.r_[j, i, np.arange(nfree), np.full(nfree, Tn)]
    caps = np.r_[qw, qw, q(cs), q(ct)].astype(np.int32); keep = caps > 0
    G = csr_matrix((caps[keep], (rows[keep], cols[keep])), shape=(nfree + 2, nfree + 2))
    t0 = time.time(); res = maximum_flow(G, S, Tn, method='dinic')
    resid = G - res.flow; resid.data = np.maximum(resid.data, 0); resid.eliminate_zeros()
    reach = np.zeros(nfree + 2, bool); reach[breadth_first_order(resid, S, directed=True, return_predecessors=False)] = True
    r = reach[:nfree]
    cutval = q(cs)[~r].sum() + q(ct)[r].sum() + qw[r[i] != r[j]].sum()
    print('max flow %d, capacity of returned cut %d (%s), %.1fs' % (res.flow_value, cutval, 'optimal' if cutval == res.flow_value else 'MISMATCH', time.time() - t0))
    lab = np.zeros(nF, np.int64); lab[seed_w] = 1; lab[free] = r

    if cutval != res.flow_value: raise ValueError('Maxflow and cut capacity disagree')
    tick('minimum cut')
    mc = g['component']; mainc = g['mainComponent']; inmain = mc == mainc
    for _ in range(4):
        changed = 0
        for L in (0, 1):
            m = (lab[f0] == L) & (lab[f1] == L) & inmain[f0]
            nc, cc = connected_components(csr_matrix((np.ones(m.sum()), (f0[m], f1[m])), shape=(nF, nF)), directed=False)
            sel = (lab == L) & inmain
            if not sel.any(): continue
            flip = sel & (cc != np.bincount(cc[sel], weights=area[sel], minlength=nc).argmax())
            changed += flip.sum(); lab[flip] = 1 - L
        if changed == 0: break
    tick('connectivity clean-up')
    for shell in g["shells"]:
        faces = np.asarray(shell["faces"])
        if shell["hidden"]:
            label = int(lab[np.asarray(shell["nearest"])].mean() > .5)
        else:
            label = int((lab0[faces]*area[faces]).sum() > .5*area[faces].sum())
        lab[faces] = label
    tick("floating shells (ray test)")
    return lab, {"free_triangles": nfree, "cut_value": int(cutval), "flow_value": int(res.flow_value)}
