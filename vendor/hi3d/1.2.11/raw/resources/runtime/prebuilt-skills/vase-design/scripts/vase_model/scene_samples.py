"""Explicit Blender pose sampling; no collision policy or product roles."""
import math
import bpy
from mathutils import Vector
if __package__:
    from .mesh_snapshot import mesh_snapshot
else:
    from mesh_snapshot import mesh_snapshot


def sample_frames(scene, frames, inspect):
    """Return inspect(frame) results; always restore frame and subframe."""
    frames=list(frames)
    if bpy.context.scene != scene or not frames or any(not math.isfinite(f) for f in frames):
        raise ValueError('Active scene and nonempty finite frame samples required')
    original=(scene.frame_current,scene.frame_subframe)
    try:
        results=[]
        for frame in frames:
            whole=math.floor(frame);scene.frame_set(whole,subframe=frame-whole)
            bpy.context.view_layer.update();results.append(inspect(frame))
        return results
    finally:
        scene.frame_set(original[0],subframe=original[1]);bpy.context.view_layer.update()


def world_mesh(obj, *, evaluated=True):
    data = mesh_snapshot(obj, evaluated=evaluated, space='world')
    points = [Vector(row) for row in data['vertices']]
    faces = [tuple(row) for row in data['triangles']]
    if not points or not faces or any(not math.isfinite(x) for v in points for x in v):
        raise ValueError('Empty or nonfinite collision mesh: '+obj.name)
    return points, faces, tuple(row.tolist() for row in data['bounds'])
