"""Small offline Blender fixtures for rest-aware adaptation and protected assets."""

import argparse
from copy import deepcopy
import json
import math
from pathlib import Path
from types import SimpleNamespace
import bpy
import numpy as np
from mathutils import Vector, Quaternion
from .rig_adapter import (
    skeleton,
    skeleton_digest,
    cache_rig,
    calibrate_axes,
    protected_assets,
    bake_action,
    execute,
)
from .retarget_math import retarget_samples, two_bone_ik
from .service_rig import skin_table, write_changed_weights
from .timing import record_stage


def make_rig(name, scale=1, arm_angle=0):
    a = bpy.data.armatures.new(name)
    o = bpy.data.objects.new(name, a)
    bpy.context.scene.collection.objects.link(o)
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    shoulder = Vector((0.1, 0, 0.8))
    r = Quaternion((0, 1, 0), arm_angle)
    elbow = shoulder + r @ Vector((0.35, 0, 0))
    wrist = shoulder + r @ Vector((0.7, 0, 0))
    tip = wrist + r @ Vector((0.12, 0, 0))
    rows = [
        ("hip", (0.0, 0, 0.5), (0.0, 0, 0.8), None),
        ("arm", shoulder, elbow, "hip"),
        ("fore", elbow, wrist, "arm"),
        ("finger", wrist, tip, "fore"),
        ("thigh", (0.1, 0, 0.5), (0.1, 0, 0.25), "hip"),
        ("shin", (0.1, 0, 0.25), (0.1, 0, 0), "thigh"),
        ("foot", (0.1, 0, 0), (0.1, -0.1, 0), "shin"),
    ]
    for n, h, t, p in rows:
        b = a.edit_bones.new(n)
        b.head = Vector(h) * scale
        b.tail = Vector(t) * scale
        if p:
            b.parent = a.edit_bones[p]
    bpy.ops.object.mode_set(mode="OBJECT")
    o.select_set(False)
    for b in o.pose.bones:
        b.rotation_mode = "QUATERNION"
    return o


def fixture(root):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    source = make_rig("Source", 1, 0.4)
    for f in range(3):
        source.location = (0, 0.05 * f, 0)
        source.keyframe_insert("location", frame=f)
        source.pose.bones["hip"].location = (0.1 * f, 0, 0)
        source.pose.bones["hip"].keyframe_insert("location", frame=f)
        source.pose.bones["fore"].rotation_quaternion = Quaternion((0, 0, 1), f * 0.2)
        source.pose.bones["fore"].keyframe_insert("rotation_quaternion", frame=f)
        source.pose.bones["finger"].rotation_quaternion = Quaternion((0, 0, 1), f * 0.3)
        source.pose.bones["finger"].keyframe_insert("rotation_quaternion", frame=f)
    foot_goal = bpy.data.objects.new("SourceFootGoal", None)
    bpy.context.scene.collection.objects.link(foot_goal)
    foot_goal.location = (0.1, -0.06, 0.07)
    ik = source.pose.bones["shin"].constraints.new("IK")
    ik.target = foot_goal
    ik.chain_count = 2
    ik.use_stretch = False
    cache = cache_rig(source, [0, 1, 2])
    foot_index = cache["names"].index("foot")
    assert np.allclose(
        cache["poses"][:, foot_index, :3, 3], [0.1, -0.06, 0.07], atol=0.002
    )
    cache["fps"] = 30
    target = make_rig("Target", 2, 0)
    mesh = bpy.data.meshes.new("skin")
    mesh.from_pydata([(0, 0, 1), (0.1, 0, 1), (0.05, 0.1, 1)], [], [(0, 1, 2)])
    body = bpy.data.objects.new("Body", mesh)
    bpy.context.scene.collection.objects.link(body)
    for n in ["fore", "hip", "arm"]:
        g = body.vertex_groups.new(name=n)
        g.add([0, 1, 2], {"fore": 0.2, "hip": 0.3, "arm": 0.5}[n], "REPLACE")
    body.modifiers.new("Armature", "ARMATURE").object = target
    mesh.uv_layers.new(name="UVMap")
    image = bpy.data.images.new("fixture texture", 2, 2)
    image.pack()
    prop = bpy.data.objects.new("HeldProp", mesh.copy())
    bpy.context.scene.collection.objects.link(prop)
    prop.parent = target
    prop.parent_type = "BONE"
    prop.parent_bone = "fore"
    prop.location = (0.05, 0.01, 0)
    bpy.ops.wm.save_as_mainfile(filepath=str(root / "source.blend"))
    return source, target, body, cache


