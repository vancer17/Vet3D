"""Repair source-derived facial controls, attach a basic anatomical rig and eyes."""

import json
import hashlib
import sys
from pathlib import Path
import bpy
import numpy as np
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_io import coordinates, material, make_mesh
from collision import crossing_pairs, triangle_stats


def mesh_triangles(mesh):
    mesh.calc_loop_triangles()
    tri = np.empty(len(mesh.loop_triangles) * 3, np.int32)
    mesh.loop_triangles.foreach_get("vertices", tri)
    return tri.reshape(-1, 3)


def shape_coords(key):
    out = np.empty(len(key.data) * 3, np.float32)
    key.data.foreach_get("co", out)
    return out.reshape(-1, 3).astype(float)


def repair_shapes(obj, metadata, face, report_path):
    """Bounded local repairs preserve the neutral-to-expression interpolation path."""
    mesh = obj.data
    tri = mesh_triangles(mesh)
    base = shape_coords(mesh.shape_keys.key_blocks["Basis"])
    original = base.copy()
    edge = np.array([tuple(e.vertices) for e in mesh.edges])
    a = np.r_[edge[:, 0], edge[:, 1]]
    b = np.r_[edge[:, 1], edge[:, 0]]
    degree = np.bincount(a, minlength=len(base))
    height = np.ptp(base, axis=0).max()
    contact_cache = {}

    def contacts(points):
        # Cache only bit-identical states; any repair changes the key.
        key = hashlib.sha256(np.ascontiguousarray(points).view(np.uint8)).digest()
        if key not in contact_cache:
            contact_cache[key] = crossing_pairs(points, tri)
        return contact_cache[key]

    def average(points):
        return np.column_stack(
            [
                np.bincount(a, weights=points[b, c], minlength=len(points))
                / np.maximum(degree, 1)
                for c in range(3)
            ]
        )

    def local_fix(points, label, budget):
        original = points.copy()
        history = []
        for iteration in range(40):
            pairs = contacts(points)
            history.append(len(pairs))
            if not len(pairs):
                break
            active = np.zeros(len(base), bool)
            active[tri[pairs.ravel()].ravel()] = True
            # The displacement budget is geometric; the neighborhood only accelerates relaxation.
            for _ in range(2):
                active[b[active[a]]] = True
            for _ in range(3):
                delta = 0.2 * (average(points) - points)
                delta[~active] = 0
                length = np.linalg.norm(delta, axis=1)
                delta *= np.minimum(1, height * 0.0006 / np.maximum(length, 1e-15))[
                    :, None
                ]
                points += delta
            if np.max(np.linalg.norm(points - original, axis=1)) > budget:
                raise ValueError(
                    label + " repair exceeds fidelity budget; inspect patch geometry"
                )
        if history[-1]:
            raise ValueError(label + " has unresolved triangle crossings")
        print("REPAIRED", label, history, flush=True)
        return points, history

    # Relax scan wrinkles at the patch boundaries without closing the eye/lip aperture.
    weight = np.zeros(len(base))
    for patch in face["patches"]:
        cx, cz = patch["center"]
        rx, rz = patch["outer_radii"]
        weight = np.maximum(
            weight,
            np.exp(
                -0.5 * ((base[:, 0] - cx) / rx) ** 2
                - 0.5 * ((base[:, 2] - cz) / rz) ** 2
            ),
        )
    weight *= np.clip((face["front_depth"] - base[:, 1]) / (height * 0.1), 0, 1)
    weight *= np.where(
        metadata[:, 0] > 0, np.clip((1 - metadata[:, 1]) / 0.16, 0, 1), 1
    )
    for _ in range(16):
        base += 0.25 * weight[:, None] * (average(base) - base)
        offset = base - original
        length = np.linalg.norm(offset, axis=1)
        base = (
            original
            + offset
            * np.minimum(1, height * 0.0045 / np.maximum(length, 1e-15))[:, None]
        )
    base, hist = local_fix(base, "Basis", height * 0.015)
    offset = base - original
    histories = {"Basis": hist}
    mesh.shape_keys.key_blocks["Basis"].data.foreach_set(
        "co", base.astype(np.float32).ravel()
    )
    for key in mesh.shape_keys.key_blocks:
        if key.name == "Basis":
            continue
        endpoint = shape_coords(key) + offset
        endpoint, hist = local_fix(endpoint, key.name, height * 0.015)
        histories[key.name] = hist
        values = [0.25, 0.5, 0.75, 1.0]
        if key.name.startswith("eyeBlink"):
            values = [0.15, 0.3, 0.45, 0.6, 0.72, 0.8, 0.86, 0.9, 0.94, 0.97, 1]
        # Correct endpoints against failures at intermediate weights; verify once more afterward.
        for attempt in range(10):
            repaired_states = 0
            for value in values:
                points = base + value * (endpoint - base)
                if not len(contacts(points)):
                    continue
                fixed, _ = local_fix(
                    points.copy(), key.name + "@" + str(value), height * 0.008
                )
                endpoint += (fixed - points) / value
                repaired_states += 1
            if not repaired_states:
                break
        if any(
            len(contacts(base + value * (endpoint - base)))
            for value in values
        ):
            raise ValueError(key.name + " interpolation still crosses itself")
        key.data.foreach_set("co", endpoint.astype(np.float32).ravel())
    mesh.vertices.foreach_set("co", base.astype(np.float32).ravel())
    mesh.update()
    report = {
        "neutral_displacement_max": float(np.max(np.linalg.norm(offset, axis=1))),
        "histories": histories,
        "neutral": triangle_stats(base, tri),
        "scope": "nonadjacent noncoplanar triangle crossings; tangent/coplanar contacts require visual review",
    }
    Path(report_path).write_text(json.dumps(report, indent=2))


