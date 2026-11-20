"""Render a textured head mesh from the front for the head/hair label workflow.

Run inside Blender:
  blender --background --factory-startup --python render_head_hair_reference.py -- input.glb output.png camera.json
"""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from asset_scene import open_asset
from render_engine import set_engine


def arguments():
    argv = sys.argv[sys.argv.index("--") + 1 :]
    if len(argv) != 3:
        raise SystemExit("expected: INPUT.glb OUTPUT.png CAMERA.json")
    return tuple(Path(x).resolve() for x in argv)


def aim(obj, target):
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def main():
    source, output, camera_record = arguments()
    if source.suffix.lower() != ".glb" or not source.is_file():
        raise ValueError("input must be an existing GLB")
    output.parent.mkdir(parents=True, exist_ok=True)
    camera_record.parent.mkdir(parents=True, exist_ok=True)

    open_asset(source)
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not meshes:
        raise ValueError("GLB contains no mesh objects")

    corners = [obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]
    lower = Vector(tuple(min(point[axis] for point in corners) for axis in range(3)))
    upper = Vector(tuple(max(point[axis] for point in corners) for axis in range(3)))
    center = (lower + upper) * 0.5
    extent = upper - lower
    span = max(extent.x, extent.y, extent.z)
    if not math.isfinite(span) or span <= 0:
        raise ValueError("mesh bounds are invalid")

    scene = bpy.context.scene
    # Blender 5.x exposes Eevee as BLENDER_EEVEE; older 4.x builds used the
    # BLENDER_EEVEE_NEXT identifier.
    set_engine(scene)
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 1024
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.render.filepath = str(output)
    if scene.world is None:
        scene.world = bpy.data.worlds.new("ReferenceWorld")
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    background.inputs["Strength"].default_value = 1.0
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        scene.view_settings.look = "Medium High Contrast"

    # Broad three-point lighting retains form cues without hard cast shadows.
    for name, offset, energy, size in (
        ("Key", (-2.2, -3.0, 2.2), 550.0, 2.2),
        ("Fill", (2.4, -2.0, 0.8), 260.0, 2.8),
        ("Rim", (0.7, 2.6, 2.1), 340.0, 2.0),
    ):
        lamp_data = bpy.data.lights.new(name, "AREA")
        lamp_data.energy = energy * span * span
        lamp_data.shape = "DISK"
        lamp_data.size = size * span
        lamp = bpy.data.objects.new(name, lamp_data)
        scene.collection.objects.link(lamp)
        lamp.location = center + Vector(offset) * span
        aim(lamp, center)

    camera_data = bpy.data.cameras.new("FrontCamera")
    camera = bpy.data.objects.new("FrontCamera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = max(extent.x, extent.z) * 1.12
    camera_data.clip_start = max(span * 1e-5, 1e-5)
    camera_data.clip_end = span * 20.0
    # Input must be Y-up GLB with +Z front (imported as Blender -Y front).
    camera.location = center + Vector((0.0, -3.2, 0.03)) * span
    aim(camera, center)

    bpy.context.view_layer.update()
    bpy.ops.render.render(write_still=True)
    camera_record.write_text(
        json.dumps(
            {
                "source": str(source),
                "front_convention": "camera at negative world Y, looking at bounds center",
                "bounds_world": {"min": list(lower), "max": list(upper)},
                "camera_location": list(camera.location),
                "camera_rotation_euler": list(camera.rotation_euler),
                "orthographic_scale": camera_data.ortho_scale,
                "resolution": [1024, 1024],
                "background": "transparent render; caller composites over pure white",
                "lighting": "broad three-point",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
