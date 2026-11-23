"""Synthetic behavioral checks; run in Blender with -- --work-dir NEW_EMPTY_DIRECTORY."""

import bpy
import json
import math
from pathlib import Path
from mathutils import Vector
import argparse
from types import SimpleNamespace
from .stage_ops import clip, orient, text_edit
from rigging.blend_common import save_candidate, curves
from .render_samples import sample_frames
import numpy as np
from mathutils import Matrix


from render_engine import set_engine

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", required=True)
    a = parser.parse_args(argv)
    ROOT = Path(a.work_dir).resolve()
    if bpy.data.filepath:
        raise ValueError("Run in --factory-startup; do not replace a loaded project")
    if ROOT.exists() and any(ROOT.iterdir()):
        raise ValueError("Self-test needs a new empty work directory")
    ROOT.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    s = bpy.context.scene
    set_engine(s)
    s.render.fps = 30
    s.frame_start = 181
    s.frame_end = 185
    s.render.resolution_x = 128
    s.render.resolution_y = 96
    s.render.resolution_percentage = 100
    rigs = []
    for name, x in [("RigA", -1.0), ("RigB", 1.0)]:
        arm = bpy.data.armatures.new(name + "Data")
        rig = bpy.data.objects.new(name, arm)
        s.collection.objects.link(rig)
        bpy.context.view_layer.objects.active = rig
        rig.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        b = arm.edit_bones.new("head")
        b.head = (0, 0, 0)
        b.tail = (0, 0, 1)
        bpy.ops.object.mode_set(mode="OBJECT")
        rig.location.x = x
        mesh = bpy.data.meshes.new(name + "Mesh")
        mesh.from_pydata([(-0.25, 0, 0), (0.25, 0, 0), (0, 0, 1)], [], [(0, 1, 2)])
        mesh.uv_layers.new()
        ob = bpy.data.objects.new(name + "Surface", mesh)
        s.collection.objects.link(ob)
        ob.parent = rig
        g = ob.vertex_groups.new(name="head")
        g.add([0, 1, 2], 1, "REPLACE")
        mod = ob.modifiers.new("Skin", "ARMATURE")
        mod.object = rig
        action = bpy.data.actions.new(name + "Old")
        action.use_fake_user = True
        rig.animation_data_create()
        rig.animation_data.action = action
        p = rig.pose.bones["head"]
        p.rotation_mode = "XYZ"
        for fr in [181, 183, 185]:
            p.rotation_euler.z = (fr - 181) * 0.15
            p.location.x = (fr - 181) * 0.02
            p.keyframe_insert("rotation_euler", frame=fr)
            p.keyframe_insert("location", frame=fr)
        rig.animation_data.action = None
        tr = rig.animation_data.nla_tracks.new()
        tr.strips.new(action.name, 181, action)
        rigs.append(rig)
        rig.select_set(False)
    # An unselected user of RigA's Action must retain its shared source action.
    c = bpy.data.objects.new("UnselectedRig", rigs[0].data.copy())
    s.collection.objects.link(c)
    c.animation_data_create()
    c.animation_data.action = bpy.data.actions["RigAOld"]
    for name, body, pos in [
        ("MainTitle", "Fixture", (0, 1, 1.7)),
        ("Nameplate", "Person", (-1, -0.2, 0)),
    ]:
        cu = bpy.data.curves.new(name, "FONT")
        cu.body = body
        ob = bpy.data.objects.new(name, cu)
        s.collection.objects.link(ob)
        ob.location = pos
        ob.rotation_euler.x = math.pi / 2
    other = bpy.data.objects.new("OtherTitle", bpy.data.objects["MainTitle"].data)
    s.collection.objects.link(other)
    other.location = (0, 1, 3)
    bpy.ops.object.light_add(type="AREA", location=(0, -3, 4))
    light = bpy.context.object
    light.name = "Key"
    light.data.energy = 500
    bpy.ops.object.camera_add(location=(0, -6, 3))
    s.camera = bpy.context.object
    s.camera.rotation_euler = (
        (Vector((0, 0, 0.8)) - s.camera.location).to_track_quat("-Z", "Y").to_euler()
    )
    bpy.ops.object.empty_add()
    fx = bpy.context.object
    fx.name = "FX"
    for fr, value in [(1, 0), (9, 2)]:
        fx.location.x = value
        fx.keyframe_insert("location", frame=fr)
    fx.animation_data.action.name = "FXAction"
    expected = {}
    for fr in range(181, 186):
        s.frame_set(fr)
        expected[str(fr)] = {
            rig.name: [list(r) for r in rig.pose.bones["head"].matrix] for rig in rigs
        }
    (ROOT / "expected.json").write_text(json.dumps(expected))
    (ROOT / "text.json").write_text(
        json.dumps(
            {
                "set": [
                    {"object": "MainTitle", "text": "Custom Title", "max_width": 4}
                ],
                "remove": ["Nameplate"],
            }
        )
    )
    s.frame_set(181)
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "source.blend"))

    fx_expected = [
        curves(bpy.data.actions["FXAction"])[0].evaluate(t) for t in [1, 3, 5, 7, 9]
    ]
    options = SimpleNamespace(
        source_start=181,
        source_end=185,
        start=0,
        rigs=["RigA", "RigB"],
        stage_actions=["FXAction"],
        stage_source_start=1,
        stage_source_end=9,
        rebase_markers=True,
        output=str(ROOT / "clip.blend"),
        report=None,
        pack=False,
    )
    save_candidate(options, clip(options))
    worst_pose = 0.0
    for fr in range(5):
        bpy.context.scene.frame_set(fr)
        for name in ["RigA", "RigB"]:
            rig = bpy.data.objects[name]
            worst_pose = max(
                worst_pose,
                float(
                    abs(
                        np.array(rig.pose.bones["head"].matrix)
                        - np.array(expected[str(fr + 181)][name])
                    ).max()
                ),
            )
            assert (
                rig.animation_data.action is None
                and len(rig.animation_data.nla_tracks) == 1
            )
        assert abs(bpy.data.objects["FX"].location.x - fx_expected[fr]) < 1e-5
    assert worst_pose < 1e-5
    assert bpy.data.objects["UnselectedRig"].animation_data.action.name == "RigAOld"
    assert bpy.data.actions.get("RigBOld") is None
    bpy.context.scene.frame_set(3)

    def world_points():
        values = {}
        for name in ["RigASurface", "RigBSurface"]:
            ob = bpy.data.objects[name]
            ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
            me = ev.to_mesh()
            values[name] = np.array([ev.matrix_world @ v.co for v in me.vertices])
            ev.to_mesh_clear()
        return values

    before = world_points()
    origins = {
        name: np.array(bpy.data.objects[name].matrix_world.translation)
        for name in ["RigA", "RigB"]
    }
    options.output = str(ROOT / "oriented.blend")
    options.degrees = 90
    save_candidate(options, orient(options))
    after = world_points()
    rotation = np.array(Matrix.Rotation(np.pi / 2, 3, "Z"))
    worst_rotation = 0.0
    for name in ["RigA", "RigB"]:
        target = (before[name + "Surface"] - origins[name]) @ rotation.T + origins[name]
        worst_rotation = max(
            worst_rotation, float(abs(after[name + "Surface"] - target).max())
        )
        assert (
            float(
                abs(
                    np.array(bpy.data.objects[name].matrix_world.translation)
                    - origins[name]
                ).max()
            )
            < 1e-6
        )
    assert worst_rotation < 1e-5
    options.output = str(ROOT / "text.blend")
    options.spec = str(ROOT / "text.json")
    save_candidate(options, text_edit(options))
    assert bpy.data.objects["MainTitle"].data.body == "Custom Title"
    assert bpy.data.objects["OtherTitle"].data.body == "Fixture"
    assert bpy.data.objects.get("Nameplate") is None
    assert sample_frames(0, 359, 30, 1) == list(range(0, 360, 30))
    assert sample_frames(0, 4, 30, 0.1) == [0, 3]
    report = {
        "pass": True,
        "pose_matrix_max_error": worst_pose,
        "world_vertex_rotation_max_error": worst_rotation,
        "shared_action_preserved": True,
        "shared_text_protected": True,
        "sampling_off_by_one_checked": True,
    }
    (ROOT / "self_test_report.json").write_text(json.dumps(report, indent=2))
    print("SELF_TEST_COMPLETE", json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
