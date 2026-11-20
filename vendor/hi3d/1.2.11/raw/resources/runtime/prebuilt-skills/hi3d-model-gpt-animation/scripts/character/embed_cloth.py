"""Capture a baked cloth proxy, embed local-space samples, and verify the saved blend."""

import argparse
from pathlib import Path
import bpy
import numpy as np
from rigging.blend_common import curves, open_input, write_json
from .contact_check import mesh_arrays, rest_surface
from rigging.weight_graph import file_digest


def evaluate(ob, frame, rest):
    bpy.context.scene.frame_set(int(frame))
    evaluated = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        v, f = mesh_arrays(mesh)
        if v.shape != rest["vertices"].shape or not np.array_equal(f, rest["faces"]):
            raise ValueError(
                "Proxy topology changed; vertex correspondence is required"
            )
        matrix = np.asarray(evaluated.matrix_world, dtype=np.float64)
        if not np.isfinite(v).all() or not np.isfinite(matrix).all():
            raise ValueError("Nonfinite proxy sample")
        return v, matrix
    finally:
        evaluated.to_mesh_clear()


def capture(args):
    dst = args.output.resolve()
    report_path = Path(str(dst) + ".json")
    if dst.exists() or report_path.exists():
        raise ValueError("Capture outputs already exist")
    src = open_input(args.input)
    if args.end < args.start:
        raise ValueError("Invalid frame range")
    ob = bpy.data.objects[args.proxy]
    rest = rest_surface(ob)
    cloth = [m for m in ob.modifiers if m.type == "CLOTH" and m.show_viewport]
    if len(cloth) != 1 or not cloth[0].point_cache.is_baked:
        raise ValueError(
            "Capture the original file with one enabled, baked Cloth modifier"
        )
    cache = cloth[0].point_cache
    if args.start < cache.frame_start or args.end > cache.frame_end:
        raise ValueError("Requested frames are outside the baked cache")
    frames = np.arange(args.start, args.end + 1, dtype=np.int32)
    if len(frames) < 2:
        raise ValueError("Capture at least two consecutive frames")
    samples = [evaluate(ob, frame, rest) for frame in frames]
    positions = np.stack([x[0] for x in samples])
    matrices = np.stack([x[1] for x in samples])
    source_sha = file_digest(src)
    fps = bpy.context.scene.render.fps / bpy.context.scene.render.fps_base
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("wb") as stream:
        np.savez_compressed(
            stream,
            frames=frames,
            positions=positions,
            matrices=matrices,
            source_sha256=source_sha,
            mesh_sha256=rest["mesh_sha256"],
            proxy=ob.name,
            fps=fps,
        )
    write_json(
        report_path,
        {
            "source_sha256": source_sha,
            "capture_sha256": file_digest(dst),
            "proxy": ob.name,
            "mesh_sha256": rest["mesh_sha256"],
            "frames": frames.tolist(),
            "fps": fps,
            "vertices": len(rest["vertices"]),
            "space": "evaluated object local",
            "note": "Integer samples of this take only; cache validity and visual quality still require inspection.",
        },
    )
    print("CLOTH_CAPTURED", dst, flush=True)


