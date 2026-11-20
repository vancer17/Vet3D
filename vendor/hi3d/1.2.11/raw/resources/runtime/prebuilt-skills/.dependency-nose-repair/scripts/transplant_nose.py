"""Excise a configured nose, transplant the fitted donor, solve a Poisson seam."""

import json, sys, time, hashlib
from pathlib import Path
import numpy as np
import trimesh
from scipy.interpolate import RectBivariateSpline
from scipy.ndimage import gaussian_filter, distance_transform_edt

from nose_operators import (
    loops,
    rho,
    order_loop,
    monotonic_angles,
    gray_mesh,
    poisson_reference,
    regularize_band_xy,
    triangulate_annulus,
)


def main(root):
    if (root / "repaired.glb").exists():
        raise FileExistsError("Use a new repair revision")
    start = time.monotonic()
    cfg = json.loads((root / "render_original.json").read_text())
    src = Path(cfg["source"])
    profile = json.loads((root / "profile.json").read_text())
    if hashlib.sha256(src.read_bytes()).hexdigest() != profile["source"]["sha256"]:
        raise ValueError("Source hash mismatch")
    if (
        hashlib.sha256((root / "fit/structural_prior.npz").read_bytes()).hexdigest()
        != profile["donor_sha256"]
    ):
        raise ValueError("Donor hash mismatch")
    scene = trimesh.load(src, process=False, force="scene")
    if len(scene.geometry) != 1:
        raise ValueError(
            "Nose adapter requires a single mesh; prepare an explicit source subset first"
        )
    source = scene.to_geometry()
    v = np.asarray(source.vertices).copy()
    f = np.asarray(source.faces).copy()
    # Merge only coincident UV-split vertices in the local nasal neighborhood.
    local_profile=profile['nose']
    local_radius=rho(v,np.array(local_profile['center']),np.array(local_profile['radii']))
    ids=np.flatnonzero((local_radius<1.35)&(v[:,2]>local_profile['min_z']))
    _,first,inverse=np.unique(v[ids],axis=0,return_index=True,return_inverse=True)
    remap=np.arange(len(v));remap[ids]=ids[first[inverse]]
    f=remap[f]
    np.savez_compressed(root/'local_uv_weld.npz',original_indices=ids,representatives=remap[ids])
    source_v = v.copy()
    fit = np.load(root / "fit/structural_prior.npz")
    tv = fit["vertices"]
    q = fit["quads"]
    tf = np.concatenate([q[:, [0, 1, 2]], q[:, [0, 2, 3]]])
    edited_source = []
    report = dict(
        source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),
        regions=[],
        method="Excise old triangles, transplant fitted anatomy; discrete edge-gradient Poisson with fixed inner/outer boundaries. Not global screened surface reconstruction.",
        units="Original GLB normalized coordinates; physical millimeters not known.",
    )
    # Nose: boundary remains outside alar creases; all template cavity folds inside.
    nose = profile["nose"]
    c = np.array(nose["center"])
    r = np.array(nose["radii"])
    rr = rho(v, c, r)
    remove = (rr[f].min(1) < 1) & (v[f, 2].min(1) > nose["min_z"])
    removed = f[remove]
    ob = loops(removed)
    if len(ob) != 1:
        raise ValueError("Nasal source cut has " + str(len(ob)) + " boundaries")
    outer = order_loop(ob[0], v, c)
    f = f[~remove]
    tr = rho(tv, c, r * 0.75)
    keep = (tr[tf].max(1) < 1) & (tv[tf, 2].min(1) > nose["min_z"])
    nf = tf[keep]
    # The template's upper oral lining can project into this rectangle behind
    # the nose. Retain only the connected skin/cavity patch, not that second part.
    tempmesh = trimesh.Trimesh(vertices=tv, faces=nf, process=False)
    components = trimesh.graph.connected_components(
        tempmesh.face_adjacency, nodes=np.arange(len(nf)), min_len=1
    )
    nf = nf[max(components, key=len)]
    nb = loops(nf)
    if len(nb) != 1:
        raise ValueError("Template nose patch has " + str(len(nb)) + " boundaries")
    used, inv = np.unique(nf, return_inverse=True)
    nf = inv.reshape(-1, 3)
    nv = tv[used].copy()
    inner = np.searchsorted(used, nb[0])
    ni = len(v)
    v = np.vstack([v, nv])
    inner = inner + ni
    nf = nf + ni
    # Smoothly interpolate cross-section positions through the transition; solve z.
    heights = np.load(root / "heightfields.npz")
    for key, path in [
        ("source_sha256", src),
        ("donor_sha256", root / "fit/structural_prior.npz"),
        ("profile_sha256", root / "profile.json"),
    ]:
        if str(heights[key]) != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError("Stale nose heightfield")
    splines = {}
    for key in ["source", "template"]:
        field = heights[key]
        missing = ~np.isfinite(field)
        if missing.all():
            raise ValueError("Empty heightfield")
        if missing.any():
            nearest = distance_transform_edt(
                missing, return_distances=False, return_indices=True
            )
            field = field[tuple(nearest)]
        splines[key] = RectBivariateSpline(
            heights["y"], heights["x"], gaussian_filter(field, 0.65)
        )

    # Expand the donor border outward and move the high-mesh border inward.
    # This avoids stepping past their retained neighboring triangles.
    for border, factor, kind in [(inner, 0.755, "template"), (outer, 0.990, "source")]:
        border = order_loop(border, v, c)
        old = v[border].copy()
        angles = monotonic_angles(
            np.unwrap(np.arctan2((old[:, 1] - c[1]) / r[1], (old[:, 0] - c[0]) / r[0]))
        )
        span=angles[-1]-angles[0]
        if span>=2*np.pi-1e-5:
            angles=angles[0]+(angles-angles[0])*((2*np.pi-1e-4)/span)
        v[border, :2] = c + factor * np.c_[np.cos(angles) * r[0], np.sin(angles) * r[1]]
        v[border, 2] = splines[kind].ev(v[border, 1], v[border, 0])
    edited_source.extend(outer.tolist())
    step = profile["transition_spacing"]
    gx = np.arange(c[0] - r[0], c[0] + r[0], step)
    gy = np.arange(c[1] - r[1], c[1] + r[1], step)
    xy = np.stack(np.meshgrid(gx, gy), axis=-1).reshape(-1, 2)
    rr = rho(np.c_[xy, np.zeros(len(xy))], c, r)
    xy = xy[(rr > 0.775) & (rr < 0.970)]
    new = np.arange(len(v), len(v) + len(xy))
    v = np.vstack([v, np.c_[xy, splines["source"].ev(xy[:, 1], xy[:, 0])]])
    ringf = triangulate_annulus(v, outer, inner, new, c)
    f = np.vstack([f, nf, ringf])

    def nose_reference(p):
        radius = rho(p, c, r)
        t = np.clip((radius - 0.69) / (1.10 - 0.69), 0, 1)
        t = t * t * (3 - 2 * t)
        a = splines["template"].ev(p[:, 1], p[:, 0])
        b = splines["source"].ev(p[:, 1], p[:, 0])
        return a * (1 - t) + b * t

    radius = rho(v, c, r)
    fair_ids = np.where(
        (radius > 0.69) & (radius < 1.10) & (v[:, 2] > nose["band_min_z"])
    )[0]
    fair = poisson_reference(v, f, fair_ids, nose_reference)
    edited_source.extend(fair_ids[fair_ids < len(source_v)].tolist())
    radius = rho(v, c, r)
    par_ids = np.where(
        (radius > 0.68) & (radius < 1.13) & (v[:, 2] > nose["band_min_z"])
    )[0]
    chart = regularize_band_xy(v, f, par_ids)
    fair = poisson_reference(v, f, par_ids, nose_reference)
    edited_source.extend(par_ids[par_ids < len(source_v)].tolist())
    report["regions"].append(
        dict(
            name="nose",
            removed_triangles=len(removed),
            template_triangles=len(nf),
            transition_triangles=len(ringf),
            poisson=fair,
            chart_regularization=chart,
            triangulation="Constrained Delaunay annulus, donor and source boundary edges preserved",
        )
    )
    # No welding/decimation/normal displacement outside the cut. Keep used originals.
    used, inv = np.unique(f, return_inverse=True)
    ff = inv.reshape(-1, 3)
    vv = v[used]
    edited_source = np.unique(edited_source)
    original_ids = used[used < len(source_v)]
    outside = np.setdiff1d(original_ids, edited_source)
    err = np.linalg.norm(v[outside] - source_v[outside], axis=1)
    report.update(
        vertices=len(vv),
        triangles=len(ff),
        retained_original_vertices=len(original_ids),
        boundary_adjusted_vertices=len(np.intersect1d(edited_source, used)),
        unchanged_source_vertices=len(outside),
        outside_change_max=float(err.max()),
        seconds=time.monotonic() - start,
    )
    np.savez_compressed(
        root / "repair_provenance.npz",
        source_vertex_indices=original_ids,
        output_vertex_indices=np.searchsorted(used, original_ids),
        adjusted_source_vertex_indices=np.intersect1d(edited_source, used),
        unchanged_source_vertex_indices=outside,
    )
    mesh = gray_mesh(vv, ff, "Neutral gray geometry")
    output_scene = trimesh.Scene()
    output_scene.add_geometry(
        mesh, geom_name="repaired_skin", node_name="repaired_skin"
    )
    output_scene.export(root / "repaired.glb")
    gray_mesh(tv, tf, "Fitted template").export(root / "fitted_template.glb")
    report["skin_triangles"] = len(ff)
    report["triangles"] = len(ff)
    report["mesh_parts"] = ["repaired_skin"]
    report["finite"] = bool(np.isfinite(vv).all())
    report["status"] = "pending_local_checks"
    (root / "repair_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    from timing import stage

    root = Path(sys.argv[1]).resolve()
    with stage(root / "timings.jsonl", "nose_transplant"):
        main(root)
