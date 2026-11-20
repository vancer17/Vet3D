"""Check saved Blender deformation, skin seams, normalized weights and wrist angles."""

import argparse
import json
import math
from pathlib import Path
import bpy
import numpy as np
from .skin_weights import stretch_metrics


def parse_frames(value):
    result = []
    for part in value.split(","):
        if ":" in part:
            start, end = map(int, part.split(":"))
            result.extend(range(start, end + 1))
        else:
            result.append(int(part))
    return sorted(set(result))


def validate(collection, rig, frames, height, seam_exclude=()):
    parts = sorted(bpy.data.collections[collection].objects, key=lambda o: o.name)
    reference = {}
    all_rest = []
    skin_ids = []
    cursor = 0
    invalid_weights = 0
    for ob in parts:
        if ob.type != "MESH":
            continue
        me = ob.data
        if any(len(p.vertices) != 3 for p in me.polygons):
            raise ValueError("QA expects triangular working topology")
        v = np.empty(len(me.vertices) * 3, dtype=np.float32)
        me.vertices.foreach_get("co", v)
        v = v.reshape(-1, 3)
        f = np.empty(len(me.loops), dtype=np.int32)
        me.loops.foreach_get("vertex_index", f)
        f = f.reshape(-1, 3)
        for vertex in me.vertices:
            groups = [
                g.weight
                for g in vertex.groups
                if ob.vertex_groups[g.group].name in rig.data.bones
                and rig.data.bones[ob.vertex_groups[g.group].name].use_deform
            ]
            if (
                not groups
                or not all(math.isfinite(w) for w in groups)
                or abs(sum(groups) - 1) > 0.0002
                or min(groups) < 0
            ):
                invalid_weights += 1
        reference[ob.name] = (f, v)
        if not ob.get("intentional_rigid_shell") and ob.name not in seam_exclude:
            skin_ids.extend(range(cursor, cursor + len(v)))
        all_rest.append(v)
        cursor += len(v)
    skin_ids = np.array(skin_ids, dtype=np.int32)
    if len(skin_ids):
        _, first, inverse = np.unique(
            np.concatenate(all_rest)[skin_ids],
            axis=0,
            return_index=True,
            return_inverse=True,
        )
    report = dict(
        frames_checked=0,
        nonfinite_frames=0,
        invalid_weight_vertices=invalid_weights,
        significant_stretched_faces=0,
        large_area_expansions=0,
        max_edge_ratio=0.0,
        max_area_ratio=0.0,
        max_skin_shared_boundary_gap_m=0.0,
        wrist_bend_degrees={},
        per_frame=[],
        worst=[],
    )
    wrists = {
        s: []
        for s in ["L", "R"]
        if "hand." + s in rig.pose.bones and "forearm." + s in rig.pose.bones
    }
    for frame in frames:
        bpy.context.scene.frame_set(frame)
        deps = bpy.context.evaluated_depsgraph_get()
        posed_all = []
        count = 0
        maxr = 0.0
        maxa = 0.0
        finite = True
        for ob in parts:
            if ob.name not in reference:
                continue
            f, rest = reference[ob.name]
            evaluated = ob.evaluated_get(deps)
            me = evaluated.to_mesh()
            v = np.empty(len(me.vertices) * 3, dtype=np.float32)
            me.vertices.foreach_get("co", v)
            v = v.reshape(-1, 3)
            if len(v) != len(ob.data.vertices):
                raise ValueError(
                    "Topology-changing modifiers invalidate vertex correspondence"
                )
            posed_all.append(v)
            finite &= bool(np.isfinite(v).all())
            if np.isfinite(v).all():
                check = stretch_metrics(rest, v, f, height)
                count += check["significant_faces"]
                report["large_area_expansions"] += check["large_area_faces"]
                if check["worst_faces"]:
                    detail = check["worst_face_metrics"][0]
                    index = detail["face"]
                    report["worst"].append(
                        dict(
                            frame=frame,
                            part=ob.name,
                            face=index,
                            count=check["bad_face_count"],
                            edge_ratio=detail["edge_ratio"],
                            area_ratio=detail["area_ratio"],
                            posed_center=v[f[index]].mean(axis=0).tolist(),
                        )
                    )
                maxr = max(maxr, check["max_edge_ratio"])
                maxa = max(maxa, check["max_area_ratio"])
            evaluated.to_mesh_clear()
        if len(skin_ids):
            positions = np.concatenate(posed_all)[skin_ids]
            gap = float(
                np.linalg.norm(positions - positions[first][inverse], axis=1).max()
            )
            report["max_skin_shared_boundary_gap_m"] = max(
                report["max_skin_shared_boundary_gap_m"], gap
            )
        for side in wrists:
            fore = rig.pose.bones["forearm." + side]
            hand = rig.pose.bones["hand." + side]
            wrists[side].append(
                math.degrees((fore.tail - fore.head).angle(hand.tail - hand.head))
            )
        report["frames_checked"] += 1
        report["nonfinite_frames"] += int(not finite)
        report["significant_stretched_faces"] += count
        report["max_edge_ratio"] = max(report["max_edge_ratio"], maxr)
        report["max_area_ratio"] = max(report["max_area_ratio"], maxa)
        report["per_frame"].append(
            dict(frame=frame, significant_faces=count, max_edge_ratio=maxr)
        )
    report["worst"] = sorted(
        report["worst"], key=lambda r: r["edge_ratio"], reverse=True
    )[:100]
    report["wrist_bend_degrees"] = {
        s: dict(min=min(v), max=max(v), mean=float(np.mean(v)))
        for s, v in wrists.items()
    }
    report["pass"] = not (
        invalid_weights
        or report["nonfinite_frames"]
        or report["significant_stretched_faces"]
        or report["large_area_expansions"]
        or report["max_skin_shared_boundary_gap_m"] > height * 1e-6
    )
    report["criteria"] = dict(
        edge_ratio=3,
        edge_growth_m=height / 120,
        area_ratio=8,
        double_area_growth_m2=height**2 / 81000,
        seam_tolerance_m=height * 1e-6,
    )
    report["limitations"] = (
        "Numerical deformation check; does not prove good anatomy, absence of self-intersection, or artistic motion quality. UV positions compared only where rest coordinates are exactly shared."
    )
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--collection", default="CharacterParts")
    p.add_argument("--rig", default="CharacterRig")
    p.add_argument(
        "--frames", required=True, help="Inclusive ranges, e.g. 1:23,181:540"
    )
    p.add_argument("--height", type=float, default=1.8)
    p.add_argument(
        "--seam-exclude",
        nargs="*",
        default=[],
        help="Intentional rigid accessory shells only",
    )
    a = p.parse_args(argv)
    frames = parse_frames(a.frames)
    if not frames:
        raise ValueError("At least one frame required")
    bpy.ops.wm.open_mainfile(filepath=str(a.input))
    r = validate(
        a.collection, bpy.data.objects[a.rig], frames, a.height, a.seam_exclude
    )
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(r, indent=2))
    print(json.dumps({k: v for k, v in r.items() if k not in {"per_frame", "worst"}}))
    if not r["pass"]:
        raise RuntimeError("Deformation acceptance failed; inspect report")


if __name__ == "__main__":
    main()
