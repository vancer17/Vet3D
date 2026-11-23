"""Build a calibrated rig, split/skin surfaces, retarget actions, and pack a .blend."""

import argparse
import json
import math
import sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Quaternion
from .blender_core import (
    create_rig,
    mesh_arrays,
    mesh_fingerprint,
    initial_weights,
    localized_solve,
    part_labels,
    split_bind,
)
from .motion import build_action
from .weight_graph import calibration_digest, file_digest


def resolve_weights(v, f, names, initial, profile, height, profile_dir):
    """Load a fingerprinted weight cache or solve current calibration in mesh units."""
    calibration_sha = calibration_digest(profile, height)
    solve_report = {}
    if profile.get("weights_npz"):
        d = np.load(profile_dir / profile["weights_npz"], allow_pickle=False)
        if (
            str(d["mesh_sha256"]) != mesh_fingerprint(v, f)
            or list(d["bone_names"]) != names
        ):
            raise ValueError("Cached weights target a different mesh or bone order")
        if str(d["calibration_sha256"]) != calibration_sha:
            raise ValueError("Cached weights target a different calibration")
        weights, fixed = d["weights"], d["fixed"]
        if (
            weights.shape != initial.shape
            or fixed.shape != (len(v),)
            or fixed.dtype != np.bool_
            or not np.isfinite(weights).all()
            or np.any(weights < 0)
            or not np.allclose(weights.sum(1), 1, atol=1e-7, rtol=0)
        ):
            raise ValueError("Invalid cached weights")
        if not np.array_equal(weights[fixed], initial[fixed]):
            raise ValueError("Cached rigid anchors changed")
        solve_report = {
            "external_weights_npz": profile["weights_npz"],
            "weights_sha256": file_digest(profile_dir / profile["weights_npz"]),
            "calibration_sha256": calibration_sha,
        }
    else:
        solve = profile.get("solver", {})
        weights, fixed = localized_solve(
            v,
            f,
            initial,
            height * solve.get("radius", 0.0194),
            height * solve.get("fidelity_length", 0.0139),
            height * solve.get("edge_floor", 0.0000167),
            method=solve.get("method", "direct"),
            rtol=solve.get("rtol", 2e-6),
            maxiter=solve.get("maxiter", 1500),
            diagnostics=solve_report,
        )
    return weights, fixed, solve_report


def resolve_labels(v, f, profile, height, profile_dir):
    """Derive calibrated part labels or validate labels against the exact mesh."""
    labels = part_labels(v, f, profile, height)
    if profile.get("labels_npz"):
        d = np.load(profile_dir / profile["labels_npz"], allow_pickle=False)
        if str(d["mesh_sha256"]) != mesh_fingerprint(v, f):
            raise ValueError("Part labels target a different mesh")
        labels = d["labels"]
        if len(labels) != len(f):
            raise ValueError("Part label count mismatch")
    return labels


def sequence_actions(rig, profile, profile_dir):
    """Bake all actions before creating NLA strips and an inspection frame outside them."""
    # Create every action before adding NLA, so strips cannot contaminate later baking.
    actions = [
        (spec, build_action(rig, spec, profile, profile_dir))
        for spec in profile.get("animations", [])
    ]
    rig.animation_data_create()
    rig.animation_data.action = None
    track = rig.animation_data.nla_tracks.new()
    track.name = "CharacterPerformance"
    scene = bpy.context.scene
    scene.render.fps = int(profile.get("fps", 30))
    end_frame = 1
    for spec, action in actions:
        strip = track.strips.new(spec["name"], int(spec["timeline_start"]), action)
        strip.repeat = float(spec.get("repeat", 1))
        strip.extrapolation = "NOTHING"
        strip.blend_type = "REPLACE"
        end_frame = max(end_frame, math.ceil(strip.frame_end))
        scene.timeline_markers.new(spec["name"], frame=int(strip.frame_start))
    inspection = int(profile.get("inspection_frame", end_frame + 10))
    if any(s.frame_start <= inspection <= s.frame_end for s in track.strips):
        raise ValueError("Inspection frame must lie outside animation strips")
    scene.frame_start = 1
    scene.frame_end = max(end_frame, inspection)
    scene.frame_set(inspection)
    return scene, track, actions, inspection


