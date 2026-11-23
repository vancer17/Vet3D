"""Inspect, clip, orient, or edit text in a local Blender scene. Run via Blender --python."""

import argparse
import json
import math
from pathlib import Path
import bpy
from mathutils import Matrix, Vector
from rigging.blend_common import (
    curves,
    linked_actions,
    animation_hash,
    geometry_hash,
    open_input,
    inventory,
    save_candidate,
    write_json,
)


def selected_rigs(names):
    result = []
    for name in names:
        ob = bpy.data.objects.get(name)
        if not ob or ob.type != "ARMATURE":
            raise ValueError("Missing armature: " + name)
        result.append(ob)
    if len(set(result)) != len(result):
        raise ValueError("Duplicate rig selection")
    return result


def inspect(args):
    report = inventory()
    if args.rigs:
        if Vector(args.forward).length_squared < 1e-12:
            raise ValueError("Rest forward axis must be nonzero")
        report["headings"] = {}
        for fr in args.frames or [bpy.context.scene.frame_start]:
            bpy.context.scene.frame_set(fr)
            for rig in selected_rigs(args.rigs):
                b = rig.data.bones.get(args.head_bone)
                if not b:
                    raise ValueError("Missing heading bone: " + args.head_bone)
                delta = (
                    rig.pose.bones[b.name].matrix.to_quaternion()
                    @ b.matrix_local.to_quaternion().inverted()
                )
                forward = rig.matrix_world.to_3x3() @ (delta @ Vector(args.forward))
                report["headings"].setdefault(rig.name, []).append(
                    {"frame": fr, "world_forward": list(forward.normalized())}
                )
    write_json(args.report, report)
    return report


def orient(args):
    if not math.isfinite(args.degrees):
        raise ValueError("Rotation must be finite")
    rigs = selected_rigs(args.rigs)
    for rig in rigs:
        if (
            rig.parent
            or rig.constraints
            or (rig.animation_data and rig.animation_data.drivers)
        ):
            raise ValueError(
                "Orientation helper requires independent, unconstrained rigs; use an explicitly designed group pivot for this hierarchy"
            )
        if any(
            not c.data_path.startswith("pose.bones[")
            for a in linked_actions(rig)
            for c in curves(a)
        ):
            raise ValueError(
                "Rig object transform/property animation needs a group pivot, not static object rotation"
            )
        for ob in bpy.data.objects:
            if ob.type != "MESH" or not any(
                mod.type == "ARMATURE" and mod.object == rig for mod in ob.modifiers
            ):
                continue
            parent = ob.parent
            while parent and parent != rig:
                parent = parent.parent
            if parent != rig:
                raise ValueError("Bound mesh is outside the rig hierarchy: " + ob.name)
    g0, a0 = geometry_hash(), animation_hash()
    transforms = {}
    for rig in rigs:
        origin = rig.matrix_world.translation.copy()
        delta = (
            Matrix.Translation(origin)
            @ Matrix.Rotation(math.radians(args.degrees), 4, "Z")
            @ Matrix.Translation(-origin)
        )
        rig.matrix_world = delta @ rig.matrix_world
        transforms[rig.name] = [list(row) for row in delta]
    bpy.context.view_layer.update()
    assert geometry_hash() == g0 and animation_hash() == a0
    return {
        "operation": "orient",
        "degrees_z": args.degrees,
        "world_transforms": transforms,
        "geometry_uv_weights_rest_hash": g0,
        "animation_channels_hash": a0,
        "geometry_and_animation_channels_unchanged": True,
    }


def text_edit(args):
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    updates, removals = spec.get("set", []), spec.get("remove", [])
    names = [x["object"] for x in updates] + removals
    if len(set(names)) != len(names):
        raise ValueError("Conflicting or repeated text selectors")
    for name in names:
        ob = bpy.data.objects.get(name)
        if not ob or ob.type != "FONT":
            raise ValueError("Selector must name an existing text object: " + name)
    for edit in updates:
        if not isinstance(edit["text"], str) or edit.get("max_width", 1) <= 0:
            raise ValueError("Invalid text or max_width")
    g0, a0 = geometry_hash(), animation_hash()
    for edit in updates:
        ob = bpy.data.objects[edit["object"]]
        if ob.data.users > 1:
            ob.data = ob.data.copy()
        ob.data.body = edit["text"]
        bpy.context.view_layer.update()
        if edit.get("max_width") and ob.dimensions.x > edit["max_width"]:
            ob.data.size *= edit["max_width"] / ob.dimensions.x
    for name in removals:
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
    assert geometry_hash() == g0 and animation_hash() == a0
    return {
        "operation": "text",
        "edits": spec,
        "geometry_and_animation_channels_unchanged": True,
        "geometry_uv_weights_rest_hash": g0,
        "animation_channels_hash": a0,
    }


