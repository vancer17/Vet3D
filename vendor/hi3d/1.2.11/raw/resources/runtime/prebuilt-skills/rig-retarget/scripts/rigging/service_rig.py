"""Local Blender handoff for auto-rig: export, bind, inspect and repair. No network."""

import argparse
import hashlib
import json
from pathlib import Path
import bpy
import numpy as np
from .io_utils import atomic_json, file_digest
from .weight_graph import mesh_digest
from .skin_weights import check_weights, repair_regions, stretch_metrics
from .validate_blend import parse_frames


def surface(obj):
    """Read base vertices and loop-triangulated indices without editing topology."""
    if obj.type != "MESH" or not len(obj.data.polygons):
        raise ValueError("Expected a nonempty mesh surface")
    mesh = obj.data
    v = np.empty(len(mesh.vertices) * 3, np.float32)
    mesh.vertices.foreach_get("co", v)
    if not np.isfinite(v).all():
        raise ValueError("Mesh contains nonfinite coordinates")
    mesh.calc_loop_triangles()
    f = np.empty(len(mesh.loop_triangles) * 3, np.int32)
    mesh.loop_triangles.foreach_get("vertices", f)
    return v.reshape(-1, 3), f.reshape(-1, 3)


def skin_table(obj, rig):
    """Dense N x deform-bones table; non-bone groups are excluded and untouched."""
    names = [b.name for b in rig.data.bones if b.use_deform]
    lookup = {
        g.index: names.index(g.name) for g in obj.vertex_groups if g.name in names
    }
    weights = np.zeros((len(obj.data.vertices), len(names)), np.float32)
    for v in obj.data.vertices:
        for group in v.groups:
            if group.group in lookup:
                weights[v.index, lookup[group.group]] = group.weight
    return names, check_weights(weights)


def rig_digest(obj, rig):
    """Bind matrices and hierarchy expressed in the mesh's local coordinate system."""
    relative = obj.matrix_world.inverted() @ rig.matrix_world
    values = [
        (
            b.name,
            b.parent.name if b.parent else None,
            b.use_deform,
            [list(row) for row in relative @ b.matrix_local],
        )
        for b in rig.data.bones
    ]
    return hashlib.sha256(
        json.dumps(values, separators=(",", ":")).encode()
    ).hexdigest()


def write_changed_weights(obj, names, before, after):
    """Write changed rows only; callers must supply the matching object/bone order."""
    check_weights(before)
    check_weights(after)
    if before.shape != after.shape or after.shape != (
        len(obj.data.vertices),
        len(names),
    ):
        raise ValueError("Weight dimensions do not match object and bones")
    rows = np.flatnonzero(np.any(before != after, axis=1))
    if len(rows):
        if obj.data.users > 1:
            obj.data = obj.data.copy()
        for j, name in enumerate(names):
            group = obj.vertex_groups.get(name)
            if group is None:
                if not np.any(after[rows, j]):
                    continue
                group = obj.vertex_groups.new(name=name)
            # Preserve existing deform-entry order: DQ hemisphere selection can
            # depend on accumulation order for widely separated rotations.
            removed = rows[(before[rows, j] > 0) & (after[rows, j] == 0)]
            if len(removed):
                group.remove(removed.tolist())
            for i in rows[(after[rows, j] > 0) & (after[rows, j] != before[rows, j])]:
                group.add([int(i)], float(after[i, j]), "REPLACE")
    return len(rows)


def preserved_signature(obj, groups=()):
    """Geometry, corner UV/material slots, transforms and nominated protected groups."""
    mesh = obj.data
    v, _ = surface(obj)
    loops = np.empty(len(mesh.loops), np.int32)
    mesh.loops.foreach_get("vertex_index", loops)
    h = hashlib.sha256(v.tobytes() + loops.tobytes())
    values = np.empty(len(mesh.polygons), np.int32)
    for field in ["loop_start", "loop_total", "material_index"]:
        mesh.polygons.foreach_get(field, values)
        h.update(values.tobytes())
    for layer in mesh.uv_layers:
        uv = np.empty(len(layer.data) * 2, np.float32)
        layer.data.foreach_get("uv", uv)
        h.update(layer.name.encode())
        h.update(uv.tobytes())
    if mesh.shape_keys:
        for key in mesh.shape_keys.key_blocks:
            co = np.empty(len(key.data) * 3, np.float32)
            key.data.foreach_get("co", co)
            h.update(key.name.encode())
            h.update(co.tobytes())
    indices = {obj.vertex_groups[n].index for n in groups}
    if indices:
        for vertex in mesh.vertices:
            for g in vertex.groups:
                if g.group in indices:
                    h.update(
                        f"{vertex.index}:{obj.vertex_groups[g.group].name}:{g.weight!r};".encode()
                    )
    return dict(
        data_sha256=h.hexdigest(),
        materials=[m.name if m else None for m in mesh.materials],
        matrix_world=[list(row) for row in obj.matrix_world],
    )


