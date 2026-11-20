"""Run with Blender --background --factory-startup --python-exit-code 1 --python ... -- --work NEW_DIR."""

import argparse
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from blender_review import edge_counts, review_asset
from hi3d_storage import digest, load, save


def mesh_snapshot():
    return sorted(
        (
            obj.name,
            tuple(tuple(vertex.co) for vertex in obj.data.vertices),
            tuple(tuple(polygon.vertices) for polygon in obj.data.polygons),
            tuple(tuple(row) for row in obj.matrix_world),
        )
        for obj in bpy.context.scene.objects
        if obj.type == "MESH"
    )


def run_review_test(root):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mesh = bpy.data.meshes.new("seamed-square")
    mesh.from_pydata(
        [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [], [(0, 1, 2), (0, 2, 3)]
    )
    obj = bpy.data.objects.new("seamed-square", mesh)
    bpy.context.collection.objects.link(obj)
    obj.location = (2, 3, 4)
    layer = mesh.uv_layers.new(name="UVMap")
    for corner, uv in zip(
        layer.data, [(0, 0), (1, 0), (1, 1), (0.2, 0.2), (0.8, 0.8), (0, 1)]
    ):
        corner.uv = uv
    colors = mesh.color_attributes.new(name="Color", type="FLOAT_COLOR", domain="POINT")
    for value in colors.data:
        value.color = (0.2, 0.6, 0.8, 1)
    source = root / "source.glb"
    bpy.ops.export_scene.gltf(
        filepath=str(source), export_format="GLB", export_all_vertex_colors=True
    )
    source_hash = digest(source)
    report = review_asset(
        source,
        root / "metrics.json",
        weld=True,
        vertex_colors=True,
        display=root / "display.blend",
    )
    assert report["mesh_objects"] == 1 and report["triangles"] == 2
    detail = report["objects"][0]
    assert detail["finite_coordinates"] and detail["degenerate_triangles"] == 0
    assert detail["vertices"] == 6
    assert detail["exact_position_weld_diagnostic"]["vertices"] == 4
    assert detail["indexed_topology"]["boundary_edges"] == 6
    assert detail["exact_position_weld_diagnostic"]["boundary_edges"] == 4
    assert report["display_copy"]["vertex_color_bindings"]
    before = mesh_snapshot()
    bpy.ops.wm.open_mainfile(filepath=str(root / "display.blend"), use_scripts=False)
    assert mesh_snapshot() == before
    assert digest(source) == source_hash == report["input_sha256"]
    assert load(root / "metrics.json")["display_copy"]["sha256"] == digest(
        root / "display.blend"
    )
    for metrics, display in (
        (root / "metrics.json", None),
        (source, None),
        (root / "new.json", source),
    ):
        try:
            review_asset(source, metrics, display=display)
        except (FileExistsError, ValueError):
            pass
        else:
            raise AssertionError("Expected source/output protection")
    import numpy as np

    edges = edge_counts(np.array([[0, 0, 1], [0, 1, 2]], dtype=np.int32))
    assert edges["collapsed_edge_uses"] == 1 and edges["edges_over_two_faces"] == 1
    result = {
        "passed": True,
        "source_sha256": source_hash,
        "indexed_vertices": 6,
        "diagnostic_vertices": 4,
        "triangles": 2,
        "saved_geometry_and_transforms_equal": True,
    }
    save(root / "test-report.json", result, exclusive=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", required=True)
    args = parser.parse_args(
        sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    )
    print(run_review_test(args.work))


if __name__ == "__main__":
    main()
