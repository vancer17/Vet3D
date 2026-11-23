"""Reopen delivered scenes and inspect actual evaluated deformation states."""

import json
import sys
from pathlib import Path
import numpy as np
import bpy
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collision import crossing_pairs, triangle_stats
from low_rig import mesh_triangles
from blender_io import coordinates, render_view, material


def evaluate(obj):
    bpy.context.view_layer.update()
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    points = (
        coordinates(evaluated)
        if evaluated.data == mesh
        else np.array([tuple(v.co) for v in mesh.vertices])
    )
    evaluated.to_mesh_clear()
    return points.astype(float)


def inspect_states(obj, names, skin_mask=None):
    obj.hide_set(False)
    keys = obj.data.shape_keys
    if keys.animation_data:
        keys.animation_data_clear()
    for key in keys.key_blocks:
        if not key.name.startswith("POSE_"):
            key.value = 0
    tri = mesh_triangles(obj.data)
    base = evaluate(obj)
    if skin_mask is not None:
        tri = tri[skin_mask[tri].all(1)]
    baseline = set(map(tuple, crossing_pairs(base, tri)))
    armatures = [m.object for m in obj.modifiers if m.type == "ARMATURE"]
    bone_names = {b.name for armature in armatures for b in armature.data.bones}
    groups = {vg.index: vg.name for vg in obj.vertex_groups}
    weights = np.array(
        [
            sum(g.weight for g in v.groups if groups[g.group] in bone_names)
            for v in obj.data.vertices
        ]
    )
    edge = np.array([tuple(e.vertices) for e in obj.data.edges])
    length = np.linalg.norm(base[edge[:, 0]] - base[edge[:, 1]], axis=1)
    results = []
    cases = [("neutral", {})]
    for name in names:
        values = [0.25, 0.5, 0.75, 1]
        if "Blink" in name:
            values = [0.25, 0.5, 0.75, 0.9, 0.97, 1]
        cases.extend((name + "@" + str(value), {name: value}) for value in values)
    if all(
        name in names for name in ["eyeBlink_L", "eyeBlink_R", "mouthSmile", "jawOpen"]
    ):
        cases.extend(
            [
                ("both_blink", {"eyeBlink_L": 1, "eyeBlink_R": 1}),
                (
                    "smile_blink",
                    {"mouthSmile": 0.65, "eyeBlink_L": 0.8, "eyeBlink_R": 0.8},
                ),
                ("smile_open", {"mouthSmile": 0.5, "jawOpen": 0.45}),
            ]
        )
    for label, values in cases:
        for name in names:
            keys.key_blocks[name].value = values.get(name, 0)
        points = evaluate(obj)
        pairs = set(map(tuple, crossing_pairs(points, tri)))
        stats = triangle_stats(points, tri)
        lengths = np.linalg.norm(points[edge[:, 0]] - points[edge[:, 1]], axis=1)
        stats.update(
            {
                "state": label,
                "crossings": len(pairs),
                "new_crossings": len(pairs - baseline),
                "edge_ratio_p99": float(
                    np.percentile(lengths / np.maximum(length, 1e-15), 99)
                ),
            }
        )
        results.append(stats)
        print("VALIDATE", obj.name, label, stats["new_crossings"], flush=True)
    for name in names:
        keys.key_blocks[name].value = 0
    return {
        "weight_sum_range": [float(weights.min()), float(weights.max())],
        "baseline_crossings": len(baseline),
        "states": results,
        "passed": bool(
            np.allclose(weights, 1, atol=2e-5)
            and all(
                s["finite"] and not s["new_crossings"] and not s["degenerate_triangles"]
                for s in results
            )
        ),
        "scope": "evaluated skin mesh only, nonadjacent triangle crossings; excludes coplanar/tangent contacts and inter-part collisions",
    }


def validate(config, stage):
    root = Path(config["output"])
    path = root / ("Lowpoly_Rigged.blend" if stage == "low" else "Heads_Rigged.blend")
    bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False)
    scene = bpy.context.scene
    scene.frame_set(1)
    low = bpy.data.objects["Lowpoly_Head"]
    names = np.load(root / "lowpoly_data.npz")["expression_names"].tolist()
    report = {
        "blender": bpy.app.version_string,
        "file": path.name,
        "lowpoly": inspect_states(low, names),
    }
    (
        root / ("lowpoly_validation.json" if stage == "low" else "validation.json")
    ).write_text(json.dumps(report, indent=2))
    bounds = np.array(json.loads((root / "source_report.json").read_text())["bounds"])
    span = max(bounds[1] - bounds[0])
    center = bounds.mean(0)
    for other in scene.objects:
        if other.type == "MESH":
            other.hide_render = not other.name.startswith("Lowpoly_")
    for name, value in ([
        ("neutral", 0),
        ("eyeBlink_L", 1),
        ("mouthSmile", 0.75),
        ("jawOpen", 0.6),
    ] if config.get("diagnostic_previews", False) else []):
        for key in low.data.shape_keys.key_blocks:
            key.value = value if key.name == name else 0
        render_view(
            scene.camera, center, span, (0, -3, 0), root / f"low_check_{name}.png"
        )
    if not report["lowpoly"]["passed"]:
        raise ValueError(
            "Lowpoly deformation review failed; see lowpoly_validation.json"
        )
    print("VALIDATION_COMPLETE", stage, flush=True)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1 :]
    validate(json.loads(Path(args[1]).read_text()), args[0])