def export_body(obj, output, faces=None):
    """Export one base/rest mesh copy in world space; optional submission-only decimation."""
    if (
        obj.type != "MESH"
        or not len(obj.data.polygons)
        or (faces is not None and faces < 4)
    ):
        raise ValueError("Nonempty mesh and optional face budget >= 4 required")
    target = Path(output)
    if target.exists() or target.suffix.lower() != ".glb":
        raise ValueError("Use a new .glb output")
    selected = list(bpy.context.selected_objects)
    active = bpy.context.view_layer.objects.active
    copy = bpy.data.objects.new("AutoRig submission", obj.data.copy())
    bpy.context.scene.collection.objects.link(copy)
    copy.matrix_world = obj.matrix_world.copy()
    try:
        if copy.data.shape_keys:
            copy.shape_key_clear()
        bpy.ops.object.select_all(action="DESELECT")
        copy.select_set(True)
        bpy.context.view_layer.objects.active = copy
        _, f = surface(copy)
        if faces is not None and len(f) > faces:
            mod = copy.modifiers.new("Submission proxy", "DECIMATE")
            mod.ratio = faces / len(f)
            bpy.ops.object.modifier_apply(modifier=mod.name)
        target.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.export_scene.gltf(
            filepath=str(target),
            export_format="GLB",
            use_selection=True,
            export_animations=False,
            export_skins=False,
            export_morph=False,
        )
        return dict(
            mesh=str(target),
            sha256=file_digest(target),
            triangles=len(surface(copy)[1]),
            source_object=obj.name,
            base_mesh_only=True,
        )
    finally:
        mesh = copy.data
        bpy.data.objects.remove(copy, do_unlink=True)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        for ob in selected:
            ob.select_set(True)
        bpy.context.view_layer.objects.active = active


