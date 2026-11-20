"""Source-bound masked Taubin fairing, with fixed topology and displacement cap."""

import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import trimesh
from scipy.sparse import coo_matrix, diags
from timing import stage


def digest(path):
    with Path(path).open("rb") as stream:
        value = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def denoise(
    vertices, faces, weights, *, iterations=80, lambda_=0.5, mu=-0.53, max_displacement
):
    """Return new vertices and metrics. Zero-weight vertices stay bitwise fixed.

    Inputs are local mesh coordinates, triangles, [0,1] weights and an explicit
    cap in those coordinate units. Does not identify face skin or test crossings.
    """
    v = np.asarray(vertices, dtype=float)
    raw_faces = np.asarray(faces)
    weight = np.asarray(weights, dtype=float)
    if (
        v.ndim != 2
        or v.shape[1] != 3
        or not np.isfinite(v).all()
        or raw_faces.ndim != 2
        or raw_faces.shape[1] != 3
        or raw_faces.dtype.kind not in "iu"
        or not len(raw_faces)
        or raw_faces.min() < 0
        or raw_faces.max() >= len(v)
        or weight.shape != (len(v),)
        or not np.isfinite(weight).all()
        or np.any((weight < 0) | (weight > 1))
    ):
        raise ValueError("Invalid mesh or vertex weights")
    f = raw_faces.astype(np.int64, copy=False)
    if (
        isinstance(iterations, bool)
        or not isinstance(iterations, int)
        or iterations < 0
        or not np.isfinite([lambda_, mu, max_displacement]).all()
        or not 0 < lambda_ <= 1
        or not -1 <= mu < 0
        or max_displacement < 0
    ):
        raise ValueError("Invalid fairing parameters")
    active = weight > 0
    ff = f[active[f].any(1)]
    report = dict(
        iterations=iterations,
        vertices=len(v),
        triangles=len(f),
        triangles_added=0,
        triangles_removed=0,
        protected_vertex_change_max=0,
    )
    if not len(ff) or iterations == 0 or max_displacement == 0:
        return v.copy(), dict(
            report,
            affected_vertices=0,
            displacement_max=0,
            displacement_rms=0,
            status="unchanged",
        )
    used, inv = np.unique(ff, return_inverse=True)
    triangles = inv.reshape(-1, 3)
    rest = v[used].copy()
    w = weight[used, None]
    current = rest.copy()
    e = np.concatenate(
        [triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]]
    )
    matrix = coo_matrix(
        (np.ones(len(e) * 2), (np.r_[e[:, 0], e[:, 1]], np.r_[e[:, 1], e[:, 0]])),
        shape=(len(used), len(used)),
    ).tocsr()
    matrix.data[:] = 1
    matrix = diags(1 / np.maximum(np.asarray(matrix.sum(1)).ravel(), 1)) @ matrix
    for _ in range(iterations):
        current += lambda_ * w * (matrix @ current - current)
        current += mu * w * (matrix @ current - current)
    delta = current - rest
    length = np.linalg.norm(delta, axis=1)
    delta *= np.minimum(1, max_displacement / np.maximum(length, 1e-15))[:, None]
    old = rest[triangles]
    normal = np.cross(old[:, 1] - old[:, 0], old[:, 2] - old[:, 0])
    area2 = np.linalg.norm(normal, axis=1)
    factor = np.ones(len(rest))
    for _ in range(40):
        trial = rest + factor[:, None] * delta
        tri = trial[triangles]
        new_normal = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        signed = (new_normal * normal).sum(1) / np.maximum(area2**2, 1e-30)
        bad = (area2 > 1e-15) & (signed < 0.25)
        if not bad.any():
            break
        factor[np.unique(triangles[bad])] *= 0.5
        factor = np.minimum(factor, 0.5 * (factor + matrix @ factor))
    else:
        raise ValueError("Could not preserve oriented triangle area")
    final = v.copy()
    final[used] = trial
    if not np.isfinite(final).all() or not np.array_equal(final[~active], v[~active]):
        raise ValueError("Nonfinite result or protected vertices changed")
    moved = np.linalg.norm(final - v, axis=1)
    changed = moved > 0
    measured = w[:, 0] > 0
    report.update(
        affected_vertices=int(changed.sum()),
        displacement_max=float(moved.max()),
        displacement_rms=float(np.sqrt(np.mean(moved[changed] ** 2)))
        if changed.any()
        else 0,
        high_frequency_laplacian_rms_before=float(
            np.sqrt(np.mean((matrix @ rest - rest)[measured] ** 2))
        ),
        high_frequency_laplacian_rms_after=float(
            np.sqrt(np.mean((matrix @ trial - trial)[measured] ** 2))
        ),
        minimum_signed_area_ratio=float(signed[area2 > 1e-15].min())
        if np.any(area2 > 1e-15)
        else None,
        status="pending_visual_and_crossing_review",
    )
    return final, report


def run(config):
    source, out = Path(config["source"]), Path(config["output"])
    products = [
        out,
        out.with_suffix(".report.json"),
        out.with_suffix(".provenance.npz"),
    ]
    if any(path.exists() for path in products) or source.resolve() == out.resolve():
        raise FileExistsError("Use a new output revision")
    source_hash = digest(source)
    if source_hash != config["source_sha256"]:
        raise ValueError("Denoise source hash mismatch")
    scene = trimesh.load(source, process=False, force="scene")
    name = config.get("mesh_name")
    if name is None:
        if len(scene.geometry) != 1:
            raise ValueError("Multiple geometries: specify mesh_name")
        name = next(iter(scene.geometry))
    mesh = scene.geometry[name]
    with np.load(config["mask"], allow_pickle=False) as data:
        if str(data["source_sha256"]) != source_hash:
            raise ValueError("Mask belongs to another source revision")
        weight = data["weights"].astype(float)
    before = np.array(mesh.vertices)
    final, report = denoise(
        before,
        mesh.faces,
        weight,
        iterations=config.get("iterations", 80),
        lambda_=config.get("lambda", 0.5),
        mu=config.get("mu", -0.53),
        max_displacement=config["max_displacement"],
    )
    mesh.vertices = final
    out.parent.mkdir(parents=True, exist_ok=True)
    scene.export(out)
    ids = np.flatnonzero(np.any(final != before, axis=1))
    np.savez_compressed(
        products[2],
        vertex_indices=ids,
        source_positions=before[ids],
        output_positions=final[ids],
        source_sha256=source_hash,
        weights=weight[ids],
    )
    report.update(
        source_sha256=source_hash,
        output_sha256=digest(out),
        mesh_name=name,
        limitation="Laplacian energy is a numerical proxy, not identity or age preservation.",
    )
    products[1].write_text(json.dumps(report, indent=2, allow_nan=False))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    with stage(
        Path(config["output"]).parent / "timings.jsonl", "wrinkle_geometry_repair"
    ):
        print(json.dumps(run(config)))


if __name__ == "__main__":
    main()
