"""BVH cache retargeting and palm-axis correction for every action."""

import math
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector
from .blend_common import curves as fcurves


def hand_offset(style, side, index, period):
    sign = 1 if side == "L" else -1
    phase = 2 * math.pi * index / max(period, 1) + (0 if side == "L" else math.pi)
    flex, dev = 4.0, 1.0
    if style == "run":
        flex, dev = 5 + 2 * math.sin(phase - 0.45), 1.5 + math.sin(phase - 0.8)
    elif style == "dance":
        # Original palm/wrist phrase, not a replacement for full-body mocap.
        poses = [
            (5, -3),
            (-14, 5),
            (8, -6),
            (-20, 6),
            (6, -4),
            (-12, 4),
            (12, -6),
            (-18, 5),
            (3, 0),
            (25, 3),
            (-23, -3),
            (5, 0),
            (21, -4),
            (-20, 4),
            (4, 0),
            (15, -3),
            (-10, 4),
            (8, -6),
            (-19, 6),
            (4, 0),
            (15, -6),
            (-22, 5),
            (6, -3),
            (-10, 2),
            (5, 0),
        ]
        x = max(
            0.0, min(24.0, index / max(period, 1) * 24 - (0 if side == "L" else 0.55))
        )
        a = min(23, int(x))
        t = x - a
        t = t**3 * (10 - 15 * t + 6 * t * t)
        flex, dev = np.array(poses[a]) * (1 - t) + np.array(poses[a + 1]) * t
    return Quaternion((1, 0, 0), math.radians(sign * dev)) @ Quaternion(
        (0, 0, 1), math.radians(-sign * flex)
    )


def ground_height(rig, collection_name="CharacterParts"):
    """Lowest evaluated mesh vertex in rig space; the ground plane is rig Z=0."""
    collection = bpy.data.collections.get(collection_name)
    if collection is None:
        raise ValueError("Missing character parts collection: " + collection_name)
    deps = bpy.context.evaluated_depsgraph_get()
    world_to_rig = rig.matrix_world.inverted()
    low = float("inf")
    for ob in collection.all_objects:
        if ob.type != "MESH":
            continue
        evaluated = ob.evaluated_get(deps)
        mesh = evaluated.to_mesh()
        try:
            if mesh is None or not len(mesh.vertices):
                continue
            coords = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
            mesh.vertices.foreach_get("co", coords)
            transform = world_to_rig @ evaluated.matrix_world
            # Only the Z row is needed, including local object translation.
            z = coords.reshape(-1, 3) @ np.array(transform[2][:3]) + transform[2][3]
            low = min(low, float(z.min()))
        finally:
            evaluated.to_mesh_clear()
    if not math.isfinite(low):
        raise ValueError(
            "Character parts collection has no evaluated vertices: " + collection_name
        )
    return low


