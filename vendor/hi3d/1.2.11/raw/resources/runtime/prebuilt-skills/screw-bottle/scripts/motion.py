"""Rigid screw animation in a caller-owned mm scene."""
import math
import bpy
from mathutils import Vector
from blender_ops import screw_matrix
from geometry import finite, integer, screw_lift


def action_curves(action):
    if hasattr(action, 'layers'):
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    yield from bag.fcurves
    else:
        yield from action.fcurves


def animate_screw(objects, center_mm, axis, pitch_mm, frames_angles, *, hand=1, name='Screw control'):
    """Parent closed meshes without moving them, then keyframe the same pitch law as checks.

    Refuse existing animation/constraints/parenting rather than silently replacing it.
    Free lift after thread release is a separate task-specific motion.
    """
    if not objects or len(set(objects)) != len(objects):
        raise ValueError('Distinct moving objects required')
    if any(o.parent or o.animation_data or o.constraints for o in objects):
        raise ValueError('Bake or preserve existing controls explicitly before adding screw animation')
    if len(frames_angles) < 2 or frames_angles[0][1] != 0:
        raise ValueError('At least two keys, starting closed, required')
    previous = None
    for frame, degrees in frames_angles:
        integer(frame, 'frame', 0)
        if previous is not None and frame <= previous:
            raise ValueError('Key frames must increase')
        previous = frame
        lift = screw_lift(pitch_mm, math.radians(finite(degrees, 'angle_deg')), hand)
        if lift < 0:
            raise ValueError('Opening keys cannot move into the body')
    screw_matrix(center_mm, axis, 0, 0)
    normal = Vector(axis).normalized(); center = Vector(center_mm)
    root = bpy.data.objects.new(name, None); bpy.context.collection.objects.link(root)
    root.location = center; root.rotation_mode = 'AXIS_ANGLE'
    root.rotation_axis_angle = (0, *normal)
    bpy.context.view_layer.update()
    for obj in objects:
        world = obj.matrix_world.copy(); obj.parent = root; obj.matrix_world = world
    for frame, degrees in frames_angles:
        angle = math.radians(degrees)
        root.location = center + normal * screw_lift(pitch_mm, angle, hand)
        root.rotation_axis_angle = (angle, *normal)
        root.keyframe_insert(data_path='location', frame=frame)
        root.keyframe_insert(data_path='rotation_axis_angle', frame=frame)
    for curve in action_curves(root.animation_data.action):
        for key in curve.keyframe_points:
            key.interpolation = 'LINEAR'
    bpy.context.scene.frame_set(frames_angles[0][0])
    return root
