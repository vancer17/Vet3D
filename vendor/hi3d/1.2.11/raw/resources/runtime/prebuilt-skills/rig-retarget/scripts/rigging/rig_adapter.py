"""Inspect/calibrate an existing rig, cache evaluated motion, and bake a mapped action."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
from .blend_common import (
    open_input,
    write_json,
    inventory,
    digest,
    curves,
    linked_actions,
)
from .io_utils import file_digest
from .retarget_math import rigid_matrices, retarget_samples
from .service_rig import preserved_signature


def selected_rig(name):
    rig = bpy.data.objects.get(name)
    if rig is None or rig.type != "ARMATURE":
        raise ValueError("Select an existing Armature by object name")
    return rig


def skeleton(rig):
    names = [b.name for b in rig.data.bones]
    return {
        "names": names,
        "parents": np.array(
            [names.index(b.parent.name) if b.parent else -1 for b in rig.data.bones]
        ),
        "rest": np.array([b.matrix_local for b in rig.data.bones]),
        "heads": np.array([b.head_local for b in rig.data.bones]),
        "tails": np.array([b.tail_local for b in rig.data.bones]),
    }


def skeleton_digest(data):
    return digest(
        {
            "names": list(data["names"]),
            "parents": np.asarray(data["parents"]).tolist(),
            "rest": np.asarray(data["rest"]).tolist(),
        }
    )


def protected_assets():
    """Geometry, UV, shape keys, material slots, all groups and image content."""
    images = {}
    for im in bpy.data.images:
        if im.source == "GENERATED":
            pixels = np.empty(len(im.pixels), np.float32)
            im.pixels.foreach_get(pixels)
            images[im.name] = hashlib.sha256(pixels.tobytes()).hexdigest()
        elif im.packed_file:
            images[im.name] = hashlib.sha256(im.packed_file.data).hexdigest()
        elif im.source == "FILE" and im.filepath:
            images[im.name] = file_digest(
                bpy.path.abspath(im.filepath, library=im.library)
            )
        elif im.source not in ["VIEWER"]:
            raise ValueError(
                "Image type needs an explicit content-preservation adapter: " + im.name
            )
    meshes = {}
    for o in bpy.context.scene.objects:
        if o.type != "MESH" or not len(o.data.polygons):
            continue
        row = preserved_signature(o, [g.name for g in o.vertex_groups])
        # Bone-parented props must move with the new action. Preserve attachment
        # and local transforms instead of their evaluated world placement.
        row.pop("matrix_world")
        row["matrix_basis"] = np.array(o.matrix_basis).tolist()
        row["matrix_parent_inverse"] = np.array(o.matrix_parent_inverse).tolist()
        row["parent"] = [
            o.parent.name if o.parent else None,
            o.parent_type,
            o.parent_bone,
        ]
        meshes[o.name] = row
    return {"meshes": meshes, "images": images}


def require_preserved(before, frame):
    """Compare at the same scene time; restore the intended preview frame."""
    scene = bpy.context.scene
    current = (scene.frame_current, scene.frame_subframe)
    try:
        scene.frame_set(frame[0], subframe=frame[1])
        if protected_assets() != before:
            raise ValueError(
                "Protected mesh, UV, weights, attachments or textures changed"
            )
    finally:
        scene.frame_set(current[0], subframe=current[1])


def validate_target(rig, replace_animation=False):
    rigid_matrices(np.array(rig.matrix_world), "target world")
    if (
        rig.parent
        or rig.constraints
        or (rig.animation_data and rig.animation_data.drivers)
    ):
        raise ValueError(
            "Target object parents, constraints or drivers need an explicit baking adapter"
        )
    if any(
        p.constraints
        or p.bone.inherit_scale != "FULL"
        or not p.bone.use_inherit_rotation
        or not p.bone.use_local_location
        for p in rig.pose.bones
    ):
        raise ValueError(
            "Target requires normal FK inheritance and no pose constraints"
        )
    if rig.data.users > 1:
        raise ValueError("Make the target armature data single-user before adapting it")
    ad = rig.animation_data
    if ad and (ad.action or ad.nla_tracks) and not replace_animation:
        raise ValueError(
            "Existing animation: explicitly choose replacement in a new candidate"
        )
    if rig.data.animation_data:
        raise ValueError("Animated armature data requires an explicit adapter")
    for action in linked_actions(rig):
        for c in curves(action):
            if not c.data_path.startswith("pose.bones["):
                raise ValueError(
                    "Object animation must be baked/isolated before target replacement"
                )


def calibrate_axes(rig, spec, replace_animation=False):
    """Set explicit tails/roll only, preserving heads; reject stale or animated input."""
    data = skeleton(rig)
    if spec.get("calibrated") is not True or spec.get("rig_sha256") != skeleton_digest(
        data
    ):
        raise ValueError("Calibration must match the inspected skeleton fingerprint")
    validate_target(rig, replace_animation)
    rows = spec["bones"]
    if not rows:
        raise ValueError("No calibrated bone edits supplied")
    for n, row in rows.items():
        if n not in data["names"]:
            raise ValueError("Unknown calibration bone")
        head = Vector(data["heads"][data["names"].index(n)])
        if "tail_at" in row:
            tail = Vector(data["heads"][data["names"].index(row["tail_at"])])
        else:
            tail = Vector(row["tail"])
        axis = Vector(row["roll_axis"])
        if (
            not np.isfinite([*tail, *axis]).all()
            or (tail - head).length < 1e-8
            or axis.cross(tail - head).length < 1e-8
        ):
            raise ValueError("Nondegenerate tail and nonparallel roll axis required")
    if replace_animation:
        rig.animation_data_clear()
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        for n, row in rows.items():
            b = rig.data.edit_bones[n]
            b.tail = (
                rig.data.edit_bones[row["tail_at"]].head.copy()
                if "tail_at" in row
                else Vector(row["tail"])
            )
            b.align_roll(Vector(row["roll_axis"]))
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
    after = skeleton(rig)
    if not np.allclose(after["heads"], data["heads"], atol=1e-7, rtol=0):
        raise ValueError("Joint heads changed during axis calibration")
    return {
        "before_rig_sha256": skeleton_digest(data),
        "after_rig_sha256": skeleton_digest(after),
        "joint_heads_preserved": True,
        "edited_bones": list(rows),
    }


def cache_rig(rig, frames):
    """Evaluate source IK/NLA/object motion into a fixed first-frame rig space."""
    if not frames or not all(math.isfinite(f) for f in frames):
        raise ValueError("Nonempty finite frames required")
    if rig.data.pose_position != "POSE" or not rig.visible_get():
        raise ValueError("Source rig must be visible and in Pose Position")
    scene = bpy.context.scene
    original = (scene.frame_current, scene.frame_subframe)
    data = skeleton(rig)
    poses = []
    anchor = None
    try:
        for f in frames:
            base = math.floor(f)
            scene.frame_set(base, subframe=f - base)
            ev = rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
            if anchor is None:
                anchor = rigid_matrices(np.array(ev.matrix_world), "source world")
            transform = np.linalg.inv(anchor) @ np.array(ev.matrix_world)
            poses.append(
                [transform @ np.array(ev.pose.bones[n].matrix) for n in data["names"]]
            )
    finally:
        scene.frame_set(original[0], subframe=original[1])
    data["poses"] = rigid_matrices(poses, "source poses")
    data["sample_frames"] = np.array(frames)
    data["source_world_at_first_sample"] = anchor
    data["source_fps"] = scene.render.fps / scene.render.fps_base
    return data


def bake_action(rig, names, quaternions, locations, root, frame_start, name):
    """Bulk-create one Blender 5.x Action with continuous quaternion signs."""
    if name in bpy.data.actions:
        raise ValueError("Choose a new Action name")
    if "slots" not in bpy.types.Action.bl_rna.properties:
        raise ValueError("This adapter requires Blender layered Action slots")
    count = len(quaternions)
    frames = np.arange(frame_start, frame_start + count, dtype=np.float32)
    rig.animation_data_clear()
    rig.data.pose_position = "POSE"
    for pb in rig.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
        pb.scale = (1, 1, 1)
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    slot = action.slots.new("OBJECT", rig.name)
    layer = action.layers.new("Retargeted motion")
    strip = layer.strips.new(type="KEYFRAME")
    bag = strip.channelbags.new(slot)
    rig.animation_data_create()
    rig.animation_data.action = action
    rig.animation_data.action_slot = slot
    linear = (
        bpy.types.Keyframe.bl_rna.properties["interpolation"].enum_items["LINEAR"].value
    )

    def channel(path, index, values):
        c = bag.fcurves.new(data_path=path, index=index)
        c.keyframe_points.add(count)
        c.keyframe_points.foreach_set("co", np.column_stack((frames, values)).ravel())
        c.keyframe_points.foreach_set("interpolation", np.full(count, linear, np.int32))
        c.update()

    for i, n in enumerate(names):
        path = rig.pose.bones[n].path_from_id("rotation_quaternion")
        for k in range(4):
            channel(path, k, quaternions[:, i, k])
    for k in range(3):
        channel(rig.pose.bones[root].path_from_id("location"), k, locations[:, k])
    return action


def new_path(value, forbidden=()):
    p = Path(value).expanduser().resolve()
    if p.exists() or p in [Path(x).expanduser().resolve() for x in forbidden]:
        raise ValueError("Use distinct new output/report paths")
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def execute(args):
    output = (
        new_path(args.output, [args.input, args.report])
        if getattr(args, "output", None)
        else None
    )
    report_path = new_path(args.report, [args.input])
    source = open_input(args.input)
    rig = selected_rig(args.rig)
    info = skeleton(rig)
    report = {
        "input_sha256": file_digest(source),
        "rig_sha256": skeleton_digest(info),
        "rig": rig.name,
    }
    if args.operation == "inspect":
        report.update({k: np.asarray(v).tolist() for k, v in info.items()})
        report["inventory"] = inventory()
        report["world_matrix"] = np.array(rig.matrix_world).tolist()
    elif args.operation == "cache":
        if args.end < args.start or min(args.fps, args.source_fps or 1) <= 0:
            raise ValueError("Valid fps and nonempty frame range required")
        source_fps = (
            args.source_fps
            or bpy.context.scene.render.fps / bpy.context.scene.render.fps_base
        )
        count = (
            int(math.floor((args.end - args.start) * args.fps / source_fps + 1e-8)) + 1
        )
        frames = (args.start + np.arange(count) * source_fps / args.fps).tolist()
        data = cache_rig(rig, frames)
        data["source_fps"] = source_fps
        data["fps"] = args.fps
        data["schema"] = "rig-retarget-cache-v1"
        data["input_sha256"] = report["input_sha256"]
        data["rig_sha256"] = report["rig_sha256"]
        with output.open("xb") as stream:
            np.savez_compressed(stream, **data)
        report.update(
            {
                "output": str(output),
                "frames": count,
                "source_frames": [frames[0], frames[-1]],
                "source_fps": source_fps,
                "fps": args.fps,
                "cache_sha256": file_digest(output),
            }
        )
    else:
        spec = json.loads(Path(args.spec).read_text())
        before = protected_assets()
        protected_frame = (
            bpy.context.scene.frame_current,
            bpy.context.scene.frame_subframe,
        )
        validate_target(rig, args.replace_animation)
        if args.operation == "calibrate":
            report.update(calibrate_axes(rig, spec, args.replace_animation))
        else:
            if spec.get("rig_sha256") != skeleton_digest(info):
                raise ValueError(
                    "Mapping fingerprint does not match this target rest skeleton"
                )
            with np.load(args.cache, allow_pickle=False) as archive:
                data = {k: archive[k] for k in archive.files}
            if data.get("schema", "") != "rig-retarget-cache-v1":
                raise ValueError(
                    "Use a rig_adapter cache with explicit hierarchy and space metadata"
                )
            if spec.get("cache_sha256") != file_digest(args.cache):
                raise ValueError("Mapping fingerprint does not match motion cache")
            quats, locs, details = retarget_samples(data, info, spec)
            bake_action(
                rig,
                info["names"],
                quats,
                locs,
                details["root"],
                args.frame_start,
                args.action,
            )
            scene = bpy.context.scene
            scene.frame_start = args.frame_start
            scene.frame_end = args.frame_start + len(quats) - 1
            fps = float(data["fps"])
            scene.render.fps = round(fps)
            scene.render.fps_base = round(fps) / fps
            scene.frame_set(args.frame_start)
            report.update(details)
            report["fps"] = fps
            report["frame_range"] = [scene.frame_start, scene.frame_end]
            report["cache_sha256"] = file_digest(args.cache)
        require_preserved(before, protected_frame)
        bpy.ops.file.pack_all()
        bpy.ops.wm.save_as_mainfile(filepath=str(output), compress=True)
        bpy.ops.wm.open_mainfile(filepath=str(output), use_scripts=False)
        require_preserved(before, protected_frame)
        report["saved_inventory"] = inventory()
        report["file_sha256"] = file_digest(output)
        report["output"] = str(output)
        report["protected_assets_preserved"] = True
        report["pose_qa_pending"] = True
    if file_digest(source) != report["input_sha256"]:
        raise ValueError("Source file changed")
    write_json(report_path, report)
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="operation", required=True)
    for name in ["inspect", "cache", "calibrate", "retarget"]:
        s = sub.add_parser(name)
        s.add_argument("--input", required=True)
        s.add_argument("--rig", required=True)
        s.add_argument("--report", required=True)
        if name != "inspect":
            s.add_argument("--output", required=True)
        if name == "cache":
            s.add_argument("--start", type=float, required=True)
            s.add_argument("--end", type=float, required=True)
            s.add_argument("--fps", type=float, required=True)
            s.add_argument("--source-fps", type=float)
        if name in ["calibrate", "retarget"]:
            s.add_argument("--spec", required=True)
            s.add_argument("--replace-animation", action="store_true")
        if name == "retarget":
            s.add_argument("--cache", required=True)
            s.add_argument("--action", required=True)
            s.add_argument("--frame-start", type=int, default=0)
    args = p.parse_args(argv)
    result = execute(args)
    print(
        json.dumps(
            {
                "operation": args.operation,
                "report": args.report,
                "output": result.get("output"),
                "pose_qa_pending": result.get("pose_qa_pending"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    main()
