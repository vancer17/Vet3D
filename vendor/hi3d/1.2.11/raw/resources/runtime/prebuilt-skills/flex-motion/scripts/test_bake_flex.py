"""Blender check: a child bone aims at a direction while its parent is posed."""

import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bake_flex import aim_pose_bone


def main():
    bpy.ops.object.armature_add(location=(0, 0, 0))
    armature = bpy.context.object
    bpy.ops.object.mode_set(mode="EDIT")
    body = armature.data.edit_bones[0]
    body.name = "Body"
    body.head = (0.0, 0.0, 0.0)
    body.tail = (0.0, 0.4, 0.0)
    flex = armature.data.edit_bones.new("Flex_sleeve_01")
    flex.head = (0.0, 0.4, 0.0)
    flex.tail = (0.0, 0.7, 0.0)
    flex.parent = body
    flex.use_connect = True
    bpy.ops.object.mode_set(mode="POSE")
    body_pose = armature.pose.bones["Body"]
    body_pose.rotation_mode = "XYZ"
    body_pose.rotation_euler[2] = math.radians(35)
    bpy.context.view_layer.update()
    flex_pose = armature.pose.bones["Flex_sleeve_01"]
    rest_length = flex_pose.bone.length
    desired = Vector((0.25, 0.85, -0.15)).normalized()
    aim_pose_bone(flex_pose, desired)
    bpy.context.view_layer.update()
    aimed = (flex_pose.tail - flex_pose.head).normalized()
    if aimed.dot(desired) < 0.999:
        raise SystemExit("aimed direction mismatch: " + str(aimed))
    if abs((flex_pose.tail - flex_pose.head).length - rest_length) > 1e-4:
        raise SystemExit("bone length changed")
    if abs(flex_pose.location.length) > 1e-5:
        raise SystemExit("aim wrote a location channel")
    print("bake-flex-aim-ok")


if __name__ == "__main__":
    main()
