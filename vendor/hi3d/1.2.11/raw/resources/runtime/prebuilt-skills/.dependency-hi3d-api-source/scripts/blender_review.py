"""Blender inspection of original mesh data; optional separate vertex-color display copy."""

import argparse
import sys
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hi3d_storage import digest, save
from triangle_arrays import edge_counts, measure_indexed


def inspect(obj, weld):
    mesh = obj.data
    mesh.calc_loop_triangles()
    coords = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", coords)
    coords = coords.reshape(-1, 3)
    triangles = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int32)
    mesh.loop_triangles.foreach_get("vertices", triangles)
    triangles = triangles.reshape(-1, 3)
    data = {
        **measure_indexed(coords, triangles, area_threshold=1e-12, exact_weld=weld),
        "name": obj.name,
        "polygons": len(mesh.polygons),
        "object_dimensions": list(obj.dimensions),
        "matrix_world": [list(r) for r in obj.matrix_world],
        "uv_layers": [x.name for x in mesh.uv_layers],
        "color_attributes": [
            {"name": x.name, "domain": x.domain, "type": x.data_type}
            for x in mesh.color_attributes
        ],
        "materials": [m.name if m else None for m in mesh.materials],
    }
    return data


def import_asset(path):
    ext = path.suffix.lower()
    if ext == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False, use_scripts=False)
        return
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=str(path))
    elif ext == ".stl":
        bpy.ops.wm.stl_import(filepath=str(path))
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path))
    else:
        raise ValueError("Supported inputs: GLB, GLTF, OBJ, STL, FBX, BLEND.")


def bind_vertex_colors(objects):
    materials = {}
    bound = []
    for obj in objects:
        attrs = obj.data.color_attributes
        if not len(attrs):
            continue
        attr = attrs.active_color or attrs[0]
        if attr.name not in materials:
            mat = bpy.data.materials.new("Hi3D Display " + attr.name)
            mat.use_nodes = True
            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            node = mat.node_tree.nodes.new("ShaderNodeVertexColor")
            node.layer_name = attr.name
            mat.node_tree.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
            bsdf.inputs["Roughness"].default_value = 0.55
            materials[attr.name] = mat
        obj.data.materials.clear()
        obj.data.materials.append(materials[attr.name])
        for polygon in obj.data.polygons:
            polygon.material_index = 0
        bound.append({"object": obj.name, "attribute": attr.name})
    return bound


def review_asset(source, metrics, *, weld=False, vertex_colors=False, display=None):
    source, metrics = (
        Path(source).expanduser().resolve(),
        Path(metrics).expanduser().resolve(),
    )
    display = Path(display).expanduser().resolve() if display else None
    if not source.is_file():
        raise ValueError("Input file not found")
    if source == metrics or display == source or display == metrics:
        raise ValueError("Input, metrics and display paths must differ")
    if metrics.exists() or (display and display.exists()):
        raise FileExistsError(
            "Use new output paths; original and prior results are preserved"
        )
    if display and display.suffix.lower() != ".blend":
        raise ValueError("Display copy requires .blend")
    if vertex_colors and not display:
        raise ValueError("Vertex-color display requires a separate blend copy")
    source_hash = digest(source)
    import_asset(source)
    objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not objects:
        raise ValueError("Imported asset contains no mesh objects")
    detail = [inspect(obj, weld) for obj in objects]
    result = {
        "input_name": source.name,
        "input_sha256": source_hash,
        "blender_version": bpy.app.version_string,
        "mesh_objects": len(objects),
        "triangles": sum(item["triangles"] for item in detail),
        "armatures": sum(obj.type == "ARMATURE" for obj in bpy.context.scene.objects),
        "actions": len(bpy.data.actions),
        "objects": detail,
        "images": [
            {
                "name": img.name,
                "size": list(img.size),
                "packed": bool(img.packed_file),
                "source": img.source,
            }
            for img in bpy.data.images
            if img.type != "RENDER_RESULT"
        ],
        "limits": "Original mesh data, not evaluated modifiers. Triangulation edges included. Exact-position weld is per object and diagnostic only. No self-intersection, thickness or manufacturing proof.",
    }
    if display:
        bound = bind_vertex_colors(objects) if vertex_colors else []
        display.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.file.pack_all()
        bpy.ops.wm.save_as_mainfile(filepath=str(display))
        result["display_copy"] = {
            "path": str(display),
            "sha256": digest(display),
            "vertex_color_bindings": bound,
            "geometry_changed": False,
            "transforms_changed": False,
        }
    if digest(source) != source_hash:
        raise RuntimeError("Source changed during inspection")
    save(metrics, result, exclusive=True)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--metrics", required=True)
    parser.add_argument("--weld-check", action="store_true")
    parser.add_argument("--vertex-colors", action="store_true")
    parser.add_argument("--display-blend")
    if argv is None:
        argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    args = parser.parse_args(argv)
    result = review_asset(
        args.input,
        args.metrics,
        weld=args.weld_check,
        vertex_colors=args.vertex_colors,
        display=args.display_blend,
    )
    print(
        {
            "metrics": str(Path(args.metrics).resolve()),
            "mesh_objects": result["mesh_objects"],
            "triangles": result["triangles"],
        }
    )


if __name__ == "__main__":
    main()