def embed(args):
    report_path = args.report or args.output.with_suffix(".cloth.json")
    if report_path.resolve().exists():
        raise ValueError("Report already exists")
    src = open_input(args.input, args.output)
    with np.load(args.cache, allow_pickle=False) as data:
        if str(data["source_sha256"].item()) != file_digest(src):
            raise ValueError("Capture must match the exact source blend")
        name = str(data["proxy"].item())
        ob = bpy.data.objects[name]
        rest = rest_surface(ob)
        if str(data["mesh_sha256"].item()) != rest["mesh_sha256"]:
            raise ValueError("Proxy rest-mesh fingerprint changed")
        frames = data["frames"].copy()
        positions = data["positions"].copy()
        matrices = data["matrices"].copy()
        fps = float(data["fps"])
    if (
        frames.ndim != 1
        or frames.dtype.kind not in "iu"
        or len(frames) < 2
        or not np.all(np.diff(frames) == 1)
    ):
        raise ValueError("Expected consecutive integer frames")
    if positions.shape != (len(frames), len(rest["vertices"]), 3) or matrices.shape != (
        len(frames),
        4,
        4,
    ):
        raise ValueError("Capture dimensions do not match the proxy")
    if not np.isfinite(positions).all() or not np.isfinite(matrices).all():
        raise ValueError("Nonfinite capture")
    scene = bpy.context.scene
    if abs(fps - scene.render.fps / scene.render.fps_base) > 1e-8:
        raise ValueError("Scene fps changed")
    if args.tolerance <= 0 or not np.isfinite(args.tolerance):
        raise ValueError("Invalid tolerance")
    followers = [
        o.name
        for o in scene.objects
        for m in o.modifiers
        if m.type == "SURFACE_DEFORM" and m.target == ob and m.is_bound
    ]
    if ob.data.users > 1:
        raise ValueError("Make the proxy mesh single-user before capture")
    native_collection = bpy.data.collections.new(name + "__NativeCloth")
    scene.collection.children.link(native_collection)
    native = ob.copy()
    native.data = ob.data.copy()
    native.name = name + "__NativeBackup"
    native_name = native.name
    native_collection.objects.link(native)
    native_collection.hide_render = True
    native_collection.hide_viewport = True
    native["cache_note"] = (
        "Configuration backup only; rebake the original simulation for new motion."
    )
    # Retain object identity for already-bound Surface Deform followers. Captured positions
    # already include every upstream modifier, so retaining an Armature would deform twice.
    removed = [m.type for m in ob.modifiers]
    for modifier in list(ob.modifiers):
        ob.modifiers.remove(modifier)
    ob.shape_key_clear()
    ob.shape_key_add(name="Basis", from_mix=False)
    for frame, v in zip(frames, positions):
        key = ob.shape_key_add(name=f"Cloth_{int(frame):06d}", from_mix=False)
        key.data.foreach_set("co", v.ravel())
        for time, value in [(int(frame) - 1, 0), (int(frame), 1), (int(frame) + 1, 0)]:
            key.value = value
            key.keyframe_insert("value", frame=time)
    keys = ob.data.shape_keys
    ad = keys.animation_data
    action = ad.action
    action.name = name + "__EmbeddedCloth"
    slot = getattr(ad, "action_slot", None)
    for curve in curves(action):
        for key in curve.keyframe_points:
            key.interpolation = "LINEAR"
    track = ad.nla_tracks.new()
    track.name = "Embedded Cloth Playback"
    strip = track.strips.new(action.name, int(frames[0]), action)
    if slot is not None and hasattr(strip, "action_slot"):
        strip.action_slot = slot
    strip.action_frame_start = int(frames[0])
    strip.action_frame_end = int(frames[-1])
    strip.frame_start = int(frames[0])
    strip.frame_end = int(frames[-1])
    strip.blend_type = "REPLACE"
    ad.action = None
    ob["embedded_cloth_range"] = [int(frames[0]), int(frames[-1])]
    ob["embedded_cloth_capture_sha256"] = file_digest(args.cache)
    if args.set_range:
        scene.frame_start, scene.frame_end = int(frames[0]), int(frames[-1])
    scene.frame_set(int(frames[0]))
    dst = args.output.resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(dst), compress=True)
    bpy.ops.wm.open_mainfile(filepath=str(dst))
    ob = bpy.data.objects[name]
    maximum = 0.0
    matrix_error = 0.0
    for frame, v, matrix in zip(frames, positions, matrices):
        actual, actual_matrix = evaluate(ob, frame, rest)
        maximum = max(maximum, float(np.max(np.abs(actual - v))))
        matrix_error = max(matrix_error, float(np.max(np.abs(actual_matrix - matrix))))
    current_followers = [
        o.name
        for o in bpy.context.scene.objects
        for m in o.modifiers
        if m.type == "SURFACE_DEFORM" and m.target == ob and m.is_bound
    ]
    passed = (
        maximum <= args.tolerance
        and matrix_error <= args.tolerance
        and sorted(followers) == sorted(current_followers)
    )
    report = {
        "passed": passed,
        "input_sha256": file_digest(src),
        "output_sha256": file_digest(dst),
        "capture_sha256": file_digest(args.cache),
        "proxy": name,
        "native_backup": native_name,
        "frames": [int(frames[0]), int(frames[-1])],
        "fps": fps,
        "vertices": len(rest["vertices"]),
        "maximum_local_coordinate_error": maximum,
        "maximum_world_matrix_error": matrix_error,
        "tolerance": args.tolerance,
        "bound_followers_preserved": sorted(followers) == sorted(current_followers),
        "removed_playback_modifiers": removed,
        "limitations": "This take only. Subframes interpolate linearly. Inspect transferred render meshes and contacts. Native backup retains settings, not a portable physics cache.",
    }
    write_json(report_path, report)
    if not passed:
        raise RuntimeError(
            "Saved embedded-cloth playback differs from capture; inspect report"
        )
    print("CLOTH_EMBED_VERIFIED", dst, maximum, flush=True)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    c = sub.add_parser("capture")
    c.add_argument("--input", type=Path, required=True)
    c.add_argument("--proxy", required=True)
    c.add_argument("--start", type=int, required=True)
    c.add_argument("--end", type=int, required=True)
    c.add_argument("--output", type=Path, required=True)
    e = sub.add_parser("embed")
    e.add_argument("--input", type=Path, required=True)
    e.add_argument("--cache", type=Path, required=True)
    e.add_argument("--output", type=Path, required=True)
    e.add_argument("--report", type=Path)
    e.add_argument("--set-range", action="store_true")
    e.add_argument(
        "--tolerance",
        type=float,
        default=1e-5,
        help="Coordinate/matrix component tolerance in scene units",
    )
    a = p.parse_args(argv)
    (capture if a.command == "capture" else embed)(a)


if __name__ == "__main__":
    main()