def clip(args):
    if args.source_end <= args.source_start:
        raise ValueError("Clip requires at least two inclusive source frames")
    rigs = selected_rigs(args.rigs)
    suffixes = (
        ".location",
        ".rotation_quaternion",
        ".rotation_euler",
        ".rotation_axis_angle",
        ".scale",
    )
    for rig in rigs:
        if rig.constraints or any(p.constraints for p in rig.pose.bones):
            raise ValueError(
                "Bake constraints/IK explicitly first; this helper copies evaluated unconstrained local poses"
            )
        if rig.animation_data and rig.animation_data.drivers:
            raise ValueError("Drivers require explicit visual baking")
        for action in linked_actions(rig):
            if any(
                not c.data_path.startswith("pose.bones[")
                or not c.data_path.endswith(suffixes)
                for c in curves(action)
            ):
                raise ValueError(
                    "Clip helper only replaces pose transform channels: " + action.name
                )
    stage = []
    for name in args.stage_actions:
        a = bpy.data.actions.get(name)
        if not a:
            raise ValueError("Missing stage action: " + name)
        if a in [x for rig in rigs for x in linked_actions(rig)]:
            raise ValueError("Stage action overlaps selected rig action")
        if a.users > 1 + int(a.use_fake_user):
            raise ValueError(
                "Stage action is shared; make its scope explicit before editing"
            )
        stage.append(a)
    n = args.source_end - args.source_start + 1
    end = args.start + n - 1
    s = bpy.context.scene
    if (
        args.start < s.bl_rna.properties["frame_start"].hard_min
        or end > s.bl_rna.properties["frame_end"].hard_max
    ):
        raise ValueError("Destination frame range exceeds scene limits")
    old = {a for rig in rigs for a in linked_actions(rig)}
    snapshots = {rig.name: [] for rig in rigs}
    # Sample every selected rig before changing any Action/NLA assignment.
    for frame in range(args.source_start, args.source_end + 1):
        s.frame_set(frame)
        for rig in rigs:
            snapshots[rig.name].append(
                {p.name: p.matrix_basis.copy() for p in rig.pose.bones}
            )
    lo = (
        args.stage_source_start
        if args.stage_source_start is not None
        else args.source_start
    )
    hi = args.stage_source_end if args.stage_source_end is not None else args.source_end
    if stage and hi <= lo:
        raise ValueError("Invalid stage source interval")
    stage_values = [
        (
            a,
            [
                (c, [c.evaluate(lo + i * (hi - lo) / (n - 1)) for i in range(n)])
                for c in curves(a)
            ],
        )
        for a in stage
    ]
    for rig in rigs:
        rig.animation_data_clear()
    for action in old:
        if action.users == int(action.use_fake_user):
            action.use_fake_user = False
            bpy.data.actions.remove(action)
    created = []
    for rig in rigs:
        a = bpy.data.actions.new(rig.name + "__clip")
        a.use_fake_user = True
        rig.animation_data_create()
        rig.animation_data.action = a
        previous = {}
        for i, sample in enumerate(snapshots[rig.name]):
            for name, mat in sample.items():
                p = rig.pose.bones[name]
                loc, q, scale = mat.decompose()
                if name in previous and q.dot(previous[name]) < 0:
                    q.negate()
                previous[name] = q.copy()
                p.rotation_mode = "QUATERNION"
                p.location, p.rotation_quaternion, p.scale = loc, q, scale
                for prop in ("location", "rotation_quaternion", "scale"):
                    p.keyframe_insert(prop, frame=args.start + i, group=name)
        for c in curves(a):
            for k in c.keyframe_points:
                k.interpolation = "LINEAR"
        rig.animation_data.action = None
        created.append((rig, a))
    for rig, a in created:
        track = rig.animation_data.nla_tracks.new()
        track.name = "Selected clip"
        strip = track.strips.new(a.name, args.start, a)
        strip.extrapolation = "NOTHING"
    for action, values in stage_values:
        for c, values in values:
            for mod in list(c.modifiers):
                c.modifiers.remove(mod)
            c.keyframe_points.clear()
            c.keyframe_points.add(n)
            for i, value in enumerate(values):
                c.keyframe_points[i].co = (args.start + i, value)
                c.keyframe_points[i].interpolation = "LINEAR"
            c.update()
    # Timeline is scene-wide; unselected animations are reported, never silently deleted.
    s.frame_start, s.frame_end = args.start, end
    s.use_preview_range = True
    s.frame_preview_start, s.frame_preview_end = args.start, end
    if args.rebase_markers:
        for marker in list(s.timeline_markers):
            if args.source_start <= marker.frame <= args.source_end:
                marker.frame += args.start - args.source_start
            else:
                s.timeline_markers.remove(marker)
    s.frame_set(args.start)
    return {
        "operation": "clip",
        "source_frames_inclusive": [args.source_start, args.source_end],
        "output_frames_inclusive": [args.start, end],
        "samples": n,
        "rigs": args.rigs,
        "stage_actions": args.stage_actions,
        "unselected_animation": "Retained; inspect the saved inventory before declaring a whole-scene cleanup",
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="op", required=True)
    for name in ("inspect", "orient", "text", "clip"):
        q = sub.add_parser(name)
        q.add_argument("--input", required=True)
        q.add_argument("--report", required=name == "inspect")
        if name != "inspect":
            q.add_argument("--output", required=True)
            q.add_argument("--pack", action="store_true")
        if name in ("inspect", "orient", "clip"):
            q.add_argument("--rigs", nargs="+", required=name != "inspect")
        if name == "inspect":
            q.add_argument("--frames", nargs="+", type=int)
            q.add_argument("--head-bone", default="head")
            q.add_argument("--forward", nargs=3, type=float, default=(0, -1, 0))
        elif name == "orient":
            q.add_argument("--degrees", required=True, type=float)
        elif name == "text":
            q.add_argument("--spec", required=True)
        elif name == "clip":
            q.add_argument("--source-start", required=True, type=int)
            q.add_argument("--source-end", required=True, type=int)
            q.add_argument("--start", default=0, type=int)
            q.add_argument("--stage-actions", nargs="*", default=[])
            q.add_argument("--stage-source-start", type=float)
            q.add_argument("--stage-source-end", type=float)
            q.add_argument("--rebase-markers", action="store_true")
    a = p.parse_args(argv)
    open_input(a.input, getattr(a, "output", None))
    report = {"inspect": inspect, "orient": orient, "text": text_edit, "clip": clip}[
        a.op
    ](a)
    if a.op != "inspect":
        save_candidate(a, report)
    print(json.dumps({"operation": a.op, "complete": True}))


if __name__ == "__main__":
    main()
