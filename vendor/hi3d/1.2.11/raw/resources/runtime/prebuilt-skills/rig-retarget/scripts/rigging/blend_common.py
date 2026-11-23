"""Blender-only helpers. No credentials, network, or project-specific assets."""

import hashlib
import json
from pathlib import Path
import bpy
import numpy as np
from .io_utils import file_digest


def curves(action):
    if getattr(action, "layers", None):
        return [
            c
            for layer in action.layers
            for strip in layer.strips
            for bag in getattr(strip, "channelbags", ())
            for c in bag.fcurves
        ]
    return list(getattr(action, "fcurves", ()))


def linked_actions(obj):
    ad = obj.animation_data
    if not ad:
        return []
    items = [ad.action] if ad.action else []
    items += [s.action for t in ad.nla_tracks for s in t.strips if s.action]
    return list(dict.fromkeys(items))


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def animation_hash():
    data = []
    for a in sorted(bpy.data.actions, key=lambda a: a.name):
        data.append(
            [
                a.name,
                [
                    [
                        c.data_path,
                        c.array_index,
                        c.extrapolation,
                        [
                            [
                                *k.co,
                                *k.handle_left,
                                *k.handle_right,
                                k.interpolation,
                                k.handle_left_type,
                                k.handle_right_type,
                            ]
                            for k in c.keyframe_points
                        ],
                    ]
                    for c in curves(a)
                ],
            ]
        )
    return digest(data)


def geometry_hash():
    h = hashlib.sha256()
    for o in sorted(bpy.data.objects, key=lambda o: o.name):
        if o.type == "MESH":
            m = o.data
            h.update(o.name.encode())
            for seq, attr, dtype, size in [
                (m.vertices, "co", np.float32, 3),
                (m.loops, "vertex_index", np.int32, 1),
                (m.polygons, "loop_total", np.int32, 1),
                (m.polygons, "material_index", np.int32, 1),
            ]:
                a = np.empty(len(seq) * size, dtype)
                seq.foreach_get(attr, a)
                h.update(a.tobytes())
            for uv in m.uv_layers:
                h.update(uv.name.encode())
                a = np.empty(len(m.loops) * 2, np.float32)
                uv.data.foreach_get("uv", a)
                h.update(a.tobytes())
            h.update(json.dumps([g.name for g in o.vertex_groups]).encode())
            for v in m.vertices:
                h.update(json.dumps([(g.group, g.weight) for g in v.groups]).encode())
            if m.shape_keys:
                for key in m.shape_keys.key_blocks:
                    h.update(key.name.encode())
                    a = np.empty(len(key.data) * 3, np.float32)
                    key.data.foreach_get("co", a)
                    h.update(a.tobytes())
        elif o.type == "ARMATURE":
            for b in o.data.bones:
                h.update(
                    json.dumps(
                        [b.name, b.parent.name if b.parent else None, b.use_deform]
                    ).encode()
                )
                h.update(np.asarray(b.matrix_local, dtype=np.float32).tobytes())
    return h.hexdigest()


def open_input(path, output=None):
    src = Path(path).expanduser().resolve()
    if not src.is_file():
        raise ValueError("Input blend does not exist")
    if output:
        dst = Path(output).expanduser().resolve()
        if dst == src or dst.exists():
            raise ValueError(
                "Write a new candidate path; input and existing outputs are never overwritten"
            )
    bpy.ops.wm.open_mainfile(filepath=str(src), use_scripts=False)
    return src


def write_json(path, value):
    p = Path(path).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def save_candidate(args, report):
    dst = Path(args.output).expanduser().resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)
    if args.pack:
        bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(dst), compress=True)
    # Reopen the exact saved artifact before delivering its inventory.
    bpy.ops.wm.open_mainfile(filepath=str(dst), use_scripts=False)
    report["saved_inventory"] = inventory()
    report["file_sha256"] = file_digest(dst)
    write_json(args.report or str(dst.with_suffix(".report.json")), report)


def inventory():
    s = bpy.context.scene
    rigs = []
    for o in s.objects:
        if o.type != "ARMATURE":
            continue
        ad = o.animation_data
        rigs.append(
            {
                "name": o.name,
                "parent": o.parent.name if o.parent else None,
                "location": list(o.matrix_world.translation),
                "bones": [b.name for b in o.data.bones],
                "active_action": ad.action.name if ad and ad.action else None,
                "strips": [
                    {
                        "track": t.name,
                        "name": st.name,
                        "action": st.action.name if st.action else None,
                        "scene_range": [st.frame_start, st.frame_end],
                        "scale": st.scale,
                        "repeat": st.repeat,
                    }
                    for t in ad.nla_tracks
                    for st in t.strips
                ]
                if ad
                else [],
            }
        )
    return {
        "frames": [s.frame_start, s.frame_end],
        "fps": s.render.fps / s.render.fps_base,
        "camera": s.camera.name if s.camera else None,
        "camera_location": list(s.camera.matrix_world.translation)
        if s.camera
        else None,
        "texts": [
            {"object": o.name, "body": o.data.body}
            for o in s.objects
            if o.type == "FONT"
        ],
        "rigs": rigs,
        "actions": [
            {"name": a.name, "range": list(a.frame_range)} for a in bpy.data.actions
        ],
        "file_images": [
            {"name": i.name, "packed": bool(i.packed_file)}
            for i in bpy.data.images
            if i.source == "FILE"
        ],
    }
