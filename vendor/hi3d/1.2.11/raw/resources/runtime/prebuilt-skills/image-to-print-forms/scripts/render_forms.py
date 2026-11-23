import argparse
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector


def linear(channel):
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def material(name, color, roughness=0.4):
    text = color.removeprefix("#")
    rgba = tuple(linear(int(text[index:index + 2], 16) / 255) for index in (0, 2, 4)) + (1.0,)
    result = bpy.data.materials.new(name)
    result.diffuse_color = rgba
    result.use_nodes = True
    shader = result.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = rgba
    shader.inputs["Roughness"].default_value = roughness
    return result


def aim(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def render_setup(scale):
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX"
    world = bpy.data.worlds.new("Logo_Studio_World")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.8, 0.83, 0.88, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35
    scene.world = world
    bpy.ops.mesh.primitive_plane_add(size=4, location=(0, 0, -0.00015))
    floor = bpy.context.object
    floor.name = "Preview_Floor"
    floor.data.materials.append(material("Preview_Floor_Material", "#DDE3E5", 0.75))
    for name, location, energy, size in (("Key", (-0.25, -0.36, 0.42), 5, 0.32), ("Fill", (0.34, -0.05, 0.24), 2.2, 0.25), ("Rim", (0.05, 0.28, 0.35), 4, 0.24)):
        data = bpy.data.lights.new(name, "AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = size
        lamp = bpy.data.objects.new(name, data)
        scene.collection.objects.link(lamp)
        lamp.location = location
        aim(lamp, (0, 0.03, 0.05))
    data = bpy.data.cameras.new("Fixed_Isometric_Camera")
    camera = bpy.data.objects.new(data.name, data)
    scene.collection.objects.link(camera)
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = scale
    scene.camera = camera
    return camera


def export_all(directory, specification, arrays, selected):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    for record in specification["models"]:
        collection = bpy.data.collections.new(f"{record['number']:02d}_{record['name']}")
        scene.collection.children.link(collection)
        for part in record["objects"]:
            key = part["key"]
            mesh = bpy.data.meshes.new(part["name"] + "_mesh")
            mesh.from_pydata(arrays[key + "_vertices"].tolist(), [], arrays[key + "_faces"].tolist())
            mesh.update()
            mesh.set_sharp_from_angle(angle=math.radians(34))
            for face in mesh.polygons:
                face.use_smooth = True
            obj = bpy.data.objects.new(part["name"], mesh)
            collection.objects.link(obj)
            obj.data.materials.append(material(part["name"] + "_material", part["color"]))
            obj["sparc3dPhysicalUnits"] = {"version": 1, "unit": "meter"}
            obj["sourceRole"] = part["role"]
            obj["formNumber"] = record["number"]
            obj.select_set(True)
        filename = f"hi3d-{record['name']}.glb"
        if record["number"] in selected:
            bpy.ops.export_scene.gltf(filepath=str(directory / filename), export_format="GLB", use_selection=True, export_extras=True, export_yup=True, export_lights=False, export_cameras=False)
        record["glb"] = filename
        for obj in collection.objects:
            obj.select_set(False)
        print("EXPORTED", filename, flush=True)
    camera = render_setup(specification["preview"]["shared_ortho_scale_m"])
    center = Vector((0, 0.04, 0.04))
    camera.location = center + Vector((1, -1, 1)).normalized() * 0.55
    aim(camera, center)
    # All forms share one framing and overlap, so the saved project shows only the
    # lowest-numbered form selected this run; every other collection stays in the
    # file hidden and can be toggled on in Blender.
    visible = f"{min(selected):02d}_"
    for collection in scene.collection.children:
        hidden = not collection.name.startswith(visible)
        collection.hide_render = hidden
        collection.hide_viewport = hidden
    bpy.ops.wm.save_as_mainfile(filepath=str(directory / "hi3d-logo-four-forms-editable.blend"))


def render_all(directory, specification, selected):
    renders = directory / "renders"
    renders.mkdir(exist_ok=True)
    for record in specification["models"]:
        if record["number"] not in selected:
            continue
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(directory / record["glb"]))
        imported = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
        points = np.asarray([obj.matrix_world @ Vector(corner) for obj in imported for corner in obj.bound_box])
        center = Vector((points.min(axis=0) + points.max(axis=0)) / 2)
        camera = render_setup(specification["preview"]["shared_ortho_scale_m"])
        directions = {"isometric": Vector((1, -1, 1)).normalized()}
        if record["number"] == 4:
            directions["side"] = Vector((1, 0, 0))
        if record["number"] == 5:
            directions["top"] = Vector((0.01, -0.01, 1)).normalized()
        if record["number"] in (3, 7):
            directions["front"] = Vector((0, -1, 0))
        record["previews"] = {}
        for view, direction in directions.items():
            camera.location = center + direction * 0.55
            aim(camera, center)
            filename = f"hi3d-{record['number']:02d}-{record['name']}-{view}.png"
            bpy.context.scene.render.filepath = str(renders / filename)
            bpy.ops.render.render(write_still=True)
            record["previews"][view] = f"renders/{filename}"
        record["export_reimport_rendered"] = True
        print("REIMPORTED_RENDERED", record["number"], flush=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--forms", nargs="+", type=int, default=[3, 4, 5, 7])
    args = parser.parse_args(argv)
    directory = args.directory.resolve()
    specification = json.loads((directory / "hi3d-logo-forms.json").read_text(encoding="utf-8"))
    arrays = np.load(directory / "hi3d-logo-meshes.npz")
    export_all(directory, specification, arrays, args.forms)
    render_all(directory, specification, args.forms)
    (directory / "hi3d-logo-forms.json").write_text(json.dumps(specification, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