def build_rig(face):
    data = bpy.data.armatures.new("Lowpoly facial rig")
    rig = bpy.data.objects.new("Lowpoly_Rig", data)
    bpy.context.scene.collection.objects.link(rig)
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    for name, (head, tail, parent) in face["joints"].items():
        bone = data.edit_bones.new(name)
        bone.head = head
        bone.tail = tail
        if parent:
            bone.parent = data.edit_bones[parent]
    bpy.ops.object.mode_set(mode="OBJECT")
    rig.show_in_front = True
    return rig


def bind(obj, rig, bone=None):
    if bone:
        vg = obj.vertex_groups.new(name=bone)
        vg.add(list(range(len(obj.data.vertices))), 1, "REPLACE")
    modifier = obj.modifiers.new("Linear skinning", "ARMATURE")
    modifier.object = rig
    modifier.use_deform_preserve_volume = False
    obj.parent = rig


def add_eyes_and_cavity(source, low, rig, face):
    """Keep the visible ocular surface of the source; back it with a recessed sclera."""
    vertices = coordinates(source)
    tri = mesh_triangles(source.data)
    uvs = None
    if source.data.uv_layers.active:
        uv_all = np.empty(len(source.data.loops) * 2, np.float32)
        source.data.uv_layers.active.data.foreach_get("uv", uv_all)
        loops = np.empty((len(source.data.loop_triangles), 3), np.int32)
        source.data.loop_triangles.foreach_get("loops", loops.ravel())
        uvs = uv_all.reshape(-1, 2)[loops]
    skin = BVHTree.FromObject(low, bpy.context.evaluated_depsgraph_get())
    ray_start_y = float(vertices[:, 1].min()) - 1
    for patch in face["patches"]:
        if patch["kind"] != "eye":
            continue
        cx, cz = patch["center"]
        rx, rz = patch["inner_radii"]
        side = patch["side"]
        mask = (
            ((vertices[:, 0] - cx) / (rx * 1.34)) ** 2
            + ((vertices[:, 2] - cz) / (rz * 2.4)) ** 2
            < 1
        ) & (vertices[:, 1] < face["front_depth"])
        selected = np.where(mask[tri].any(1))[0]
        used, inverse = np.unique(tri[selected], return_inverse=True)
        positions = vertices[used].copy()
        clearance = rx * 0.025
        positions[:, 1] += clearance
        for p in positions:
            hit, _, _, _ = skin.ray_cast(
                (p[0], ray_start_y, p[2]), (0, 1, 0), 3
            )
            # A ray through an open eyelid hits the back of the head: that is not a lid.
            if (
                hit is not None
                and abs(hit.y - p[1]) < rx * 0.35
                and p[1] < hit.y + clearance
            ):
                p[1] = hit.y + clearance
        eye = make_mesh("Lowpoly_EyeSurface_" + side, positions, inverse.reshape(-1, 3))
        if uvs is not None:
            eye.data.uv_layers.new(name="SourceUV").data.foreach_set(
                "uv", uvs[selected].ravel()
            )
        for mat in source.data.materials:
            eye.data.materials.append(mat)
        bpy.ops.object.select_all(action="DESELECT")
        eye.select_set(True)
        bpy.context.view_layer.objects.active = eye
        if len(eye.data.polygons) > 4500:
            modifier = eye.modifiers.new("Ocular density", "DECIMATE")
            modifier.ratio = 4500 / len(eye.data.polygons)
            bpy.ops.object.modifier_apply(modifier=modifier.name)
        bind(eye, rig, "Eye_" + side)
        center = np.array(face["joints"]["Eye_" + side][0])
        center[1] += rx * 0.51
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=40, ring_count=24, radius=rx * 1.10, location=center
        )
        back = bpy.context.object
        back.name = "Lowpoly_EyeBack_" + side
        back.data.materials.append(material("Sclera", (0.47, 0.44, 0.4, 1), 0.35))
        bind(back, rig, "Eye_" + side)
    mouth = next(p for p in face["patches"] if p["kind"] == "mouth")
    cx, cz = mouth["center"]
    rx, _ = mouth["inner_radii"]
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=40,
        ring_count=24,
        radius=1,
        location=(cx, face["joints"]["Jaw"][1][1] - 0.015, cz - rx * 0.20),
    )
    bag = bpy.context.object
    bag.name = "Lowpoly_MouthInterior"
    bag.scale = (rx * 0.93, rx * 0.37, rx * 0.70)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bag.data.materials.append(
        material("Mouth interior", (0.014, 0.0025, 0.0035, 1), 0.86)
    )
    bind(bag, rig, "Head")