def bind_result(glb, body, targets, alignment_tolerance):
    """Import one service skin and transfer by nearest-face interpolation to unbound targets."""
    if (
        not targets
        or body not in targets
        or len(set(targets)) != len(targets)
        or not np.isfinite(alignment_tolerance)
        or alignment_tolerance <= 0
    ):
        raise ValueError(
            "Unique targets including body and positive alignment tolerance required"
        )
    for obj in targets:
        if obj.type != "MESH" or obj.find_armature() or not len(obj.data.polygons):
            raise ValueError("Bind requires nonempty, unbound mesh targets")
    previous = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(glb))
    imported = set(bpy.data.objects) - previous
    rigs = [o for o in imported if o.type == "ARMATURE"]
    if len(rigs) != 1:
        raise ValueError(
            "Expected one service armature; select/prepare ambiguous results explicitly"
        )
    rig = rigs[0]
    if rig.animation_data and (
        rig.animation_data.action or len(rig.animation_data.nla_tracks)
    ):
        raise ValueError("Animated service results need explicit rest-pose preparation")
    sources = [o for o in imported if o.type == "MESH" and o.find_armature() == rig]
    if len(sources) != 1:
        raise ValueError("Expected one skinned service body")
    source = sources[0]
    names, _ = skin_table(source, rig)
    if any(set(g.name for g in o.vertex_groups) & set(names) for o in targets):
        raise ValueError(
            "Existing group names collide with service bones; do not overwrite them"
        )

    def bounds(obj):
        v, _ = surface(obj)
        m = np.asarray(obj.matrix_world)
        v = v @ m[:3, :3].T + m[:3, 3]
        return np.array([v.min(0), v.max(0)])

    delta = float(np.max(np.abs(bounds(source) - bounds(body))))
    if delta > alignment_tolerance:
        raise ValueError(
            f"Service/body bounds differ by {delta:g}; calibrate space and scale first"
        )
    # Remove only non-skin groups on the imported reference, never on accepted targets.
    for group in list(source.vertex_groups):
        if group.name not in names:
            source.vertex_groups.remove(group)
    rig.data.pose_position = "REST"
    rig.show_in_front = True
    records = []
    for obj in targets:
        protected = [g.name for g in obj.vertex_groups]
        before = preserved_signature(obj, protected)
        if obj.data.users > 1:
            obj.data = obj.data.copy()
        bpy.ops.object.select_all(action="DESELECT")
        obj.hide_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        for name in names:
            obj.vertex_groups.new(name=name)
        transfer = obj.modifiers.new("Service weight transfer", "DATA_TRANSFER")
        transfer.object = source
        transfer.use_vert_data = True
        transfer.data_types_verts = {"VGROUP_WEIGHTS"}
        transfer.vert_mapping = "POLYINTERP_NEAREST"
        transfer.layers_vgroup_select_src = "ALL"
        transfer.layers_vgroup_select_dst = "NAME"
        transfer.use_object_transform = True
        transfer.mix_mode = "REPLACE"
        transfer.mix_factor = 1
        obj.modifiers.move(len(obj.modifiers) - 1, 0)
        bpy.ops.object.modifier_apply(modifier=transfer.name)
        mod = obj.modifiers.new("Service skin", "ARMATURE")
        mod.object = rig
        mod.use_deform_preserve_volume = True
        obj.modifiers.move(len(obj.modifiers) - 1, 0)
        bpy.ops.object.vertex_group_normalize_all(
            group_select_mode="BONE_DEFORM", lock_active=False
        )
        skin_table(obj, rig)
        if preserved_signature(obj, protected) != before:
            raise RuntimeError(
                "Weight transfer altered protected geometry, UVs or groups"
            )
        records.append(dict(object=obj.name, preserved=True))
    rig.data.pose_position = "POSE"
    for obj in imported:
        if obj.type == "MESH":
            obj.hide_render = True
            obj.hide_set(True)
    return dict(
        rig=rig.name,
        reference_body=source.name,
        bones=len(names),
        bounds_max_delta=delta,
        targets=records,
        service_glb_sha256=file_digest(glb),
        pose_qa_pending=True,
    )


