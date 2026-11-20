"""Synthetic Blender regressions for world contacts and portable cloth; no private assets."""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
import bpy
import numpy as np
from rigging.blend_common import curves
from .contact_check import check, sample_frames, rest_surface
from .embed_cloth import capture, embed, evaluate


def require_error(function, fragment):
    try:
        function()
    except ValueError as error:
        assert fragment in str(error), str(error)
    else:
        raise AssertionError("Expected rejection: " + fragment)


def mesh_object(name, vertices, faces):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def contact_fixture():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    a = mesh_object(
        "SurfaceA",
        [(-1, -1, 0), (1, -1, 0), (0, 1, 0), (20, 20, 0), (21, 20, 0), (20, 21, 0)],
        [(0, 1, 2), (3, 4, 5)],
    )
    b = mesh_object(
        "SurfaceB",
        [(0, -0.5, -1), (0, 0.5, -1), (0, 0, 1), (0, 40, 2), (0, 41, 2), (0, 40, 3)],
        [(0, 1, 2), (3, 4, 5)],
    )
    for ob, scale in [(a, (2, 1, 1)), (b, (1, 2, 1))]:
        parent = bpy.data.objects.new(ob.name + "Parent", None)
        scene.collection.objects.link(parent)
        parent.location = (4, 2, 1)
        parent.scale = scale
        ob.parent = parent
    for frame, x in [(1, -4), (2, 4)]:
        b.location.x = x
        b.keyframe_insert("location", frame=frame)
    for curve in curves(b.animation_data.action):
        for key in curve.keyframe_points:
            key.interpolation = "LINEAR"
    spec = {"pairs": [{"a": a.name, "b": b.name}]}
    require_error(lambda: check(spec, []), "nonempty")
    scene.frame_set(8, subframe=0.25)
    integer = check(spec, sample_frames("1:2"))
    half = check(spec, sample_frames("1:2:0.5"), True)
    assert integer["passed"] and not half["passed"], "Half-frame collision was missed"
    assert half["contact_face_union"][0]["SurfaceA"] == [0]
    assert scene.frame_current == 8 and abs(scene.frame_subframe - 0.25) < 1e-6
    surface = rest_surface(a)
    rule = {
        "object": a.name,
        "reason": "Synthetic fixed attachment triangle",
        "mesh_sha256": surface["mesh_sha256"],
        "face_ids": [0],
    }
    spec["pairs"][0]["exclude"] = [rule]
    excluded = check(spec, [1.5])
    assert excluded["passed"]
    row = excluded["results"][0]["pairs"][0]
    assert row["raw_contacts"] > 0 and row["excluded_contacts"] == row["raw_contacts"]
    assert excluded["exclusions"][0]["selector"] == {"face_ids": [0]}
    rule["rest_bounds"] = [[-1, -1, -1], [1, 1, 1]]
    require_error(lambda: check(spec, [1.5]), "exactly one")
    del rule["rest_bounds"]
    rule["mesh_sha256"] = "stale"
    require_error(lambda: check(spec, [1.5]), "fingerprint")
    rule["mesh_sha256"] = surface["mesh_sha256"]
    rule["face_ids"] = [0, 1]
    require_error(lambda: check(spec, [1.5]), "entire mesh")
    rule["face_ids"] = [0]
    rule["reason"] = ""
    require_error(lambda: check(spec, [1.5]), "reason")
    spec["pairs"][0]["exclude"] = []
    b.modifiers.new("ChangedTopology", "SOLIDIFY")
    require_error(lambda: check(spec, [1.5]), "triangulated")
    for expression in ["1:2:0", "2:1", "NaN", "1:2:-1"]:
        require_error(lambda: sample_frames(expression), "")
    assert sample_frames("-1:1:0.5,2") == [-1, -0.5, 0, 0.5, 1, 2]
    return {
        "world_transforms": True,
        "subframes": True,
        "exclusion_guards": True,
        "frame_restored": True,
        "topology_guard": True,
    }


