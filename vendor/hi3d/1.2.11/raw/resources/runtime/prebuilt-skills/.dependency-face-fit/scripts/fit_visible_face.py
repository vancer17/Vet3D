"""Fit only observed facial skin of a hair-bearing source using the shared brush.
This bypasses no bald-target declaration: it is an explicit partial-observation adapter.
The complete target mesh and its hair are never deformed by registration.
"""

import json, time, hashlib
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree

from brush import fit_brush, similarity, landmark_weights, vertex_normals
from fit_metrics import metrics


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(c):
    skill = Path(__file__).resolve().parents[1]
    if not (
        c["hair_state"] in {"present", "bald"}
        and c["target_parts"] == "visible_semantic_face_skin"
    ):
        raise ValueError("Invalid input: fit_visible_face contract")
    tpath = skill / "assets/taro/template.npz"
    t = dict(np.load(tpath))
    target = dict(np.load(c["target"]))
    s = json.loads(Path(c["settings"]).read_text())
    if not (
        s["template_sha256"] == digest(tpath)
        and s["target_sha256"] == digest(c["target"])
    ):
        raise ValueError("Invalid input: fit_visible_face contract")
    if not (str(target["source_sha256"]) == c["source_sha256"] == digest(c["source"])):
        raise ValueError("Invalid input: fit_visible_face contract")
    if not (len(target["vertices"]) > 1000 and np.isfinite(target["vertices"]).all()):
        raise ValueError("Invalid input: fit_visible_face contract")
    if not (np.allclose(np.linalg.norm(target["normals"], axis=1), 1, atol=1e-3)):
        raise ValueError("Invalid input: fit_visible_face contract")
    a = s["landmarks"]
    ids = np.array([x["vertex_index"] for x in a])
    goals = np.array([x["target"] for x in a])
    mobility = np.asarray(s.get("mobility", np.ones(len(t["vertices"]))), float)
    fit_ids = np.asarray(s["fit_indices"])
    if (
        len(ids) < 4
        or ids.dtype.kind not in "iu"
        or ids.min() < 0
        or ids.max() >= len(t["vertices"])
        or not np.isfinite(goals).all()
        or goals.shape != (len(ids), 3)
        or mobility.shape != (len(t["vertices"]),)
        or not np.isfinite(mobility).all()
        or np.any((mobility < 0) | (mobility > 1))
        or fit_ids.dtype.kind not in "iu"
        or len(fit_ids) == 0
        or fit_ids.min() < 0
        or fit_ids.max() >= len(t["vertices"])
    ):
        raise ValueError("Invalid landmarks, fit indices or mobility")
    for item in s.get("brush_stages", []):
        if item["iterations"] <= 0 or item["sigma_edges"] <= 0:
            raise ValueError("Brush stages must be positive")
    linear, offset = similarity(
        t["vertices"][ids], goals, landmark_weights(a, s.get("landmark_group_budgets"))
    )
    rest = np.einsum("ij,kj->ik", t["vertices"], linear) + offset
    tri = np.concatenate([t["quads"][:, [0, 1, 2]], t["quads"][:, [0, 2, 3]]])
    normal = vertex_normals(rest, tri)
    # Keep the observed face exterior, without attracting the hidden scalp to face samples.
    dist = cKDTree(target["vertices"]).query(rest)[0]
    extent = np.ptp(target["vertices"], axis=0).max()
    observed = (normal[:, 1] < -0.05) & (dist < extent * 0.18)
    old = np.array(s["fit_indices"])
    s["fit_indices"] = old[observed[old]].tolist()
    if not (len(s["fit_indices"]) > 500):
        raise ValueError("Invalid input: fit_visible_face contract")
    # Keep original smooth mobility across nearby inner/outer sheets.
    out = Path(c["output"])
    out.mkdir(exist_ok=False, parents=True)
    (out / "observed_face_settings.json").write_text(json.dumps(s))
    start = time.monotonic()
    v, linear, offset, rest, smooth, history = fit_brush(
        t["vertices"],
        t["quads"],
        target["vertices"],
        None,
        s,
        target_normals=target["normals"],
    )
    if not np.isfinite(v).all():
        raise ValueError("Nonfinite fitted vertices")
    np.savez_compressed(
        out / "brush_fit.npz",
        source_sha256=np.array(c["source_sha256"]),
        vertices=v,
        quads=t["quads"],
        quad_uvs=t["quad_uvs"],
        rest=rest,
        native_vertices=np.einsum("ij,kj->ik", v - offset, np.linalg.inv(linear)),
        linear=linear,
        offset=offset,
        dna_sha256=t.get("dna_sha256", np.array("")),
    )
    report = dict(
        seconds=time.monotonic() - start,
        stages=history,
        **metrics(v, rest, smooth, s, s["fit_indices"]),
        template_sha256=digest(tpath),
        target_sha256=digest(c["target"]),
        vertices=len(v),
        quads=len(t["quads"]),
        topology_preserved=True,
        observed_fit_vertices=len(s["fit_indices"]),
        target_samples=len(target["vertices"]),
        source_has_hair=c["hair_state"] == "present",
        scope="Front-visible Sapiens2 facial skin only; hidden scalp is not reconstructed or evaluated",
        status="fitted_pending_geometry_and_runtime_review",
    )
    (out / "brush_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "stages"}))

    return report


def main():
    import argparse
    from timing import stage

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config")
    a = parser.parse_args()
    c = json.loads(Path(a.config).read_text())
    with stage(Path(c["output"]).parent / "timings.jsonl", "fitting"):
        run(c)


if __name__ == "__main__":
    main()
