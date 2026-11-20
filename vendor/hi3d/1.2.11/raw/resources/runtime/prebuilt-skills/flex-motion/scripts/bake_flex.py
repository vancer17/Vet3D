"""Aim an existing pose bone at an armature-space direction. Run inside Blender.

The spring step lives in flex_motion.py and does not import bpy. This module only
writes the bone rotation that points the rest axis at the simulated tip.
"""

from __future__ import annotations


def aim_pose_bone(pose_bone, desired_direction):
    """Rotate pose_bone so its axis matches desired_direction in armature space.

    Location and scale channels are left unchanged. The direction must be finite
    and non-zero. Parent pose is included, so call this after the parent chain
    has been updated.
    """
    import math

    import mathutils

    desired = mathutils.Vector(desired_direction)
    if desired.length < 1e-8 or not all(math.isfinite(component) for component in desired):
        raise ValueError("desired bone direction is degenerate")
    desired.normalize()
    hint = pose_bone.x_axis
    x_axis = hint - desired * hint.dot(desired)
    if x_axis.length < 1e-6:
        x_axis = pose_bone.z_axis.cross(desired)
    if x_axis.length < 1e-6:
        raise ValueError("cannot build a bone basis")
    x_axis.normalize()
    z_axis = x_axis.cross(desired)
    z_axis.normalize()
    rotation = mathutils.Matrix((
        (x_axis.x, desired.x, z_axis.x),
        (x_axis.y, desired.y, z_axis.y),
        (x_axis.z, desired.z, z_axis.z),
    )).to_4x4()
    basis = mathutils.Matrix.Translation(pose_bone.head) @ rotation
    if pose_bone.parent:
        parent_pose = pose_bone.parent.matrix
        parent_rest = pose_bone.parent.bone.matrix_local
        rest = pose_bone.bone.matrix_local
        channel = (parent_rest.inverted() @ rest).inverted() @ parent_pose.inverted() @ basis
    else:
        channel = pose_bone.bone.matrix_local.inverted() @ basis
    pose_bone.rotation_mode = "QUATERNION"
    pose_bone.rotation_quaternion = channel.to_quaternion()
