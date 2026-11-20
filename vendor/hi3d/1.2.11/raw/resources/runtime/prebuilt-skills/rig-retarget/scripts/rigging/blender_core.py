"""Reusable geometry, calibrated skeleton and localized skinning operations."""

import bpy
import numpy as np
from .mesh_snapshot import mesh_snapshot
from mathutils import Vector


def mesh_arrays(ob):
    if any(len(p.vertices) != 3 for p in ob.data.polygons):
        raise ValueError("Triangulate the working mesh before solving weights")
    data = mesh_snapshot(ob, evaluated=False, space='local', triangulation='require_triangles', precision='float32')
    return data['vertices'], data['triangles']


def mesh_fingerprint(v, f):
    from .weight_graph import mesh_digest

    return mesh_digest(v, f)


def create_rig(spec, height):
    data = bpy.data.armatures.new("CharacterRig")
    rig = bpy.data.objects.new("CharacterRig", data)
    bpy.context.scene.collection.objects.link(rig)
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    for row in spec:
        b = data.edit_bones.new(row["name"])
        b.head = Vector(row["head"]) * height
        b.tail = Vector(row["tail"]) * height
        if (b.tail - b.head).length < height * 1e-5:
            raise ValueError("Deforming bones require distinct anatomical endpoints")
        if row.get("parent"):
            b.parent = data.edit_bones[row["parent"]]
        b.use_deform = row.get("deform", True)
        if row.get("roll_axis"):
            b.align_roll(Vector(row["roll_axis"]))
    bpy.ops.object.mode_set(mode="OBJECT")
    for b in data.bones:
        b.inherit_scale = "NONE"
        b.bbone_segments = 1
    for p in rig.pose.bones:
        p.rotation_mode = "QUATERNION"
        p.lock_scale = (True, True, True)
    rig.show_in_front = True
    return rig


def region_mask(points, row):
    lo, hi = np.array(row["bounds"][0]), np.array(row["bounds"][1])
    return np.all((points >= lo) & (points <= hi), axis=1)


def initial_weights(v, names, profile, height):
    """Ordered anatomical regions; later regions override earlier ones."""
    p = v / height
    weights = np.zeros((len(v), len(names)), dtype=np.float64)
    weights[:, names.index(profile["default_bone"])] = 1
    for row in profile["weight_regions"]:
        ids = np.flatnonzero(region_mask(p, row))
        if not len(ids):
            continue
        weights[ids] = 0
        chain = row["bones"]
        if len(chain) == 1:
            weights[ids, names.index(chain[0])] = 1
            continue
        coord = p[ids, row["axis"]] * row.get("sign", 1)
        transitions = row["transitions"]
        if len(transitions) != len(chain) - 1:
            raise ValueError("One transition required between each pair of bones")
        centers = [t[0] for t in transitions]
        if centers != sorted(centers) or any(t[1] <= 0 for t in transitions):
            raise ValueError(
                "Transition centers must increase along signed coordinate; widths positive"
            )
        ts = []
        for center, half_width in transitions:
            t = np.clip((coord - center + half_width) / (2 * half_width), 0, 1)
            ts.append(t * t * (3 - 2 * t))
        remaining = np.ones(len(ids))
        for i, bone in enumerate(chain[:-1]):
            weights[ids, names.index(bone)] = remaining * (1 - ts[i])
            remaining *= ts[i]
        weights[ids, names.index(chain[-1])] = remaining
    return weights


def localized_solve(v, f, initial, radius, fidelity_length, edge_floor, **options):
    """Compatibility entrypoint; pure numerical solver also supports external Python."""
    from .weight_graph import solve_weights

    return solve_weights(v, f, initial, radius, fidelity_length, edge_floor, **options)


def part_labels(v, f, profile, height):
    points = v[f].mean(axis=1) / height
    labels = np.full(len(f), profile.get("default_part", "Body"), dtype="<U80")
    for rule in profile.get("part_rules", []):
        labels[region_mask(points, rule)] = rule["name"]
    return labels


def split_bind(surface, rig, names, weights, labels, rigid_parts):
    """Split only after solving on the welded graph; retain corner UVs and shared weights."""
    v, f = mesh_arrays(surface)
    me = surface.data
    mats = np.empty(len(f), dtype=np.int32)
    me.polygons.foreach_get("material_index", mats)
    uvs = {}
    for layer in me.uv_layers:
        a = np.empty(len(me.loops) * 2, dtype=np.float32)
        layer.data.foreach_get("uv", a)
        uvs[layer.name] = a.reshape(-1, 3, 2)
    collection = bpy.data.collections.new("CharacterParts")
    bpy.context.scene.collection.children.link(collection)
    parts = []
    for label in sorted(np.unique(labels)):
        mask = labels == label
        ids, inv = np.unique(f[mask], return_inverse=True)
        mesh = bpy.data.meshes.new(str(label))
        mesh.from_pydata(v[ids].tolist(), [], inv.reshape(-1, 3).tolist())
        mesh.update()
        ob = bpy.data.objects.new(str(label), mesh)
        collection.objects.link(ob)
        for mat in me.materials:
            mesh.materials.append(mat)
        mesh.polygons.foreach_set("material_index", mats[mask])
        for poly in mesh.polygons:
            poly.use_smooth = True
        for layer_name, values in uvs.items():
            mesh.uv_layers.new(name=layer_name).data.foreach_set(
                "uv", values[mask].ravel()
            )
        local = weights[ids].copy()
        if str(label) in rigid_parts:
            local[:] = 0
            local[:, names.index(rigid_parts[str(label)])] = 1
            ob["intentional_rigid_shell"] = True
        # Quantize onto a simplex: groups sum to exactly 1, with no top-k cutoff.
        scaled = local * 65536
        quant = np.floor(scaled).astype(np.int32)
        remainder = 65536 - quant.sum(axis=1)
        ranked = np.argsort(-(scaled - quant), axis=1)
        for rank in range(len(names)):
            rows = np.flatnonzero(remainder > rank)
            quant[rows, ranked[rows, rank]] += 1
        for j, name in enumerate(names):
            group = ob.vertex_groups.new(name=name)
            order = np.argsort(quant[:, j])
            values = quant[order, j]
            boundaries = np.r_[0, np.flatnonzero(np.diff(values)) + 1, len(values)]
            for lo, hi in zip(boundaries[:-1], boundaries[1:]):
                if values[lo] > 0:
                    group.add(order[lo:hi].tolist(), int(values[lo]) / 65536, "REPLACE")
        mod = ob.modifiers.new("CharacterSkin", "ARMATURE")
        mod.object = rig
        mod.use_deform_preserve_volume = True
        ob.parent = rig
        parts.append(ob)
    bpy.data.objects.remove(surface, do_unlink=True)
    return parts
