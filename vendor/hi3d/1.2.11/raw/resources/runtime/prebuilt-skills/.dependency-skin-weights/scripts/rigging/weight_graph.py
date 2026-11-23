"""Screened harmonic skin weights; runs in Blender or an external NumPy/SciPy Python."""

import argparse
import hashlib
import inspect
import json
from pathlib import Path
import numpy as np
from .io_utils import file_digest


def mesh_digest(vertices, faces):
    h = hashlib.sha256(np.asarray(vertices, dtype="<f4").tobytes())
    h.update(np.asarray(faces, dtype="<i4").tobytes())
    return h.hexdigest()


def calibration_digest(profile, height):
    data = {key: profile[key] for key in ["bones", "default_bone", "weight_regions"]}
    data["height"] = height
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def solve_weights(
    v,
    f,
    initial,
    radius,
    fidelity_length,
    edge_floor,
    method="direct",
    rtol=2e-6,
    maxiter=1500,
    diagnostics=None,
):
    """Keep rigid anchors exact; reject unconverged CG rather than exporting a draft."""
    from scipy.sparse import coo_matrix, diags
    from scipy.sparse.csgraph import dijkstra
    from scipy.sparse.linalg import cg, splu

    v = np.asarray(v, dtype=np.float64)
    raw_faces = np.asarray(f)
    f = np.asarray(f, dtype=np.int64)
    initial = np.asarray(initial, dtype=np.float64)
    if v.ndim != 2 or v.shape[1] != 3 or not len(v) or not np.isfinite(v).all():
        raise ValueError("Expected finite, nonempty N×3 vertices")
    if f.ndim != 2 or f.shape[1] != 3 or not np.array_equal(raw_faces, f):
        raise ValueError("Expected integer M×3 triangles")
    if f.size and (f.min() < 0 or f.max() >= len(v)):
        raise ValueError("Triangle index outside vertex array")
    if (
        initial.ndim != 2
        or initial.shape[0] != len(v)
        or not initial.shape[1]
        or not np.isfinite(initial).all()
        or np.any(initial < 0)
        or not np.allclose(initial.sum(1), 1, atol=1e-8, rtol=0)
    ):
        raise ValueError("Initial weights must be finite, nonnegative and normalized")
    if (
        not np.isfinite([radius, fidelity_length, edge_floor, rtol]).all()
        or radius < 0
        or min(fidelity_length, edge_floor, rtol) <= 0
        or maxiter < 1
        or method not in {"direct", "cg"}
    ):
        raise ValueError("Invalid solver parameters")
    edges = np.unique(
        np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1),
        axis=0,
    )
    edges = edges[edges[:, 0] != edges[:, 1]]
    lengths = np.maximum(
        np.linalg.norm(v[edges[:, 0]] - v[edges[:, 1]], axis=1), edge_floor
    )
    rows, cols = np.r_[edges[:, 0], edges[:, 1]], np.r_[edges[:, 1], edges[:, 0]]
    owner = initial.argmax(1)
    boundary = edges[owner[edges[:, 0]] != owner[edges[:, 1]]]
    fixed = initial.max(1) >= 1 - 1e-10
    if len(boundary) and radius:
        graph = coo_matrix(
            (np.r_[lengths, lengths], (rows, cols)), shape=(len(v), len(v))
        ).tocsr()
        distance = dijkstra(
            graph,
            directed=False,
            indices=np.unique(boundary),
            min_only=True,
            limit=radius,
        )
        fixed[distance < radius] = False
        del graph, distance
    free, anchors = np.flatnonzero(~fixed), np.flatnonzero(fixed)
    report = {
        "method": method,
        "vertices": len(v),
        "edges": len(edges),
        "free_vertices": len(free),
        "anchor_vertices": len(anchors),
        "radius": radius,
        "fidelity_length": fidelity_length,
        "edge_floor": edge_floor,
        "rtol": rtol,
        "maxiter": maxiter,
        "columns": [],
    }
    score = initial.copy()
    if len(free):
        conductance = 1 / lengths**2
        adj = coo_matrix(
            (np.r_[conductance, conductance], (rows, cols)), shape=(len(v), len(v))
        ).tocsr()
        fidelity = 1 / fidelity_length**2
        diagonal = np.asarray(adj.sum(1)).ravel() + fidelity
        system = diags(diagonal[free]) - adj[free][:, free]
        boundary_matrix = adj[free][:, anchors]
        factor = splu(system.tocsc()) if method == "direct" else None
        preconditioner = diags(1 / diagonal[free]) if method == "cg" else None
        tolerance = (
            {"rtol": rtol}
            if "rtol" in inspect.signature(cg).parameters
            else {"tol": rtol}
        )
        for j in range(initial.shape[1]):
            rhs = fidelity * initial[free, j] + boundary_matrix @ initial[anchors, j]
            iterations = [0]

            def callback(_):
                iterations[0] += 1

            if not np.any(rhs):
                solution, info = np.zeros(len(free)), 0
            elif factor is not None:
                solution, info = factor.solve(rhs), 0
            else:
                solution, info = cg(
                    system,
                    rhs,
                    x0=initial[free, j],
                    M=preconditioner,
                    maxiter=maxiter,
                    atol=0,
                    callback=callback,
                    **tolerance,
                )
            residual = float(
                np.linalg.norm(system @ solution - rhs)
                / max(np.linalg.norm(rhs), np.finfo(float).tiny)
            )
            report["columns"].append(
                {
                    "index": j,
                    "iterations": iterations[0],
                    "info": int(info),
                    "relative_residual": residual,
                }
            )
            if (
                info != 0
                or not np.isfinite(solution).all()
                or residual > max(5 * rtol, 1e-9)
            ):
                if diagnostics is not None:
                    diagnostics.update(report)
                raise RuntimeError(
                    f"Weight column {j} did not converge: info={info}, residual={residual:g}"
                )
            score[free, j] = solution
    score = np.maximum(score, 0)
    score /= np.maximum(score.sum(1, keepdims=True), 1e-12)
    score[fixed] = initial[fixed]
    if diagnostics is not None:
        diagnostics.update(report)
    return score, fixed


