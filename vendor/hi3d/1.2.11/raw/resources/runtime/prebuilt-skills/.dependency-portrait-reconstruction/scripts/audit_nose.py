"""Skin-only local topology/crossing audit, with mesh-bound face provenance."""

import hashlib
import json
import sys
import time
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from collision import crossing_pairs, triangle_stats
from triangle_arrays import edge_incidence


def run(root):
    profile = json.loads((root / "profile.json").read_text())
    report = {}
    start = time.monotonic()
    for label, path in [
        ("original", root / "original.glb"),
        ("repaired", root / "repaired.glb"),
    ]:
        mesh_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)
        bpy.ops.import_scene.gltf(filepath=str(path))
        meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        ob = next((o for o in meshes if o.name == "repaired_skin"), meshes[0])
        mesh = ob.data
        mesh.calc_loop_triangles()
        v = np.empty((len(mesh.vertices), 3))
        mesh.vertices.foreach_get("co", v.ravel())
        v = np.c_[v, np.ones(len(v))] @ np.asarray(ob.matrix_world).T
        v = v[:, :3]
        v = v[:, [0, 2, 1]] * np.array([1, 1, -1])
        f = np.empty((len(mesh.loop_triangles), 3), np.int32)
        mesh.loop_triangles.foreach_get("vertices", f.ravel())
        report[label] = {}
        for region in [profile["nose"], *profile["eyes"]]:
            name = region["name"]
            c = region["center"]
            r = region["radii"]
            rr = np.linalg.norm((v[:, :2] - c) / r, axis=1)
            selected = np.where(
                (rr[f].max(1) < profile["validation"]["roi_factor"])
                & (v[f, 2].min(1) > profile["validation"]["min_z"])
            )[0]
            ff = f[selected]
            ids, inverse = np.unique(ff, return_inverse=True)
            vv = v[ids]
            ff = inverse.reshape(-1, 3)
            if len(ff) == 0:
                raise ValueError("Audit region is empty: " + name)
            edges = np.concatenate([ff[:, [0, 1]], ff[:, [1, 2]], ff[:, [2, 0]]])
            unique, inverse, counts = np.unique(
                np.sort(edges, axis=1), axis=0, return_inverse=True, return_counts=True
            )
            balance = np.bincount(
                inverse, weights=np.where(edges[:, 0] < edges[:, 1], 1, -1)
            )
            # Include all incident faces before counting: cropping a ROI alone
            # creates artificial boundary edges at its perimeter.
            inside = (rr < profile["validation"]["roi_factor"]) & (v[:, 2] > profile["validation"]["min_z"])
            incident = f[inside[f].any(1)]
            all_edges, all_counts, _ = edge_incidence(incident, discard_collapsed=True)
            open_edges = int(np.count_nonzero((all_counts == 1) & inside[all_edges].all(1)))
            pairs = crossing_pairs(vv, ff)
            stats = dict(
                triangles=len(ff),
                boundary_edges=open_edges,
                nonmanifold_edges=int(sum(counts > 2)),
                winding_conflicts=int(sum((counts == 2) & (abs(balance) > 0))),
                crossing_pairs=len(pairs),
                **triangle_stats(vv, ff),
            )
            report[label][name] = stats
            # Always replace even an empty result, so old crossings cannot survive a rerun.
            np.savez_compressed(
                root / (label + "_" + name + "_crossings.npz"),
                vertices=vv,
                faces=ff,
                pairs=pairs,
                global_face_indices=selected,
                mesh_sha256=mesh_hash,
            )
            print(label, name, stats, flush=True)
        report[label + "_sha256"] = mesh_hash
    report["seconds"] = time.monotonic() - start
    report["scope"] = (
        "Skin-only, configured nose region. Excludes eye/eyelid contact, "
        "adjacent faces, tangency and coplanar overlaps. Not a global anatomical or printability check."
    )
    (root / "geometry_validation.json").write_text(json.dumps(report, indent=2))

    return report


if __name__ == "__main__":
    from timing import stage

    root = Path(sys.argv[sys.argv.index("--") + 1])
    with stage(root / "timings.jsonl", "nose_audit"):
        result = run(root)
        for stats in result["repaired"].values():
            if not stats["finite"] or any(
                stats[k]
                for k in [
                    "boundary_edges",
                    "nonmanifold_edges",
                    "winding_conflicts",
                    "crossing_pairs",
                    "degenerate_triangles",
                ]
            ):
                raise ValueError("Local nose audit failed; inspect saved report")
