"""Import one source head and sample its actual triangle surfaces for fitting."""

import json
import sys
from pathlib import Path
import numpy as np
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_io import load_source, coordinates, studio, render_view, material
from run import digest


def open_boundary(vertices, triangles):
    """Find geometric boundary loops after welding only exact duplicate positions."""
    welded, inverse = np.unique(vertices, axis=0, return_inverse=True)
    tri = inverse[triangles]
    packed = []
    n = len(welded)
    for a, b in [(0, 1), (1, 2), (2, 0)]:
        low = np.minimum(tri[:, a], tri[:, b]).astype(np.int64)
        high = np.maximum(tri[:, a], tri[:, b]).astype(np.int64)
        packed.append(low * n + high)
    edges, counts = np.unique(np.concatenate(packed), return_counts=True)
    edges = edges[counts == 1]
    if len(edges) == 0:
        return {"status": "closed_or_no_boundary"}
    pairs = np.column_stack([edges // n, edges % n])
    adjacency = {}
    for a, b in pairs:
        adjacency.setdefault(int(a), []).append(int(b))
        adjacency.setdefault(int(b), []).append(int(a))
    todo = set(adjacency)
    loops = []
    while todo:
        seed = todo.pop()
        stack = [seed]
        component = [seed]
        while stack:
            for neighbor in adjacency[stack.pop()]:
                if neighbor in todo:
                    todo.remove(neighbor)
                    stack.append(neighbor)
                    component.append(neighbor)
        if len(component) > 20 and all(len(adjacency[i]) == 2 for i in component):
            points = welded[component]
            center = points.mean(0)
            _, _, vt = np.linalg.svd(points - center, full_matrices=False)
            normal = vt[-1]
            # The source centroid determines which halfspace contains the head.
            if np.dot(vertices.mean(0) - center, normal) < 0:
                normal = -normal
            residual = np.abs((points - center) @ normal)
            loops.append(
                {
                    "count": len(component),
                    "points": points.tolist(),
                    "normal": normal.tolist(),
                    "offset": float(normal @ center),
                    "p95_plane_residual": float(np.percentile(residual, 95)),
                    "center": center.tolist(),
                }
            )
    height = np.ptp(vertices, axis=0).max()
    candidates = [
        loop
        for loop in loops
        if loop["center"][2] < np.mean(vertices[:, 2])
        and loop["p95_plane_residual"] < height * 0.015
    ]
    return {
        "status": "detected" if candidates else "no_planar_lower_loop",
        "boundary_edges": len(edges),
        "loop_count": len(loops),
        "neck": max(candidates, key=lambda item: item["count"]) if candidates else None,
    }


def prepare(config):
    root = Path(config["output"])
    root.mkdir(parents=True, exist_ok=True)
    source = load_source(config["source"], config.get("source_object"), config.get("hair_objects", []))
    vertices = coordinates(source)
    if not np.isfinite(vertices).all() or len(vertices) < 4:
        raise ValueError("Source geometry is empty or nonfinite")
    if not 0.95 <= np.ptp(vertices, axis=0).max() <= 1.05:
        raise ValueError(
            "This facial adapter requires a unit-extent source; normalize a task copy and record its transform first"
        )
    source.data.calc_loop_triangles()
    triangles = np.empty(len(source.data.loop_triangles) * 3, np.int32)
    source.data.loop_triangles.foreach_get("vertices", triangles)
    triangles = triangles.reshape(-1, 3)
    points = vertices[triangles]
    cross = np.cross(points[:, 1] - points[:, 0], points[:, 2] - points[:, 0])
    areas2 = np.linalg.norm(cross, axis=1)
    if areas2.sum() <= 0:
        raise ValueError("Source has no positive area triangles")
    rng = np.random.default_rng(config.get("seed", 0))
    count = config.get("surface_samples", 250000)
    selected = rng.choice(len(triangles), count, p=areas2 / areas2.sum())
    uv = rng.random((count, 2))
    uv[uv.sum(1) > 1] = 1 - uv[uv.sum(1) > 1]
    bary = np.column_stack([1 - uv.sum(1), uv])
    samples = np.einsum("ni,nic->nc", bary, points[selected])
    sample_normals = cross[selected] / areas2[selected, None]
    np.savez_compressed(
        root / "surface_samples.npz",
        points=samples.astype(np.float32),
        normals=sample_normals.astype(np.float32),
    )
    bounds = np.array([vertices.min(0), vertices.max(0)])
    boundary = open_boundary(vertices, triangles)
    (root / "source_boundary.json").write_text(json.dumps(boundary, indent=2))
    report = {
        "source_sha256": digest(config["source"]),
        "source": str(config["source"]),
        "vertices": len(vertices),
        "triangles": len(triangles),
        "bounds": bounds.tolist(),
        "degenerate_triangles": int(np.sum(areas2 <= 1e-15)),
        "sample_count": count,
        "sampling": "triangle area weighted, barycentric interior",
        "coordinate_space": "Blender imported world coordinates; no hidden normalization",
        "blender": bpy.app.version_string,
        "hair_state": config.get("hair_state", "unknown"),
        "hair_objects": config.get("hair_objects", []),
    }
    (root / "source_report.json").write_text(json.dumps(report, indent=2))
    del points, cross, triangles
    for face in source.data.polygons:
        face.use_smooth = True
    display_bounds = bounds.copy()
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH" and obj.name.startswith("Source_Hair_"):
            v = coordinates(obj)
            display_bounds[0] = np.minimum(display_bounds[0], v.min(0))
            display_bounds[1] = np.maximum(display_bounds[1], v.max(0))
    report["review_bounds"] = display_bounds.tolist()
    (root / "source_report.json").write_text(json.dumps(report, indent=2))
    camera, center, span = studio(display_bounds, config.get("preview_size", 900))
    bpy.ops.wm.save_as_mainfile(filepath=str(root / "source.blend"))
    bpy.context.view_layer.material_override = material("Source clay")
    if config.get("diagnostic_previews", False):
        for view, direction in [("front", (0, -3, 0)), ("side", (3, 0, 0))]:
            render_view(camera, center, span, direction, root / f"high_{view}.png")
    print("PREPARED", report, flush=True)


if __name__ == "__main__":
    prepare(json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text()))
