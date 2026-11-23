"""Explicit import and retention operations for an isolated Blender scene."""
from pathlib import Path
import bpy


def import_objects(path, *, reset=False):
    """Import GLB/GLTF/OBJ/PLY/BLEND and return imported objects, preserving hierarchy.

    reset=True clears the current scene; otherwise existing objects remain. BLEND
    imports all objects so parent transforms exist before any selection/retention.
    No unit conversion, join, renaming or geometry cleanup is performed.
    """
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    suffix = path.suffix.lower()
    if suffix not in (".glb", ".gltf", ".obj", ".ply", ".blend"):
        raise ValueError("Supported sources: GLB, GLTF, OBJ, PLY, BLEND")
    if reset:
        bpy.ops.wm.read_factory_settings(use_empty=True)
    before = set(bpy.context.scene.objects)
    if suffix in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif suffix == ".obj":
        bpy.ops.wm.obj_import(filepath=str(path))
    elif suffix == ".ply":
        bpy.ops.wm.ply_import(filepath=str(path))
    else:
        with bpy.data.libraries.load(str(path), link=False) as (available, requested):
            requested.objects = available.objects
        for obj in requested.objects:
            if obj is not None:
                bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.update()
    return [obj for obj in bpy.context.scene.objects if obj not in before]


def retain_meshes(objects, *, remove_others=False, apply_transform=True):
    """Detach explicit unique scene meshes without changing world geometry.

    Optionally delete other scene objects, then apply transforms one mesh at a
    time. Returns original-name to retained-object mapping; no semantic naming.
    """
    objects = list(objects)
    if not objects or len(set(objects)) != len(objects):
        raise ValueError("nonempty unique object selection required")
    if any(obj.type != "MESH" or obj.name not in bpy.context.scene.objects for obj in objects):
        raise ValueError("retained objects must be meshes in the current scene")
    bpy.context.view_layer.update()
    result = {obj.name: obj for obj in objects}
    worlds = [obj.matrix_world.copy() for obj in objects]
    for obj, world in zip(objects, worlds):
        obj.parent = None
        obj.matrix_world = world
    if remove_others:
        for obj in list(bpy.context.scene.objects):
            if obj not in objects:
                bpy.data.objects.remove(obj, do_unlink=True)
    if apply_transform:
        for obj in objects:
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return result

def create_mesh_object(name, vertices, faces, *, collection, material=None, recalculate_normals=False, smooth=False):
    """Create a mesh in exactly the explicit collection; caller supplies scene units."""
    mesh = bpy.data.meshes.new(name)
    obj = None
    try:
        mesh.from_pydata(vertices, [], faces); mesh.update()
        if recalculate_normals:
            import bmesh
            bm = bmesh.new()
            try:
                bm.from_mesh(mesh); bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces)); bm.to_mesh(mesh)
            finally: bm.free()
        for face in mesh.polygons: face.use_smooth = smooth
        if material is not None: mesh.materials.append(material)
        obj = bpy.data.objects.new(name,mesh); collection.objects.link(obj)
        return obj
    except BaseException:
        if obj is not None: bpy.data.objects.remove(obj,do_unlink=True)
        bpy.data.meshes.remove(mesh)
        raise
