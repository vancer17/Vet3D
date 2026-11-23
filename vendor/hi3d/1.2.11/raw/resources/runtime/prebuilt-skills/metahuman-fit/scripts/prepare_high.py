"""Import one explicitly selected skin high mesh and sample it without retopology."""

import json, sys, time, hashlib
from pathlib import Path
import bpy, numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_io import load_source, coordinates
from surface import sample_surface


def prepare(config):
    start = time.monotonic()
    root = Path(config["output"])
    root.mkdir(parents=True, exist_ok=True)
    source = load_source(config["high_glb"], config.get("source_object"))
    mesh = source.data
    mesh.calc_loop_triangles()
    vertices = coordinates(source)
    triangles = np.empty(len(mesh.loop_triangles) * 3, np.int32)
    mesh.loop_triangles.foreach_get("vertices", triangles)
    triangles = triangles.reshape(-1, 3)
    normals = np.empty(len(vertices) * 3, np.float32)
    mesh.vertices.foreach_get("normal", normals)
    normals = normals.reshape(-1, 3)
    points, n, ids, bary = sample_surface(
        vertices,
        triangles,
        normals,
        config.get("sample_count", 100000),
        config.get("sample_seed", 0),
    )
    polygons = np.empty(len(mesh.loop_triangles), np.int32)
    mesh.loop_triangles.foreach_get("polygon_index", polygons)
    source_hash = hashlib.sha256(Path(config["high_glb"]).read_bytes()).hexdigest()
    np.savez_compressed(
        root / "surface_raw.npz",
        vertices=points,
        normals=n,
        source_triangle_indices=ids,
        source_polygon_indices=polygons[ids],
        source_vertex_indices=triangles[ids],
        barycentric=bary,
        source_sha256=np.array(source_hash),
    )
    bpy.ops.wm.save_as_mainfile(filepath=str(root / "Source_High.blend"), compress=True)
    report = dict(
        seconds=time.monotonic() - start,
        source_sha256=source_hash,
        source_vertices=len(vertices),
        source_polygons=len(mesh.polygons),
        source_triangles=len(triangles),
        samples=len(points),
        bounds=[vertices.min(0).tolist(), vertices.max(0).tolist()],
        source_object="Source_High",
        coordinates="Source GLB imported into Blender Z-up world coordinates with object transforms applied",
        method="Area-weighted deterministic surface samples; no retopology or lowpoly dependency",
    )
    (root / "source_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == "__main__":
    prepare(json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text()))
