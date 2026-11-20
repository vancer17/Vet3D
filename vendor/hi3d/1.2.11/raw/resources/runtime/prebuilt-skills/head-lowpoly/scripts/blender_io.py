"""Head/independent-hair naming adapter over the shared Blender importer."""
import bpy
from head_io import coordinates
from head_preview import aim, render_view, make_mesh, material, studio
from head_io import load_source as _load_source


def load_source(path, object_name=None, hair_objects=()):
    source = _load_source(path, object_name, keep_objects=hair_objects)
    for name in hair_objects:
        obj = bpy.data.objects[name]
        obj["source_object_name"] = name
        obj.name = "Source_Hair_" + name
    return source