def run(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    s, t, body, cache = fixture(root)
    target = skeleton(t)
    mapping = {n: {"source": n} for n in target["names"]}
    mapping["arm"].update(target_end="fore", source_end="fore")
    mapping["fore"].update(target_end="finger", source_end="finger")
    mapping["finger"].update(
        mode="local", alignment_wxyz=[math.cos(0.2), 0, math.sin(0.2), 0]
    )
    spec = {
        "calibrated": True,
        "mapping": mapping,
        "root": {
            "target": "hip",
            "source": "hip",
            "source_chain": ["thigh", "shin", "foot"],
            "target_chain": ["thigh", "shin", "foot"],
        },
    }
    spec["limbs"] = [
        {
            "target_chain": ["thigh", "shin", "foot"],
            "source_chain": ["thigh", "shin", "foot"],
            "pole": [0, -1, 0],
        }
    ]
    q, loc, r = retarget_samples(cache, target, spec)
    assert abs(r["scale"] - 2) < 1e-5
    assert np.allclose(loc[:, 0], [0, 0.2, 0.4], atol=1e-6)
    assert np.allclose(loc[:, 2], [0, -0.1, -0.2], atol=1e-6)
    assert np.allclose(np.linalg.norm(q, axis=2), 1, atol=1e-6)
    assert np.all(np.sum(q[1:] * q[:-1], axis=2) >= 0)
    # Local finger rotation measures only that joint, excluding animated forearm.
    fi = target["names"].index("finger")
    assert abs(Quaternion(q[2, fi]).angle - 0.6) < 1e-5
    # Root offsets and in-place translation must move all IK goals together.
    shifted = deepcopy(spec)
    shifted["root"]["offset"] = [0.8, -0.4, 0.1]
    shifted_q, shifted_loc, _ = retarget_samples(cache, target, shifted)
    assert np.allclose(shifted_q, q, atol=2e-5)
    assert not np.allclose(shifted_loc, loc)
    shifted["root"]["in_place"] = True
    inplace_q, inplace_loc, _ = retarget_samples(cache, target, shifted)
    assert np.allclose(inplace_q, q, atol=2e-5)
    assert np.allclose(inplace_loc, inplace_loc[0], atol=1e-6)
    # Unmapped/local descendants inherit the newly solved parent, not its old pose.
    altered = {**cache, "poses": cache["poses"].copy()}
    foot = target["names"].index("foot")
    altered["poses"][:, cache["names"].index("foot"), 1, 3] += 0.07
    for local in [False, True]:
        dependent = deepcopy(spec)
        if local:
            dependent["mapping"]["foot"]["mode"] = "local"
        else:
            del dependent["mapping"]["foot"]
        dependent_q, _, _ = retarget_samples(altered, target, dependent)
        assert np.allclose(np.abs(dependent_q[:, foot, 0]), 1, atol=1e-5)
        assert np.allclose(dependent_q[:, foot, 1:], 0, atol=1e-5)
    invalid_limb = deepcopy(spec)
    invalid_limb["limbs"][0]["source_chain"] = ["hip", "shin", "foot"]
    try:
        retarget_samples(cache, target, invalid_limb)
    except ValueError:
        pass
    else:
        raise AssertionError("Disconnected source limb accepted")
    corrupted = {**cache, "poses": cache["poses"].copy()}
    corrupted["poses"][0, 0, 0, 0] *= 2
    try:
        retarget_samples(corrupted, target, spec)
    except ValueError:
        pass
    else:
        raise AssertionError("Scaled cache accepted")
    before = protected_assets()
    bake_action(t, target["names"], q, loc, "hip", 0, "FixtureMotion")
    assert protected_assets() == before
    bpy.context.scene.frame_set(0)
    expected = Vector(cache["rest"][cache["names"].index("fore"), :3, 3]) - Vector(
        cache["rest"][cache["names"].index("arm"), :3, 3]
    )
    actual = t.pose.bones["fore"].head - t.pose.bones["arm"].head
    assert actual.normalized().dot(expected.normalized()) > 0.99999
    for goal in [(1, 0.3, 0), (3, 0, 0)]:
        knee, ankle, error = two_bone_ik((0, 0, 0), goal, 1, 1, (0, 1, 0))
        assert abs(knee.length - 1) < 1e-6 and abs((ankle - knee).length - 1) < 1e-6
    try:
        two_bone_ik((0, 0, 0), (1, 0, 0), 1, 1, (1, 0, 0))
    except ValueError:
        pass
    else:
        raise AssertionError("Parallel pole accepted")
    # Existing membership order must survive a changed positive weight.
    names, old = skin_table(body, t)
    updated = old.copy()
    updated[0, names.index("fore")] += 0.01
    updated[0, names.index("arm")] -= 0.01
    order = [g.group for g in body.data.vertices[0].groups]
    write_changed_weights(body, names, old, updated)
    assert [g.group for g in body.data.vertices[0].groups] == order
    assert np.array_equal(skin_table(body, t)[1][1:], old[1:])
    # Reject rest-axis edits on an active animation before touching data.
    cal = {
        "calibrated": True,
        "rig_sha256": skeleton_digest(skeleton(t)),
        "bones": {"arm": {"tail_at": "fore", "roll_axis": [0, 0, 1]}},
    }
    try:
        calibrate_axes(t, cal)
    except ValueError:
        pass
    else:
        raise AssertionError("Animated calibration accepted without replacement")
    t.animation_data_clear()
    heads = skeleton(t)["heads"].copy()
    calibrate_axes(t, cal)
    assert np.array_equal(skeleton(t)["heads"], heads)
    # Exercise full saved/reopened CLI adapters with source and target files.
    bpy.ops.wm.open_mainfile(filepath=str(root / "source.blend"))
    cache_args = SimpleNamespace(
        operation="cache",
        input=str(root / "source.blend"),
        rig="Source",
        report=str(root / "cache.json"),
        output=str(root / "cache.npz"),
        start=0,
        end=2,
        fps=30,
        source_fps=30,
    )
    execute(cache_args)
    t = bpy.data.objects["Target"]
    spec["rig_sha256"] = skeleton_digest(skeleton(t))
    from .io_utils import file_digest

    spec["cache_sha256"] = file_digest(root / "cache.npz")
    (root / "mapping.json").write_text(json.dumps(spec))
    a = SimpleNamespace(
        operation="retarget",
        input=str(root / "source.blend"),
        rig="Target",
        report=str(root / "adapt.json"),
        output=str(root / "result.blend"),
        spec=str(root / "mapping.json"),
        cache=str(root / "cache.npz"),
        frame_start=10,
        action="MappedMotion",
        replace_animation=False,
    )
    execute(a)
    assert bpy.context.scene.frame_start == 10 and bpy.context.scene.frame_end == 12
    assert bpy.data.objects["Target"].animation_data.action.name == "MappedMotion"
    assert bpy.data.objects["Source"].animation_data.action is not None
    assert json.loads((root / "adapt.json").read_text())["protected_assets_preserved"]
    # Errors and successes both retain stage/attempt scope.
    with record_stage(root / "timings.jsonl", "fixture", "success"):
        pass
    try:
        with record_stage(root / "timings.jsonl", "fixture", "failure"):
            raise ValueError("fixture")
    except ValueError:
        pass
    records = [json.loads(x) for x in (root / "timings.jsonl").read_text().splitlines()]
    assert [x["status"] for x in records] == ["complete", "failed_or_interrupted"]
    assert all(x["seconds"] >= 0 and "+" in x["start"] for x in records)
    result = {
        "rest_alignment": True,
        "local_fingers": True,
        "root_scale": True,
        "source_object_motion": True,
        "source_ik_evaluated": True,
        "limb_sequence_adapted": True,
        "ik_root_offset_in_place": True,
        "ik_local_descendants": True,
        "disconnected_limb_rejected": True,
        "bone_parented_prop": True,
        "scaled_cache_rejected": True,
        "fixed_limb_lengths": True,
        "weight_order_preserved": True,
        "saved_reopened": True,
        "protected_assets": True,
        "timing": True,
    }
    (root / "checks.json").write_text(json.dumps(result, indent=2))
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--work", required=True)
    print(json.dumps(run(p.parse_args(argv).work)))
    return 0
