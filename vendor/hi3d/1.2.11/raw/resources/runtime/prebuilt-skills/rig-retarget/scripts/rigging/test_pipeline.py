"""Synthetic GLB -> BVH cache -> exported weights -> animated blend integration test."""

import argparse
import json
from pathlib import Path
import sys
import bpy
from .make_profile import profile
from .prepare_mesh import prepare_mesh
from .cache_bvh import cache_motion
from .build_character import build_character
from .weight_graph import solve_archive
from .validate_blend import validate


def write_bvh(path, calibration, frames=5, height=1.8):
    """Write a small known humanoid hierarchy and root motion, with no external asset."""
    specs = {row["name"]: row for row in calibration["bones"] if row["deform"]}
    mapping = calibration["motion_map"]
    order = []
    lines = ["HIERARCHY"]

    def emit(name, depth=0):
        row = specs[name]
        parent = specs.get(row["parent"])
        origin = parent["head"] if parent else [0, 0, 0]
        offset = [(value - base) * height for value, base in zip(row["head"], origin)]
        indent = "  " * depth
        lines.extend(
            [
                indent + ("ROOT " if depth == 0 else "JOINT ") + mapping[name],
                indent + "{",
            ]
        )
        lines.append(indent + "  OFFSET " + " ".join(map(str, offset)))
        lines.append(
            indent
            + (
                "  CHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation"
                if depth == 0
                else "  CHANNELS 3 Zrotation Xrotation Yrotation"
            )
        )
        order.append(name)
        children = [key for key, value in specs.items() if value["parent"] == name]
        for child in children:
            emit(child, depth + 1)
        if not children:
            tail = [
                (end - start) * height for start, end in zip(row["head"], row["tail"])
            ]
            lines.extend(
                [
                    indent + "  End Site",
                    indent + "  {",
                    indent + "    OFFSET " + " ".join(map(str, tail)),
                    indent + "  }",
                ]
            )
        lines.append(indent + "}")

    emit("BODY_RIGID")
    lines.extend(["MOTION", f"Frames: {frames}", "Frame Time: 0.0333333333333333"])
    for frame in range(frames):
        values = [frame * 0.01, 0, 0, 0, 0, 0] + [0, 0, 0] * (len(order) - 1)
        lines.append(" ".join(map(str, values)))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_pipeline(root):
    """Exercise saved-file contracts and public atoms on a tiny rigid body fixture."""
    root = Path(root).resolve()
    if bpy.data.filepath or (root.exists() and any(root.iterdir())):
        raise ValueError("Use factory startup and a new empty test directory")
    root.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mesh = bpy.data.meshes.new("Fixture")
    mesh.from_pydata(
        [(-0.2, 0, 0), (0.2, 0, 0), (0.2, 0, 1), (-0.2, 0, 1)],
        [],
        [(0, 1, 2), (0, 2, 3)],
    )
    mesh.uv_layers.new(name="UVMap")
    surface = bpy.data.objects.new("Fixture", mesh)
    bpy.context.scene.collection.objects.link(surface)
    surface.select_set(True)
    bpy.context.view_layer.objects.active = surface
    glb, prepared = root / "original.glb", root / "prepared.blend"
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format="GLB")
    mesh_report = prepare_mesh(glb, prepared, height=1.8)
    calibration = profile()
    # Known fixture uses rigid body weighting so deformation expectations are exact.
    calibration.update(
        calibrated=True, weight_regions=[], part_rules=[], inspection_frame=10
    )
    bvh, cache = root / "source.bvh", root / "motion.npz"
    write_bvh(bvh, calibration)
    motion_report = cache_motion(bvh, cache, fps=30, scale=1, forward="-Y", up="Z")
    calibration["animations"] = [
        dict(
            name="FixtureMove",
            cache=cache.name,
            samples=[0, 5],
            loop=False,
            timeline_start=1,
            ground=False,
        )
    ]
    profile_path = root / "profile.json"
    profile_path.write_text(json.dumps(calibration), encoding="utf-8")
    exported = root / "weights-input.npz"
    build_character(prepared, profile_path, export_weight_input=exported)
    weights = root / "weights.npz"
    solve_report = solve_archive(exported, weights, 0.035, 0.025, 0.00003)
    calibration["weights_npz"] = weights.name
    profile_path.write_text(json.dumps(calibration), encoding="utf-8")
    candidate = root / "candidate.blend"
    manifest = build_character(prepared, profile_path, candidate)
    bpy.ops.wm.open_mainfile(filepath=str(candidate))
    rig = bpy.data.objects[manifest["rig"]]
    report = validate("CharacterParts", rig, range(1, 6), 1.8)
    assert report["pass"], report
    assert manifest["actions"] == ["FixtureMove"]
    assert len(rig.animation_data.nla_tracks[0].strips) == 1
    bpy.context.scene.frame_set(1)
    first = rig.pose.bones["root"].location.copy()
    bpy.context.scene.frame_set(5)
    assert (rig.pose.bones["root"].location - first).length > 0.02
    result = dict(
        passed=True,
        mesh=mesh_report,
        motion=motion_report,
        solver=solve_report,
        manifest=manifest,
        deformation=report,
    )
    (root / "pipeline-regression.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--python-packages", type=Path, required=True)
    options = parser.parse_args(argv)
    sys.path.append(str(options.python_packages))
    report = run_pipeline(options.work_dir)
    print(
        "PIPELINE_REGRESSION",
        json.dumps(
            {
                "passed": report["passed"],
                "frames": report["deformation"]["frames_checked"],
            }
        ),
    )


if __name__ == "__main__":
    main()
