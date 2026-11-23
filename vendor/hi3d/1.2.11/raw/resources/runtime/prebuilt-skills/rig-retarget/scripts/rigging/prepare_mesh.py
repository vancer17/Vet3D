"""Import a unified GLB, normalize it, weld UV seams, then optionally reduce it."""

import argparse
import json
import math
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix


def normalize_vertices(vertices, height):
    """Center XY, place the lowest Z at zero, and scale to a positive height."""
    vertices = np.asarray(vertices)
    if (
        vertices.ndim != 2
        or vertices.shape[1] != 3
        or not len(vertices)
        or not np.isfinite(vertices).all()
    ):
        raise ValueError("Expected finite nonempty N x 3 vertices")
    if not math.isfinite(height) or height <= 0:
        raise ValueError("Height must be finite and positive")
    low, high = vertices.min(0), vertices.max(0)
    if high[2] - low[2] < 1e-8:
        raise ValueError("Degenerate height; inspect import orientation")
    center = np.array([(low[0] + high[0]) / 2, (low[1] + high[1]) / 2, low[2]])
    scale = float(height / (high[2] - low[2]))
    return (vertices - center) * scale, center, scale


def import_surface(input_path, rotation_degrees):
    """Replace the working scene with the joined, transform-applied GLB surface."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(input_path))
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        raise ValueError("GLB contains no mesh")
    bpy.ops.object.select_all(action="DESELECT")
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.join()
    surface = bpy.context.object
    surface.name = "CharacterSurface"
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    surface.data.transform(Matrix.Rotation(math.radians(rotation_degrees), 4, "Z"))
    return surface


def weld_surface(surface, distance):
    """Merge positions using Geometry Nodes, preserving face-corner UV storage."""
    tree = bpy.data.node_groups.new("WeldAtlasSeams", "GeometryNodeTree")
    tree.interface.new_socket(
        name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry"
    )
    tree.interface.new_socket(
        name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry"
    )
    source, target = tree.nodes.new("NodeGroupInput"), tree.nodes.new("NodeGroupOutput")
    merge = tree.nodes.new("GeometryNodeMergeByDistance")
    merge.inputs["Distance"].default_value = distance
    tree.links.new(source.outputs["Geometry"], merge.inputs["Geometry"])
    tree.links.new(merge.outputs["Geometry"], target.inputs["Geometry"])
    modifier = surface.modifiers.new("WeldBeforeWeights", "NODES")
    modifier.node_group = tree
    bpy.context.view_layer.objects.active = surface
    try:
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    finally:
        if tree.users == 0:
            bpy.data.node_groups.remove(tree)
    return len(surface.data.vertices)


def triangulate_reduce(surface, faces=None):
    """Triangulate and apply an optional approximate triangle-count budget."""
    bpy.context.view_layer.objects.active = surface
    modifier = surface.modifiers.new("Triangles", "TRIANGULATE")
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    if faces is not None and len(surface.data.polygons) > faces:
        modifier = surface.modifiers.new("AnimationReduction", "DECIMATE")
        modifier.ratio = faces / len(surface.data.polygons)
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    return len(surface.data.polygons)


def prepare_mesh(
    input_path, output_path, height=1.8, faces=None, weld_relative=1e-6, rotation_deg=0
):
    """Create a new prepared blend and mesh report without modifying the source GLB."""
    input_path, output_path = Path(input_path).resolve(), Path(output_path).resolve()
    report_path = output_path.with_suffix(".mesh.json")
    if (
        output_path.exists()
        or report_path.exists()
        or input_path in (output_path, report_path)
    ):
        raise ValueError("Use new working output paths; original is immutable")
    if (
        not np.isfinite([height, weld_relative, rotation_deg]).all()
        or height <= 0
        or weld_relative <= 0
    ):
        raise ValueError("Finite positive height and weld tolerance required")
    if faces is not None and (not isinstance(faces, int) or faces < 1):
        raise ValueError("Face budget must be a positive integer")
    surface = import_surface(input_path, rotation_deg)
    vertices = np.empty(len(surface.data.vertices) * 3, dtype=np.float32)
    surface.data.vertices.foreach_get("co", vertices)
    normalized, center, scale = normalize_vertices(vertices.reshape(-1, 3), height)
    surface.data.vertices.foreach_set("co", normalized.ravel())
    surface.data.update()
    before = len(surface.data.vertices)
    welded = weld_surface(surface, height * weld_relative)
    triangles = triangulate_reduce(surface, faces)
    surface["character_height_m"] = height
    surface["weld_relative"] = weld_relative
    surface["welded_before_weights"] = True
    bpy.ops.file.pack_all()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    report = {
        "vertices_before_weld": before,
        "vertices_after_weld": welded,
        "working_vertices": len(surface.data.vertices),
        "working_faces": triangles,
        "height_m": height,
        "weld_distance_m": height * weld_relative,
        "normalization_center": center.tolist(),
        "normalization_scale": scale,
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--height", type=float, default=1.8)
    parser.add_argument(
        "--faces", type=int, help="Omit to preserve full working resolution"
    )
    parser.add_argument("--weld-relative", type=float, default=1e-6)
    parser.add_argument(
        "--rotation-deg", type=float, default=0, help="Z rotation to face -Y"
    )
    args = parser.parse_args(argv)
    print(
        json.dumps(
            prepare_mesh(
                args.input,
                args.output,
                args.height,
                args.faces,
                args.weld_relative,
                args.rotation_deg,
            )
        )
    )


if __name__ == "__main__":
    main()