def attach_hair(rig, face_goal):
    """Keep explicit hair parts and their UV/materials, then bind rigidly to Head."""
    records = []
    sources = [o for o in bpy.context.scene.objects if o.name.startswith("Source_Hair_")]
    for source in sources:
        hair = source.copy()
        hair.data = source.data.copy()
        bpy.context.scene.collection.objects.link(hair)
        hair.name = "Lowpoly_Hair_" + source["source_object_name"]
        hair.hide_set(False)
        hair.hide_render = False
        hair.animation_data_clear()
        if hair.data.shape_keys:
            hair.shape_key_clear()
        hair.modifiers.clear()
        hair.vertex_groups.clear()
        before = len(hair.data.polygons)
        bpy.ops.object.select_all(action="DESELECT")
        hair.select_set(True)
        bpy.context.view_layer.objects.active = hair
        if before > face_goal:
            decimate = hair.modifiers.new("Hair density budget", "DECIMATE")
            decimate.ratio = face_goal / before
            bpy.ops.object.modifier_apply(modifier=decimate.name)
        if not np.isfinite(coordinates(hair)).all() or not len(hair.data.polygons):
            raise ValueError("Hair simplification produced invalid geometry")
        bind(hair, rig, "Head")
        source.hide_render = True
        source.hide_set(True)
        records.append({"source": source["source_object_name"], "object": hair.name,
                        "source_faces": before, "output_faces": len(hair.data.polygons),
                        "uv_layers": len(hair.data.uv_layers), "binding": "Head, weight 1"})
    return records


def run(config):
    root = Path(config["output"])
    face = json.loads(Path(config["face_config"]).read_text())
    bpy.ops.wm.open_mainfile(
        filepath=str(root / "Lowpoly_Unbaked.blend"), load_ui=False
    )
    low = bpy.data.objects["Lowpoly_Head"]
    source = bpy.data.objects["Source_High"]
    metadata = np.load(root / "lowpoly_patch_data.npz")["metadata"]
    repair_shapes(low, metadata, face, root / "lowpoly_repair.json")
    rig = build_rig(face)
    bind(low, rig)
    add_eyes_and_cavity(source, low, rig, face)
    hair = attach_hair(rig, config.get("hair_face_goal", 10000))
    (root / "hair_report.json").write_text(json.dumps({"parts": hair,
        "scope": "separate mesh hair retains source materials/UV; fused hair stays in the head surface; no strand reconstruction or hair simulation"}, indent=2))
    scene = bpy.context.scene
    scene.render.fps = 24
    scene.frame_start = 1
    names = [key.name for key in low.data.shape_keys.key_blocks if key.name != "Basis"]
    scene.frame_end = len(names) * 24 + 1
    for i, name in enumerate(names):
        key = low.data.shape_keys.key_blocks[name]
        for frame, value in [
            (1, 0),
            (i * 24 + 1, 0),
            (i * 24 + 10, 0.75),
            (i * 24 + 15, 0.75),
            (i * 24 + 24, 0),
            (scene.frame_end, 0),
        ]:
            key.value = value
            key.keyframe_insert("value", frame=frame)
    scene.frame_set(1)
    source.hide_render = True
    source.hide_set(True)
    bpy.ops.wm.save_as_mainfile(filepath=str(root / "Lowpoly_Rigged.blend"))
    basis = shape_coords(low.data.shape_keys.key_blocks["Basis"])
    np.savez_compressed(
        root / "lowpoly_data.npz",
        vertices=basis,
        triangles=mesh_triangles(low.data),
        quads=np.array([tuple(p.vertices) for p in low.data.polygons]),
        expression_names=np.array(names),
        expression_deltas=np.array(
            [
                shape_coords(low.data.shape_keys.key_blocks[name]) - basis
                for name in names
            ]
        ),
    )
    print("LOW_RIG_READY", names, flush=True)


if __name__ == "__main__":
    run(json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text()))