def cloth_fixture(root):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    vertices = [(x / 4 - 0.5, y / 4 - 0.5, 2) for y in range(5) for x in range(5)]
    faces = [
        f
        for y in range(4)
        for x in range(4)
        for f in [
            (y * 5 + x, y * 5 + x + 1, (y + 1) * 5 + x),
            (y * 5 + x + 1, (y + 1) * 5 + x + 1, (y + 1) * 5 + x),
        ]
    ]
    ob = mesh_object("ClothProxy", vertices, faces)
    parent = bpy.data.objects.new("CharacterRoot", None)
    scene.collection.objects.link(parent)
    parent.location = (3, 2, 1)
    parent.scale = (1.5, 0.8, 1.2)
    ob.parent = parent
    # Both pre-Cloth shape deformation and object motion must survive embedding exactly once.
    ob.shape_key_add(name="Basis")
    guide = ob.shape_key_add(name="Guide")
    for vertex in guide.data:
        vertex.co.z += 0.1
    guide.value = 0.75
    pre = ob.modifiers.new("UpstreamTranslation", "DISPLACE")
    pre.strength = 0.15
    pre.mid_level = 0
    for frame, z in [(1, 0), (5, 0.2)]:
        ob.location.z = z
        ob.keyframe_insert("location", frame=frame)
    for curve in curves(ob.animation_data.action):
        for key in curve.keyframe_points:
            key.interpolation = "LINEAR"
    pins = ob.vertex_groups.new(name="Pins")
    pins.add(list(range(5)), 1, "REPLACE")
    cloth = ob.modifiers.new("NativeCloth", "CLOTH")
    cloth.settings.quality = 3
    cloth.settings.vertex_group_mass = "Pins"
    cloth.point_cache.frame_start = 1
    cloth.point_cache.frame_end = 5
    cloth.point_cache.use_disk_cache = True
    follower = mesh_object(
        "RenderFollower", [(x, y, z + 0.05) for x, y, z in vertices], faces
    )
    follower.parent = parent
    # Follower shares proxy object transforms in the intended pipeline.
    follower.animation_data_create()
    follower.animation_data.action = ob.animation_data.action
    if hasattr(follower.animation_data, "action_slot"):
        follower.animation_data.action_slot = ob.animation_data.action_slot
    sd = follower.modifiers.new("FollowCloth", "SURFACE_DEFORM")
    sd.target = ob
    scene.frame_start = 1
    scene.frame_end = 5
    scene.render.fps = 30
    scene.frame_set(1)
    bpy.context.view_layer.objects.active = follower
    follower.select_set(True)
    with bpy.context.temp_override(object=follower, active_object=follower):
        bpy.ops.object.surfacedeform_bind(modifier=sd.name)
    assert sd.is_bound
    source = root / "native.blend"
    cache = root / "capture.npz"
    destination = root / "portable.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(source))
    with bpy.context.temp_override(
        object=ob, active_object=ob, point_cache=cloth.point_cache
    ):
        bpy.ops.ptcache.bake(bake=True)
    assert cloth.point_cache.is_baked
    bpy.ops.wm.save_as_mainfile(filepath=str(source))
    follower_rest = rest_surface(follower)
    expected = [evaluate(follower, f, follower_rest) for f in range(1, 6)]
    capture(
        SimpleNamespace(input=source, proxy="ClothProxy", start=1, end=5, output=cache)
    )
    embed(
        SimpleNamespace(
            input=source,
            cache=cache,
            output=destination,
            report=None,
            set_range=True,
            tolerance=1e-5,
        )
    )
    report = json.loads(destination.with_suffix(".cloth.json").read_text())
    assert report["passed"]
    ob = bpy.data.objects["ClothProxy"]
    native = bpy.data.objects[report["native_backup"]]
    assert not list(ob.modifiers) and any(m.type == "CLOTH" for m in native.modifiers)
    assert native.data.shape_keys.key_blocks.get("Guide") is not None
    assert ob.data.shape_keys.animation_data.action is None
    assert len(ob.data.shape_keys.animation_data.nla_tracks) == 1
    follower = bpy.data.objects["RenderFollower"]
    maximum = 0.0
    for frame, (v, matrix) in enumerate(expected, 1):
        actual, actual_matrix = evaluate(follower, frame, follower_rest)
        maximum = max(maximum, float(np.max(np.abs(actual - v))))
        assert np.allclose(actual_matrix, matrix, atol=1e-6)
    assert maximum < 1e-5, maximum
    require_error(
        lambda: embed(
            SimpleNamespace(
                input=destination, cache=cache, output=root / "bad.blend", report=None
            )
        ),
        "exact source",
    )
    # The final blend must also work after the native disk-cache directory is unavailable.
    for directory in root.glob("blendcache_*"):
        directory.rename(directory.with_name("unavailable_" + directory.name))
    bpy.ops.wm.open_mainfile(filepath=str(destination))
    ob = bpy.data.objects["ClothProxy"]
    rest = rest_surface(ob)
    with np.load(cache, allow_pickle=False) as data:
        for frame, v in zip(data["frames"], data["positions"]):
            actual, _ = evaluate(ob, frame, rest)
            assert np.max(np.abs(actual - v)) < 1e-5
    report["render_follower_max_error"] = maximum
    report["works_without_native_cache"] = True
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--work-dir", type=Path, required=True)
    args = p.parse_args(argv)
    root = args.work_dir.resolve()
    if bpy.data.filepath or (root.exists() and any(root.iterdir())):
        raise ValueError("Use factory startup and an empty work directory")
    root.mkdir(parents=True, exist_ok=True)
    report = {
        "contacts": contact_fixture(),
        "cloth": cloth_fixture(root),
        "passed": True,
    }
    (root / "cloth_contact_regression.json").write_text(json.dumps(report, indent=2))
    print("CLOTH_CONTACT_REGRESSION", json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
