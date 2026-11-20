"""Head review profile; preserves source geometry and scene units."""
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
from scene_io import create_mesh_object
from material_nodes import principled_material
from preview_scene import area_light

from render_engine import set_engine

def make_mesh(name, vertices, quads, uvs=None):
    obj = create_mesh_object(name, vertices, quads,
                             collection=bpy.context.scene.collection, smooth=True)
    mesh = obj.data
    if uvs is not None:
        layer = mesh.uv_layers.new(name="UVMap")
        layer.data.foreach_set("uv", np.asarray(uvs, np.float32).ravel())
    return obj

def material(name, color=(0.42, 0.48, 0.53, 1), roughness=0.65):
    return principled_material(name, color, roughness=roughness)


def aim(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def render_view(camera, center, span, direction, path):
    camera.location = np.asarray(center) + np.asarray(direction) * span
    aim(camera, center)
    bpy.context.scene.render.filepath = str(Path(path).resolve())
    bpy.ops.render.render(write_still=True)


def studio(bounds, size=900):
    scene = bpy.context.scene
    lo, hi = np.asarray(bounds)
    center = (lo + hi) * 0.5
    span = max(hi - lo)
    set_engine(scene)
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.world = bpy.data.worlds.new("Review World")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (
        0.055,
        0.065,
        0.08,
        1,
    )
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = 0.4
    scene.view_settings.view_transform = "AgX"
    camera_data = bpy.data.cameras.new("Review Camera")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = span * 1.16
    camera = bpy.data.objects.new("Review Camera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    for name, position, energy, diameter in [
        ("Key", (1, -1.8, 1.7), 180, 1.4),
        ("Fill", (-1.2, -0.8, 0.6), 95, 1.8),
        ("Rim", (0.3, 1.4, 1.4), 220, 1.1),
    ]:
        area_light(name, center + np.asarray(position) * span, center,
                   energy * span * span, diameter * span, (1, 1, 1),
                   collection=scene.collection)
    camera.location = center + np.array([0, -3, 0]) * span
    aim(camera, center)
    return camera, center, span
