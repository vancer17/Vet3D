"""Explicit single-head asset I/O; imported only inside Blender."""

import bpy
import numpy as np


from scene_io import import_objects, retain_meshes

def coordinates(obj):
    data = np.empty(len(obj.data.vertices) * 3, np.float32)
    obj.data.vertices.foreach_get("co", data)
    return data.reshape(-1, 3)


def load_source(path, object_name=None, keep_objects=()):
    """Legacy single-head selection plus explicit additional mesh retention."""
    imported = import_objects(path, reset=True)
    meshes = [obj for obj in imported if obj.type == "MESH"
              and (object_name is None or obj.name == object_name)]
    if len(meshes) != 1:
        raise ValueError("Select exactly one head mesh with source_object; candidates: "
                         + ", ".join(obj.name for obj in meshes))
    source = meshes[0]
    kept = []
    for name in keep_objects:
        obj = bpy.data.objects.get(name)
        if obj not in imported or obj.type != "MESH" or obj == source:
            raise ValueError("Invalid separate retained mesh: " + name)
        kept.append(obj)
    retain_meshes([source, *kept], remove_others=True)
    source.name = "Source_High"
    return source
