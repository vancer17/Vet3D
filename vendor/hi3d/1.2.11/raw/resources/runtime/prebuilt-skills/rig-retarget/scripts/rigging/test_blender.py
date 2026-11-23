"""Blender regression fixtures: UV seam welding, joint anchors and wrist loop axes."""

import argparse
import json
import math
import sys
from pathlib import Path
import bpy
import numpy as np
from .blender_core import localized_solve
from .motion import hand_offset, ground_height
from . import prepare_mesh


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--work", type=Path, required=True)
    p.add_argument("--python-packages", type=Path, required=True)
    args = p.parse_args(argv)
    sys.path.append(str(args.python_packages))
    args.work.mkdir(parents=True, exist_ok=True)
    # Two triangles share positions but carry different UV coordinates at the seam.
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    me = bpy.data.meshes.new("UVFixture")
    me.from_pydata(
        [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 0), (1, 0, 1), (0, 0, 1)],
        [],
        [(0, 1, 2), (3, 4, 5)],
    )
    me.update()
    ob = bpy.data.objects.new("UVFixture", me)
    bpy.context.scene.collection.objects.link(ob)
    uv = np.array(
        [(0, 0), (0.4, 0), (0.4, 0.4), (0.6, 0.6), (1, 1), (0.6, 1)], dtype=np.float32
    )
    me.uv_layers.new(name="UVMap").data.foreach_set("uv", uv.ravel())
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    glb = args.work / "uv-fixture.glb"
    prepared = args.work / "uv-prepared.blend"
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format="GLB")
    prepare_mesh.main(
        ["--input", str(glb), "--output", str(prepared), "--height", "1.8"]
    )
    me = bpy.data.objects["CharacterSurface"].data
    assert len(me.vertices) == 4, "UV duplicates were not welded"
    observed = np.empty(len(me.loops) * 2, dtype=np.float32)
    me.uv_layers.active.data.foreach_get("uv", observed)
    assert np.allclose(
        sorted(map(tuple, observed.reshape(-1, 2))), sorted(map(tuple, uv)), atol=1e-6
    ), "Corner UVs changed"
    # Fine joint strip: rigid ends remain exactly fixed and the blend is continuous.
    v = np.array(
        [(x, y, 0) for x in np.linspace(0, 1, 101) for y in [0, 0.02]], dtype=np.float32
    )
    faces = []
    for i in range(100):
        a = i * 2
        faces.extend([(a, a + 1, a + 2), (a + 1, a + 3, a + 2)])
    f = np.array(faces)
    initial = np.zeros((len(v), 2))
    initial[:, 0] = v[:, 0] < 0.5
    initial[:, 1] = 1 - initial[:, 0]
    weights, fixed = localized_solve(v, f, initial, 0.10, 0.05, 1e-6)
    assert np.array_equal(weights[fixed], initial[fixed])
    assert np.allclose(weights.sum(1), 1) and np.all(weights >= 0)
    assert np.any((weights[:, 0] > 0) & (weights[:, 0] < 1))
    assert np.max(abs(np.diff(weights[::2, 0]))) < 0.5
    for side in ["L", "R"]:
        first, last = hand_offset("run", side, 0, 22), hand_offset("run", side, 22, 22)
        assert first.rotation_difference(last).angle < 1e-5
        for style, period in [("run", 22), ("dance", 359)]:
            for frame in range(period + 1):
                q = hand_offset(style, side, frame, period)
                direction = q @ __import__("mathutils").Vector((0, 1, 0))
                bend = math.degrees(
                    direction.angle(__import__("mathutils").Vector((0, 1, 0)))
                )
                assert bend < (9 if style == "run" else 30)
    # Mixed/nested character collection: non-mesh objects and differing transforms
    # must not crash or confuse object-local height with the rig's ground plane.
    from mathutils import Matrix

    parts = bpy.data.collections.new("GroundFixture")
    bpy.context.scene.collection.children.link(parts)
    nested = bpy.data.collections.new("GroundMeshes")
    parts.children.link(nested)
    rig = bpy.data.objects.new("GroundRig", bpy.data.armatures.new("GroundRig"))
    parts.objects.link(rig)
    rig.matrix_world = Matrix.Translation((3, 4, 10)) @ Matrix.Rotation(0.6, 4, "Z")
    parts.objects.link(bpy.data.objects.new("NonMesh", None))
    mesh = bpy.data.meshes.new("GroundMesh")
    mesh.from_pydata([(0, 0, -0.25), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
    ground = bpy.data.objects.new("GroundMesh", mesh)
    nested.objects.link(ground)
    ground.matrix_world = rig.matrix_world @ Matrix.Translation((0, 0, 2))
    empty = bpy.data.objects.new("EmptyMesh", bpy.data.meshes.new("EmptyMesh"))
    parts.objects.link(empty)
    bpy.context.view_layer.update()
    assert abs(ground_height(rig, parts.name) - 1.75) < 1e-6
    missing = bpy.data.collections.new("NoVertices")
    bpy.context.scene.collection.children.link(missing)
    for name in [missing.name, "MissingCollection"]:
        try:
            ground_height(rig, name)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid grounding collection must fail: " + name)
    report = dict(
        uv_weld_vertices=4,
        uv_corners_preserved=True,
        rigid_anchors_preserved=True,
        normalized_weights=True,
        run_loop_closed=True,
        wrist_axes_valid=True,
        mixed_collection_grounding=True,
        rig_space_ground_height=1.75,
        invalid_ground_collection_rejected=True,
    )
    (args.work / "regression.json").write_text(json.dumps(report, indent=2))
    print("REGRESSION", json.dumps(report))


if __name__ == "__main__":
    main()