def build_action(rig, spec, profile, config_dir):
    cache = Path(config_dir) / spec["cache"]
    data = np.load(cache, allow_pickle=False)
    names = data["names"].tolist()
    poses = data["poses"]
    source_rest = data["rest"]
    fps = int(data["fps"])
    if fps != int(profile.get("fps", 30)):
        raise ValueError("Resample BVH cache to the output fps first")
    start, end = spec["samples"]  # zero-based, end exclusive
    if not 0 <= start < end <= len(poses):
        raise ValueError("Cache sample range invalid")
    records = range(start, end)
    mapping = profile["motion_map"]
    if any(source not in names for source in mapping.values()):
        raise ValueError("Motion mapping contains missing source bones")
    bones = list(rig.data.bones)
    rest = {b.name: b.matrix_local.to_quaternion() for b in bones}
    source_q = {
        n: Matrix(source_rest[names.index(n)].tolist()).to_quaternion() for n in names
    }
    body = profile.get("body_bone", "BODY_RIGID")
    root = profile.get("root_bone", "root")
    source_body = mapping[body]
    # Scale by corresponding leg chain lengths, not source file unit guesses.
    leg = ["thigh.L", "shin.L", "foot.L"]
    length_source = sum(
        np.linalg.norm(
            source_rest[names.index(mapping[b]), :3, 3]
            - source_rest[names.index(mapping[a]), :3, 3]
        )
        for a, b in zip(leg, leg[1:])
    )
    length_target = sum(rig.data.bones[n].length for n in leg[:2])
    if length_source < 1e-6:
        raise ValueError("Degenerate source leg lengths")
    scale = length_target / length_source
    body_positions = poses[start:end, names.index(source_body), :3, 3]
    base = body_positions[0].copy()
    median_z = np.median(body_positions[:, 2])
    ground_mode = spec.get("ground", "source_flight" if spec.get("loop") else True)
    source_feet = [n for n in ["LeftToeBase", "RightToeBase"] if n in names]
    if len(source_feet) != 2:
        source_feet = [mapping["foot.L"], mapping["foot.R"]]
    foot_lows = np.minimum(
        poses[start:end, names.index(source_feet[0]), 2, 3],
        poses[start:end, names.index(source_feet[1]), 2, 3],
    )
    source_floor = float(np.percentile(foot_lows, 12))
    action = bpy.data.actions.new(spec["name"])
    action.use_fake_user = True
    rig.animation_data_create()
    rig.animation_data.action = action
    bpy.context.scene.render.fps = fps
    previous = {}
    for step, index in enumerate(records):
        desired = {root: rest[root]}
        for bone in bones:
            n = bone.name
            if n in mapping:
                source = mapping[n]
                q = Matrix(poses[index, names.index(source)].tolist()).to_quaternion()
                desired[n] = q @ source_q[source].inverted() @ rest[n]
            elif n != root:
                parent = bone.parent.name
                desired[n] = desired[parent] @ rest[parent].inverted() @ rest[n]
        # Rigid torso is one bone. No artificial spine curvature is introduced.
        for n, amount in profile.get("rotation_factors", {}).items():
            neutral = desired[body] @ rest[body].inverted() @ rest[n]
            desired[n] = neutral.slerp(desired[n], float(amount))
        for side in ["L", "R"]:
            h, fore = "hand." + side, "forearm." + side
            if h in desired and fore in desired:
                # BVH Hand may be zero-length and point vertically. Its Y axis is
                # not the palm axis. Build the actual palm relative to the forearm.
                desired[h] = desired[fore] @ hand_offset(
                    spec.get("hand_style", "neutral"),
                    side,
                    step,
                    end - start if spec.get("loop") else end - start - 1,
                )
        frame = step + 1
        bpy.context.scene.frame_set(frame)
        for bone in bones:
            n = bone.name
            p = bone.parent.name if bone.parent else None
            q = (
                rest[n].inverted()
                @ (rest[p] @ desired[p].inverted() if p else Quaternion())
                @ desired[n]
            )
            if n in previous and q.dot(previous[n]) < 0:
                q.negate()
            previous[n] = q.copy()
            rig.pose.bones[n].rotation_quaternion = q
            rig.pose.bones[n].location = (0, 0, 0)
        displacement = Vector(body_positions[step] - base) * scale
        displacement.z = 0
        if spec.get("in_place", spec.get("loop", False)):
            displacement.x = displacement.y = 0
        rig.pose.bones[root].location = rest[root].inverted() @ displacement
        dz = float(body_positions[step, 2] - median_z) * scale
        rig.pose.bones[body].location = rest[body].inverted() @ Vector((0, 0, dz))
        bpy.context.view_layer.update()
        if ground_mode:
            # Actual bound vertices include heels/toes. Floor correction is an
            # optional grounded preset; source_flight retains captured flight height.
            low = ground_height(rig, profile.get("parts_collection", "CharacterParts"))
            flight = (
                max(0.0, float(foot_lows[step] - source_floor) * scale)
                if ground_mode == "source_flight"
                else 0.0
            )
            rig.pose.bones[body].location += rest[body].inverted() @ Vector(
                (0, 0, -low + flight)
            )
        for pb in rig.pose.bones:
            pb.keyframe_insert("rotation_quaternion", frame=frame, group=pb.name)
            if pb.name in {root, body}:
                pb.keyframe_insert("location", frame=frame, group=pb.name)
    if spec.get("loop"):
        count = end - start
        # Close residual capture mismatch over a configured short tail window.
        window = min(int(spec.get("loop_blend_frames", 4)), count // 3)
        channels = fcurves(action)
        first = {(c.data_path, c.array_index): c.evaluate(1) for c in channels}
        for c in channels:
            for k in c.keyframe_points:
                frame = int(k.co.x)
                if frame > count - window and window:
                    t = (frame - (count - window)) / (window + 1)
                    k.co.y = k.co.y * (1 - t) + first[c.data_path, c.array_index] * t
            c.keyframe_points.insert(count + 1, first[c.data_path, c.array_index])
    for curve in fcurves(action):
        for key in curve.keyframe_points:
            key.interpolation = "LINEAR"
        curve.update()
    return action