def inspect_skin(obj, rig, frames, height):
    """Report current skin, calibration identity and worst triangles with their weights."""
    frames = list(frames)
    if not frames:
        raise ValueError("At least one inspection frame required")
    if (
        not obj.visible_get()
        or not rig.visible_get()
        or not any(
            m.type == "ARMATURE" and m.object == rig and m.show_viewport
            for m in obj.modifiers
        )
    ):
        raise ValueError(
            "Enable the body, rig and armature modifier for dependency-graph evaluation"
        )
    v, f = surface(obj)
    names, w = skin_table(obj, rig)
    report = dict(
        mesh_sha256=mesh_digest(v, f),
        bone_names=names,
        rig_sha256=rig_digest(obj, rig),
        bone_heads={
            b.name: list(obj.matrix_world.inverted() @ rig.matrix_world @ b.head_local)
            for b in rig.data.bones
        },
        coordinate_space="body mesh local rest coordinates",
        max_weight_sum_error=float(abs(w.sum(1) - 1).max()),
        frames=[],
        motion_observed=False,
    )
    old_frame = bpy.context.scene.frame_current
    try:
        for frame in frames:
            bpy.context.scene.frame_set(frame)
            if (
                not obj.visible_get()
                or not rig.visible_get()
                or not any(
                    m.type == "ARMATURE" and m.object == rig and m.show_viewport
                    for m in obj.modifiers
                )
            ):
                raise ValueError(f"Body/rig evaluation is disabled at frame {frame}")
            evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
            mesh = evaluated.to_mesh()
            try:
                p = np.empty(len(mesh.vertices) * 3, np.float32)
                mesh.vertices.foreach_get("co", p)
                p = p.reshape(-1, 3)
                mesh.calc_loop_triangles()
                ff = np.empty(len(mesh.loop_triangles) * 3, np.int32)
                mesh.loop_triangles.foreach_get("vertices", ff)
                if p.shape != v.shape or not np.array_equal(ff.reshape(-1, 3), f):
                    raise ValueError(
                        "Topology-changing modifiers require a separate evaluated baseline"
                    )
                check = stretch_metrics(v, p, f, height)
                report["motion_observed"] |= bool(np.max(np.abs(p - v)) > height * 1e-6)
                check["frame"] = frame
                check["worst"] = [
                    dict(
                        face=i,
                        vertices=f[i].tolist(),
                        rest=v[f[i]].tolist(),
                        weights=[
                            {names[j]: float(w[k, j]) for j in np.flatnonzero(w[k])}
                            for k in f[i]
                        ],
                    )
                    for i in check.pop("worst_faces")
                ]
                report["frames"].append(check)
            finally:
                evaluated.to_mesh_clear()
    finally:
        bpy.context.scene.frame_set(old_frame)
    report["pass"] = all(
        not r["significant_faces"] and not r["large_area_faces"]
        for r in report["frames"]
    )
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["export", "bind", "inspect", "repair"])
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--body", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--faces", type=int)
    parser.add_argument("--rigged-glb", type=Path)
    parser.add_argument("--targets", nargs="+")
    parser.add_argument("--alignment-tolerance", type=float)
    parser.add_argument("--rig")
    parser.add_argument("--frames", help="Actual test animation, e.g. 1:60")
    parser.add_argument("--height", type=float, help="Height in mesh-local units")
    parser.add_argument("--rules", type=Path)
    args = parser.parse_args(argv)
    if args.report.exists() or args.report.resolve() == args.input.resolve():
        raise ValueError("Use a new report path")
    if args.command != "inspect" and (not args.output or args.output.exists()):
        raise ValueError("Use a new output path; input is never overwritten")
    if args.output and args.output.resolve() == args.report.resolve():
        raise ValueError("Output and report must be different paths")
    bpy.ops.wm.open_mainfile(filepath=str(args.input))
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    body = bpy.data.objects[args.body]
    if args.command == "export":
        result = export_body(body, args.output, args.faces)
    elif args.command == "bind":
        if not args.rigged_glb or not args.targets or args.alignment_tolerance is None:
            parser.error(
                "bind requires --rigged-glb, --targets and --alignment-tolerance"
            )
        result = bind_result(
            args.rigged_glb,
            body,
            [bpy.data.objects[n] for n in args.targets],
            args.alignment_tolerance,
        )
    else:
        rig = bpy.data.objects[args.rig] if args.rig else body.find_armature()
        if rig is None or rig.type != "ARMATURE" or body.find_armature() != rig:
            raise ValueError("Rig must be the body's current armature")
        if args.command == "inspect":
            if not args.frames or args.height is None:
                parser.error("inspect requires --frames and --height")
            frames = parse_frames(args.frames)
            if not frames:
                raise ValueError("At least one frame required")
            result = inspect_skin(body, rig, frames, args.height)
        else:
            if not args.rules:
                parser.error("repair requires --rules")
            config = json.loads(args.rules.read_text())
            v, f = surface(body)
            names, before = skin_table(body, rig)
            if (
                config.get("mesh_sha256") != mesh_digest(v, f)
                or config.get("bone_names") != names
                or config.get("rig_sha256") != rig_digest(body, rig)
            ):
                raise ValueError(
                    "Repair rules do not match mesh, bind matrices and ordered bones"
                )
            protected = [g.name for g in body.vertex_groups if g.name not in names]
            signature = preserved_signature(body, protected)
            after, result = repair_regions(v, before, names, config["regions"])
            write_changed_weights(body, names, before, after)
            if preserved_signature(body, protected) != signature:
                raise RuntimeError("Repair changed protected data")
            result["pose_qa_pending"] = True
    if args.command in {"bind", "repair"}:
        if args.output.suffix.lower() != ".blend":
            raise ValueError("Use a new .blend output")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.file.pack_all()
        bpy.ops.wm.save_as_mainfile(filepath=str(args.output))
        result["output_sha256"] = file_digest(args.output)
    result["input_sha256"] = file_digest(args.input)
    atomic_json(args.report, result)
    if args.command == "inspect" and not result["pass"]:
        raise RuntimeError("Skin deformation failed; inspect report before repair")


if __name__ == "__main__":
    main()