def solve_archive(
    input_path,
    output_path,
    radius,
    fidelity_length,
    edge_floor,
    method="cg",
    rtol=2e-6,
    maxiter=1500,
):
    """Validate an exported mesh cache, solve it and write weights plus diagnostics."""
    input_path, output_path = Path(input_path), Path(output_path)
    report_path = output_path.with_suffix(".solver.json")
    if output_path.exists() or report_path.exists():
        raise ValueError("Use new output paths")
    d = np.load(input_path, allow_pickle=False)
    fingerprint = mesh_digest(d["vertices"], d["faces"])
    if str(d["mesh_sha256"]) != fingerprint:
        raise ValueError("Weight input fingerprint mismatch")
    names = d["bone_names"]
    calibration_sha = str(d["calibration_sha256"].item())
    if (
        names.ndim != 1
        or names.dtype.kind not in "US"
        or len(names) != d["initial"].shape[1]
    ):
        raise ValueError("Bone names do not match weight columns")
    report = {
        "mesh_sha256": fingerprint,
        "calibration_sha256": calibration_sha,
        "input_sha256": file_digest(input_path),
    }
    try:
        weights, fixed = solve_weights(
            d["vertices"],
            d["faces"],
            d["initial"],
            radius,
            fidelity_length,
            edge_floor,
            method,
            rtol,
            maxiter,
            report,
        )
    except RuntimeError:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(dict(report, passed=False), indent=2))
        raise
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as stream:
        np.savez_compressed(
            stream,
            weights=weights,
            fixed=fixed,
            mesh_sha256=fingerprint,
            bone_names=names,
            calibration_sha256=calibration_sha,
        )
    report["weights_sha256"] = file_digest(output_path)
    report_path.write_text(json.dumps(dict(report, passed=True), indent=2))
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--radius", type=float, required=True, help="Mesh-coordinate units")
    p.add_argument("--fidelity-length", type=float, required=True)
    p.add_argument("--edge-floor", type=float, required=True)
    p.add_argument("--method", choices=["cg", "direct"], default="cg")
    p.add_argument("--rtol", type=float, default=2e-6)
    p.add_argument("--maxiter", type=int, default=1500)
    a = p.parse_args(argv)
    report = solve_archive(
        a.input,
        a.output,
        a.radius,
        a.fidelity_length,
        a.edge_floor,
        a.method,
        a.rtol,
        a.maxiter,
    )
    print(json.dumps(report))


if __name__ == "__main__":
    main()
