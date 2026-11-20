"""Blender-only synthetic export/bind/repair regression; no remote calls or user assets."""

import argparse
import json
import struct
from pathlib import Path
import bpy
import numpy as np
from . import service_rig as api
from .io_utils import file_digest
from .validate_blend import validate


def run(work):
    work = Path(work)
    if work.exists():
        raise ValueError("Use a new test directory")
    work.mkdir(parents=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    data = bpy.data.armatures.new("Skeleton")
    rig = bpy.data.objects.new("Skeleton", data)
    bpy.context.scene.collection.objects.link(rig)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    for name, x in [("hand.A", 1), ("hand.B", -1)]:
        bone = data.edit_bones.new(name)
        bone.head = (x, 0, 0)
        bone.tail = (x, 0.1, 0)
    bpy.ops.object.mode_set(mode="OBJECT")
    vertices = [
        (1, 0, 0),
        (1.005, 0, 0),
        (1, 0.005, 0),
        (-1, 0, 0),
        (-1.005, 0, 0),
        (-1, 0.005, 0),
    ]
    mesh = bpy.data.meshes.new("Surface")
    mesh.from_pydata(vertices, [], [(0, 1, 2), (3, 5, 4)])
    body = bpy.data.objects.new("Body", mesh)
    bpy.context.scene.collection.objects.link(body)
    uv = mesh.uv_layers.new()
    uv.data.foreach_set("uv", np.linspace(0, 1, 12, dtype=np.float32))
    for name in ["hand.A", "hand.B"]:
        body.vertex_groups.new(name=name)
    body.vertex_groups["hand.A"].add([0, 1, 2], 1, "REPLACE")
    body.vertex_groups["hand.B"].add([3, 4, 5], 1, "REPLACE")
    mod = body.modifiers.new("Skin", "ARMATURE")
    mod.object = rig
    mod.use_deform_preserve_volume = True
    for b in rig.pose.bones:
        b.keyframe_insert("location", frame=1)
    rig.pose.bones["hand.B"].location.x = 1
    rig.pose.bones["hand.B"].keyframe_insert("location", frame=2)
    bpy.context.scene.frame_set(1)
    # A service-like GLB with no animation and no task-specific bone naming.
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    body.select_set(True)
    glb = work / "service.glb"
    bpy.ops.export_scene.gltf(
        filepath=str(glb),
        export_format="GLB",
        use_selection=True,
        export_animations=False,
    )
    bpy.ops.wm.save_as_mainfile(filepath=str(work / "source.blend"))
    source_hash = file_digest(work / "source.blend")
    before_export = api.preserved_signature(body, [g.name for g in body.vertex_groups])
    api.export_body(body, work / "body-only.glb")
    assert (
        api.preserved_signature(body, [g.name for g in body.vertex_groups])
        == before_export
    )
    content = (work / "body-only.glb").read_bytes()
    length = struct.unpack_from("<I", content, 12)[0]
    doc = json.loads(content[20 : 20 + length])
    assert (
        len(doc["meshes"]) == 1 and not doc.get("skins") and not doc.get("animations")
    )
    # Keep the same base mesh as an unbound target with a protected non-bone group.
    body.modifiers.clear()
    body.vertex_groups.clear()
    body.vertex_groups.new(name="attachment").add([0, 2], 0.37, "REPLACE")
    solid = body.modifiers.new("Thickness", "SOLIDIFY")
    solid.thickness = 0.02
    bpy.data.objects.remove(rig, do_unlink=True)
    protected = api.preserved_signature(body, ["attachment"])
    bpy.ops.wm.save_as_mainfile(filepath=str(work / "unbound.blend"))
    api.main(
        [
            "bind",
            "--input",
            str(work / "unbound.blend"),
            "--body",
            "Body",
            "--rigged-glb",
            str(glb),
            "--targets",
            "Body",
            "--alignment-tolerance",
            ".0001",
            "--output",
            str(work / "bound.blend"),
            "--report",
            str(work / "bind.json"),
        ]
    )
    body = bpy.data.objects["Body"]
    rig = body.find_armature()
    assert api.preserved_signature(body, ["attachment"]) == protected
    assert [m.type for m in body.modifiers] == ["ARMATURE", "SOLIDIFY"]
    assert abs(body.modifiers["Thickness"].thickness - 0.02) < 1e-7
    body.modifiers["Thickness"].show_viewport = False
    # Introduce one wrong contralateral influence and prove the saved-pose check finds it.
    body.vertex_groups["hand.A"].add([0], 0.8, "REPLACE")
    body.vertex_groups["hand.B"].add([0], 0.2, "REPLACE")
    sibling = body.copy()
    sibling.name = "Unedited sibling"
    bpy.context.scene.collection.objects.link(sibling)
    for b in rig.pose.bones:
        b.keyframe_insert("location", frame=1)
    rig.pose.bones["hand.B"].location.x = 1
    rig.pose.bones["hand.B"].keyframe_insert("location", frame=2)
    bpy.context.scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(work / "bad.blend"))
    bad = api.inspect_skin(body, rig, [1, 2], 1.8)
    assert not bad["pass"] and bad["frames"][1]["worst"]
    collection = bpy.data.collections.new("CheckParts")
    bpy.context.scene.collection.children.link(collection)
    collection.objects.link(body)
    assert not validate(collection.name, rig, [1, 2], 1.8)["pass"]
    bpy.context.scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(work / "bad.blend"))
    rules = {k: bad[k] for k in ["mesh_sha256", "bone_names", "rig_sha256"]}
    rules["regions"] = [
        dict(bounds=[[0.9, -0.1, -0.1], [1.2, 0.1, 0.1]], forbidden_bones=["hand.B"])
    ]
    (work / "rules.json").write_text(json.dumps(rules))
    api.main(
        [
            "repair",
            "--input",
            str(work / "bad.blend"),
            "--body",
            "Body",
            "--rules",
            str(work / "rules.json"),
            "--output",
            str(work / "repaired.blend"),
            "--report",
            str(work / "repair.json"),
        ]
    )
    api.main(
        [
            "inspect",
            "--input",
            str(work / "repaired.blend"),
            "--body",
            "Body",
            "--frames",
            "1:2",
            "--height",
            "1.8",
            "--report",
            str(work / "after.json"),
        ]
    )
    assert json.loads((work / "after.json").read_text())["pass"]
    sibling = bpy.data.objects["Unedited sibling"]
    assert abs(sibling.vertex_groups["hand.B"].weight(0) - 0.2) < 1e-6
    assert sibling.data != bpy.data.objects["Body"].data
    assert validate(
        "CheckParts", bpy.data.objects["Body"].find_armature(), [1, 2], 1.8
    )["pass"]
    assert (
        api.preserved_signature(bpy.data.objects["Body"], ["attachment"]) == protected
    )
    assert file_digest(work / "source.blend") == source_hash
    # Stale mesh/calibration identity must fail before a candidate is saved.
    rules["rig_sha256"] = "stale"
    (work / "stale.json").write_text(json.dumps(rules))
    try:
        api.main(
            [
                "repair",
                "--input",
                str(work / "bad.blend"),
                "--body",
                "Body",
                "--rules",
                str(work / "stale.json"),
                "--output",
                str(work / "rejected.blend"),
                "--report",
                str(work / "rejected.json"),
            ]
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Stale calibration was accepted")
    assert not (work / "rejected.blend").exists()
    body = bpy.data.objects["Body"]
    rig = body.find_armature()
    body.hide_set(True)
    try:
        api.inspect_skin(body, rig, [1, 2], 1.8)
    except ValueError:
        pass
    else:
        raise AssertionError("Hidden body was accepted as evaluated motion")
    print(
        "Service rig export, bind, repair, saved-pose inspection and preservation passed"
    )


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--work", type=Path, required=True)
    run(p.parse_args(argv).work)


if __name__ == "__main__":
    main()
