"""Check explicit mesh pairs at integer/subframes in world space; no inferred exclusions."""

import argparse
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import bpy
import numpy as np
from .mesh_snapshot import mesh_data_snapshot, mesh_source
from mathutils.bvhtree import BVHTree
from rigging.blend_common import open_input, write_json
from rigging.weight_graph import mesh_digest, file_digest


def sample_frames(expression):
    result = set()
    try:
        for block in expression.split(","):
            terms = [Decimal(x) for x in block.split(":")]
            if not all(x.is_finite() for x in terms):
                raise ValueError("Nonfinite frame")
            if len(terms) == 1:
                result.add(terms[0])
                continue
            if len(terms) not in {2, 3}:
                raise ValueError("Use start:end[:step]")
            start, end = terms[:2]
            step = terms[2] if len(terms) == 3 else Decimal(1)
            if step <= 0 or end < start:
                raise ValueError("Frame range must increase with a positive step")
            count = int((end - start) // step) + 1
            if count > 1000000:
                raise ValueError("Frame range is unexpectedly large")
            result.update(start + step * i for i in range(count))
    except InvalidOperation as error:
        raise ValueError("Invalid frame expression") from error
    if not result:
        raise ValueError("No frames requested")
    return [float(x) for x in sorted(result)]


def mesh_arrays(mesh):
    if not len(mesh.polygons) or any(len(p.vertices) != 3 for p in mesh.polygons):
        raise ValueError("Contact meshes must be nonempty and triangulated")
    data = mesh_data_snapshot(mesh, triangulation='require_triangles', precision='float32')
    return data['vertices'], data['triangles']


def rest_surface(ob):
    if ob.type != "MESH":
        raise ValueError(f"{ob.name} is not a mesh")
    v, f = mesh_arrays(ob.data)
    return {"vertices": v, "faces": f, "mesh_sha256": mesh_digest(v, f)}


def evaluated_surface(ob, depsgraph, rest):
    with mesh_source(ob, evaluated=True, depsgraph=depsgraph) as (evaluated, mesh):
        v, f = mesh_arrays(mesh)
        if len(v) != len(rest["vertices"]) or not np.array_equal(f, rest["faces"]):
            raise ValueError(
                f"{ob.name}: topology changed; rest-face exclusions would be invalid"
            )
        matrix = np.asarray(evaluated.matrix_world, dtype=np.float64)
        world = v @ matrix[:3, :3].T + matrix[:3, 3]
        if not np.isfinite(world).all() or abs(np.linalg.det(matrix[:3, :3])) < 1e-15:
            raise ValueError(f"{ob.name}: nonfinite or singular evaluated geometry")
        # FromObject uses object-local coordinates; explicit world vertices handle different parents/transforms.
        tree = BVHTree.FromPolygons(world.tolist(), f.tolist(), all_triangles=True)
        return {"tree": tree, "vertices": world, "bounds": (world.min(0), world.max(0))}


def exclusion_mask(surface, rule):
    if not str(rule.get("reason", "")).strip():
        raise ValueError("An attachment exclusion needs a reason")
    if rule.get("mesh_sha256") != surface["mesh_sha256"]:
        raise ValueError("An exclusion must match the current rest-mesh fingerprint")
    mask = np.zeros(len(surface["faces"]), bool)
    if ("face_ids" in rule) == ("rest_bounds" in rule):
        raise ValueError("Specify exactly one exclusion selector")
    if "face_ids" in rule:
        ids = np.asarray(rule["face_ids"])
        if ids.ndim != 1 or (
            ids.size
            and (ids.dtype.kind not in "iu" or ids.min() < 0 or ids.max() >= len(mask))
        ):
            raise ValueError("Invalid exclusion face IDs")
        mask[ids.astype(np.int64)] = True
    elif "rest_bounds" in rule:
        bounds = np.asarray(rule["rest_bounds"], dtype=float)
        if (
            bounds.shape != (2, 3)
            or not np.isfinite(bounds).all()
            or np.any(bounds[0] > bounds[1])
        ):
            raise ValueError("Expected finite ordered rest bounds")
        inside = np.all(
            (surface["vertices"] >= bounds[0]) & (surface["vertices"] <= bounds[1]),
            axis=1,
        )
        mask = inside[surface["faces"]].all(1)
    else:
        raise ValueError("Use explicit face_ids or rest_bounds for an attachment")
    if mask.all():
        raise ValueError("Do not exclude an entire mesh from a contact pair")
    return mask


def check(spec, frames, collect_faces=False):
    frames = [float(frame) for frame in frames]
    if not frames or not np.isfinite(frames).all():
        raise ValueError("Request finite, nonempty sample frames")
    pairs = spec.get("pairs", [])
    if not pairs:
        raise ValueError("Specify at least one mesh pair")
    names = sorted({name for pair in pairs for name in [pair["a"], pair["b"]]})
    objects = {name: bpy.data.objects[name] for name in names}
    rest = {name: rest_surface(ob) for name, ob in objects.items()}
    prepared = []
    exclusions = []
    for index, pair in enumerate(pairs):
        if pair["a"] == pair["b"]:
            raise ValueError(
                "Self-intersection needs adjacency filtering; use distinct objects"
            )
        masks = {
            name: np.zeros(len(rest[name]["faces"]), bool)
            for name in [pair["a"], pair["b"]]
        }
        for rule in pair.get("exclude", []):
            name = rule["object"]
            if name not in masks:
                raise ValueError("Exclusion object is outside its pair")
            mask = exclusion_mask(rest[name], rule)
            masks[name] |= mask
            exclusions.append(
                {
                    "pair": index,
                    "object": name,
                    "reason": rule["reason"],
                    "face_count": int(mask.sum()),
                    "mesh_sha256": rest[name]["mesh_sha256"],
                    "selector": {
                        key: rule[key]
                        for key in ["face_ids", "rest_bounds"]
                        if key in rule
                    },
                }
            )
        if any(mask.all() for mask in masks.values()):
            raise ValueError("Combined exclusions cover a whole object")
        prepared.append(masks)
    report = {
        "frames": frames,
        "objects": {
            n: {"rest_mesh_sha256": r["mesh_sha256"], "triangles": len(r["faces"])}
            for n, r in rest.items()
        },
        "pairs": [{"a": p["a"], "b": p["b"]} for p in pairs],
        "exclusions": exclusions,
        "results": [],
        "passed": True,
        "limitations": "Triangle surface intersections only; no containment, self-intersection, continuous-time, or artistic-quality proof. Exclusions are explicit attachment assumptions.",
    }
    unions = [{name: set() for name in [p["a"], p["b"]]} for p in pairs]
    scene = bpy.context.scene
    original = (scene.frame_current, scene.frame_subframe)
    try:
        for frame in frames:
            integer = int(np.floor(frame))
            scene.frame_set(integer, subframe=frame - integer)
            depsgraph = bpy.context.evaluated_depsgraph_get()
            evaluated = {
                name: evaluated_surface(ob, depsgraph, rest[name])
                for name, ob in objects.items()
            }
            row = {"frame": frame, "pairs": []}
            for index, pair in enumerate(pairs):
                a, b = pair["a"], pair["b"]
                ea, eb = evaluated[a], evaluated[b]
                separated = np.any(ea["bounds"][1] < eb["bounds"][0]) or np.any(
                    eb["bounds"][1] < ea["bounds"][0]
                )
                hits = [] if separated else ea["tree"].overlap(eb["tree"])
                mask = prepared[index]
                kept = [(i, j) for i, j in hits if not (mask[a][i] or mask[b][j])]
                samples = []
                for i, j in kept[:8]:
                    samples.append(
                        {
                            "a_face": i,
                            "b_face": j,
                            "a_rest_center": rest[a]["vertices"][rest[a]["faces"][i]]
                            .mean(0)
                            .tolist(),
                            "a_world_center": ea["vertices"][rest[a]["faces"][i]]
                            .mean(0)
                            .tolist(),
                            "b_rest_center": rest[b]["vertices"][rest[b]["faces"][j]]
                            .mean(0)
                            .tolist(),
                        }
                    )
                row["pairs"].append(
                    {
                        "pair": index,
                        "raw_contacts": len(hits),
                        "excluded_contacts": len(hits) - len(kept),
                        "contacts": len(kept),
                        "samples": samples,
                    }
                )
                if collect_faces:
                    unions[index][a].update(i for i, _ in kept)
                    unions[index][b].update(j for _, j in kept)
                report["passed"] &= not bool(kept)
            report["results"].append(row)
            print(
                "CONTACT_SAMPLE",
                frame,
                [p["contacts"] for p in row["pairs"]],
                flush=True,
            )
    finally:
        scene.frame_set(original[0], subframe=original[1])
    if collect_faces:
        report["contact_face_union"] = [
            {k: sorted(v) for k, v in row.items()} for row in unions
        ]
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--spec", type=Path, required=True)
    p.add_argument(
        "--frames",
        required=True,
        help="Inclusive start:end[:step], comma-separated; e.g. 1:24:0.5",
    )
    p.add_argument("--report", type=Path, required=True)
    p.add_argument(
        "--collect-faces",
        action="store_true",
        help="Collect contacted rest-face IDs; does not cut geometry",
    )
    a = p.parse_args(argv)
    if a.report.expanduser().resolve().exists():
        raise ValueError("Use a new report path")
    path = open_input(a.input)
    report = check(
        json.loads(a.spec.read_text()), sample_frames(a.frames), a.collect_faces
    )
    report["input_sha256"] = file_digest(path)
    report["spec_sha256"] = file_digest(a.spec)
    write_json(a.report, report)
    if not report["passed"]:
        raise RuntimeError("Surface contacts found; inspect the report")


if __name__ == "__main__":
    main()