def configure_inspection(rig, parts, height, profile, scene, track, inspection):
    """Show weighted bones and write editable in-file delivery/provenance notes."""
    # Traverse deform memberships once, rather than rescanning the entire mesh for each bone.
    used = set()
    for ob in parts:
        group_names = {g.index: g.name for g in ob.vertex_groups}
        for vertex in ob.data.vertices:
            used.update(group_names[g.group] for g in vertex.groups if g.weight > 0)
    for b in rig.data.bones:
        b.hide = b.name not in used and b.name != profile.get("root_bone", "root")
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="POSE")
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                space = area.spaces.active
                space.shading.type = "SOLID"
                space.overlay.show_overlays = True
                region = space.region_3d
                region.view_perspective = "ORTHO"
                region.view_rotation = Quaternion(
                    (math.sqrt(0.5), math.sqrt(0.5), 0, 0)
                )
                region.view_location = (0, 0, height / 2)
                region.view_distance = height * 1.5
    text = bpy.data.texts.new("START_HERE")
    text.write(
        "CHARACTER DELIVERY\n\nInspection frame: "
        + str(inspection)
        + "\nFPS: "
        + str(scene.render.fps)
        + "\n"
    )
    for strip in track.strips:
        text.write(f"{strip.name}: {strip.frame_start:g}–{strip.frame_end:g}\n")
    text.write(
        "\nOriginal master geometry is retained separately. Surface splitting does not reconstruct hidden anatomy.\n"
    )
    text.write(
        "\nMotion provenance:\n"
        + json.dumps(profile.get("provenance", []), ensure_ascii=False, indent=2)
    )
    return used


def build_character(
    input_path,
    profile_path,
    output_path=None,
    export_weight_input=None,
    python_packages=None,
):
    """Compose calibrated rigging, skinning, animation and candidate delivery."""
    input_path, profile_path = Path(input_path), Path(profile_path)
    output_path = Path(output_path) if output_path is not None else None
    export_weight_input = (
        Path(export_weight_input) if export_weight_input is not None else None
    )
    if (output_path is None) == (export_weight_input is None):
        raise ValueError("Specify exactly one output blend or weight-input archive")
    if python_packages:
        sys.path.append(str(python_packages))
    destination = output_path or export_weight_input
    if destination.exists():
        raise ValueError("Use a new candidate output path")
    profile = json.loads(profile_path.read_text())
    if not profile.get("calibrated"):
        raise ValueError(
            "Fit and inspect the profile against this character before building"
        )
    bpy.ops.wm.open_mainfile(filepath=str(input_path))
    surfaces = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if len(surfaces) != 1:
        raise ValueError("Expected one prepared unified surface")
    surface = surfaces[0]
    if not surface.get("welded_before_weights"):
        raise ValueError("Prepare/weld the working mesh first")
    height = float(surface["character_height_m"])
    v, f = mesh_arrays(surface)
    rig = create_rig(profile["bones"], height)
    names = [b.name for b in rig.data.bones if b.use_deform]
    initial = initial_weights(v, names, profile, height)
    calibration_sha = calibration_digest(profile, height)
    if export_weight_input:
        export_weight_input.parent.mkdir(parents=True, exist_ok=True)
        with export_weight_input.open("wb") as stream:
            np.savez_compressed(
                stream,
                vertices=v,
                faces=f,
                initial=initial,
                bone_names=np.array(names),
                mesh_sha256=mesh_fingerprint(v, f),
                calibration_sha256=calibration_sha,
            )
        print("WEIGHT_INPUT_EXPORTED", str(export_weight_input))
        return {"weight_input": str(export_weight_input)}
    weights, fixed, solve_report = resolve_weights(
        v, f, names, initial, profile, height, profile_path.parent
    )
    labels = resolve_labels(v, f, profile, height, profile_path.parent)
    parts = split_bind(
        surface, rig, names, weights, labels, profile.get("rigid_parts", {})
    )
    scene, track, actions, inspection = sequence_actions(
        rig, profile, profile_path.parent
    )
    used = configure_inspection(rig, parts, height, profile, scene, track, inspection)
    bpy.ops.file.pack_all()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    manifest = {
        "mesh_sha256": mesh_fingerprint(v, f),
        "parts": [o.name for o in parts],
        "rig": rig.name,
        "faces": int(len(f)),
        "weighted_bones": len(used),
        "rigid_anchor_vertices": int(fixed.sum()),
        "actions": [a.name for _, a in actions],
        "inspection_frame": inspection,
        "fps": scene.render.fps,
        "provenance": profile.get("provenance", []),
        "solver": solve_report,
    }
    output_path.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--profile", type=Path, required=True)
    destination = p.add_mutually_exclusive_group(required=True)
    destination.add_argument("--output", type=Path)
    destination.add_argument(
        "--export-weight-input",
        type=Path,
        help="Export NPZ for an external SciPy solve; no blend is saved",
    )
    p.add_argument(
        "--python-packages",
        type=Path,
        help="Optional SciPy site-packages matching Blender Python ABI",
    )
    a = p.parse_args(argv)
    result = build_character(
        a.input, a.profile, a.output, a.export_weight_input, a.python_packages
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
