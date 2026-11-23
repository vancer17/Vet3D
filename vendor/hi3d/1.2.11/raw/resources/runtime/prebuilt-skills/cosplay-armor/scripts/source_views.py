"""Render six source inspection views with an explicit caller-owned lighting profile."""
from pathlib import Path
import bpy
from mathutils import Vector
from preview_scene import area_light


def render_source_views(obj, out, height_mm, *, extent_factor, light_energy,
                        light_size, light_distance, camera_distance, world_name,
                        replace_world=False):
    """Modify an isolated scene and render front/back/left/right/top/hero PNGs.

    Scene distances are metres; height_mm locates the normalized source center.
    Caller supplies an existing output directory and decides whether to run views.
    """
    out = Path(out)
    height = float(height_mm)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = 12
    sc.cycles.use_denoising = True
    sc.render.threads_mode = 'FIXED'
    sc.render.threads = 2
    sc.render.resolution_x = 600
    sc.render.resolution_y = 600
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = 'AgX'
    sc.world = bpy.data.worlds.new(world_name) if replace_world or sc.world is None else sc.world
    sc.world.color = (0.3, 0.3, 0.3)
    center = Vector((0, 0, height / 2000))
    extent = max(obj.dimensions) * extent_factor
    for name, loc in [('key', (-1, -2, 2)), ('fill', (2, -1, 1)), ('back', (0, 2, 2))]:
        area_light(name, center + Vector(loc) * light_distance, center,
                   light_energy, light_size, (1, 1, 1),
                   collection=bpy.context.collection, shape='SQUARE')
    d = bpy.data.cameras.new('Review camera')
    d.type = 'ORTHO'
    d.ortho_scale = extent
    cam = bpy.data.objects.new('Review camera', d)
    bpy.context.collection.objects.link(cam)
    sc.camera = cam
    for name, di in [('front', (0, -1, 0)), ('back', (0, 1, 0)), ('left', (-1, 0, 0)), ('right', (1, 0, 0)), ('top', (0, 0, 1)), ('hero', (1, -2, 1))]:
        cam.location = center + Vector(di).normalized() * camera_distance
        cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = str(out / (name + '.png'))
        bpy.ops.render.render(write_still=True)
