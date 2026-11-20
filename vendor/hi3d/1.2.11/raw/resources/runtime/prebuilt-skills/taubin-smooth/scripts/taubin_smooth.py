"""Uniform Taubin smoothing by composing Blender's native signed smooth operator."""
import argparse
import json
import math
from numbers import Integral
from pathlib import Path
import sys

import bmesh
import bpy
import numpy as np

from asset_scene import open_asset
from checkpoints import digest as file_digest
from path_safety import validate_write_roots
from pcg_handoff import result_from_report
from scene_io import import_objects
from timing import write_json
from tool_result import tool_result


def validate_parameters(iterations, lambda_, mu):
    """Validate the two-pass filter; reject high-frequency amplification at k=2."""
    if isinstance(iterations, bool) or not isinstance(iterations, Integral) or iterations < 0:
        raise ValueError("iterations must be a nonnegative integer")
    if not all(math.isfinite(x) for x in (lambda_, mu)):
        raise ValueError("lambda and mu must be finite")
    if not 0 < lambda_ < -mu <= 1:
        raise ValueError("Require 0 < lambda < -mu <= 1")
    if abs((1 - 2 * lambda_) * (1 - 2 * mu)) > 1:
        raise ValueError("This lambda/mu pair amplifies the highest graph frequencies")


def mesh_positions(mesh):
    """Read original local coordinates as an independent float32 (N, 3) array."""
    positions = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", positions)
    return positions.reshape(-1, 3)


def mesh_topology(mesh):
    """Snapshot exact edge, corner and polygon order without triangulation."""
    result = []
    for collection, attribute, width in (
        (mesh.edges, "vertices", 2),
        (mesh.loops, "vertex_index", 1),
        (mesh.polygons, "loop_start", 1),
        (mesh.polygons, "loop_total", 1),
    ):
        values = np.empty(len(collection) * width, dtype=np.int32)
        collection.foreach_get(attribute, values)
        result.append(values.tobytes())
    return tuple(result)


def taubin_positions(mesh, *, iterations=10, lambda_=0.5, mu=-0.53,
                     pin_boundary=False, fixed_vertices=()):
    """Return (new local coordinates, metrics), leaving the input Mesh unchanged.

    Work on a temporary BMesh; Blender owns the adjacency and synchronous update.
    Loose edges participate in adjacency. Isolated and explicitly fixed vertices
    stay unchanged. No remesh, triangulation, welding, weighting or volume rescale.
    """
    validate_parameters(iterations, lambda_, mu)
    before = mesh_positions(mesh)
    if not len(mesh.polygons) or not np.isfinite(before).all():
        raise ValueError("Expected a nonempty finite triangle mesh")
    if any(len(p.vertices) != 3 or len(set(p.vertices)) != 3 for p in mesh.polygons):
        raise ValueError("All faces must have three distinct vertex indices; triangulate explicitly first")
    fixed = set()
    for index in fixed_vertices:
        if isinstance(index, bool) or not isinstance(index, Integral) or not 0 <= index < len(before):
            raise ValueError("fixed_vertices contains an invalid vertex index")
        fixed.add(int(index))
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        bm.verts.ensure_lookup_table()
        bm.verts.index_update()
        if len(bm.verts) != len(before):
            raise ValueError("BMesh vertex count differs from the source")
        boundary = {v.index for edge in bm.edges if edge.is_boundary for v in edge.verts}
        if pin_boundary:
            fixed.update(boundary)
        active = [v for v in bm.verts if v.index not in fixed and v.link_edges]
        axes = dict(use_axis_x=True, use_axis_y=True, use_axis_z=True)
        for _ in range(iterations):
            if not active:
                break
            bmesh.ops.smooth_vert(bm, verts=active, factor=lambda_, **axes)
            # The negative pass consumes the result of the positive pass.
            bmesh.ops.smooth_vert(bm, verts=active, factor=mu, **axes)
        after = np.asarray([tuple(v.co) for v in bm.verts], dtype=np.float32)
        if not np.isfinite(after).all():
            raise ValueError("Smoothing produced nonfinite coordinates; reduce iterations/parameters")
        fixed_ids = sorted(fixed)
        if not np.array_equal(after[fixed_ids], before[fixed_ids]):
            raise RuntimeError("A fixed vertex moved")
        displacement = np.linalg.norm(after.astype(np.float64) - before, axis=1)
        report = {
            "backend": "bmesh.ops.smooth_vert",
            "weighting": "uniform_edge_neighbors",
            "iterations": int(iterations), "lambda": float(lambda_), "mu": float(mu),
            "vertices": len(before), "edges": len(mesh.edges), "triangles": len(mesh.polygons),
            "boundary_vertices": len(boundary), "fixed_vertices": len(fixed),
            "isolated_vertices": sum(not v.link_edges for v in bm.verts),
            "nonmanifold_edges": sum(len(e.link_faces) > 2 for e in bm.edges),
            "moved_vertices": int(np.count_nonzero(displacement)),
            "displacement_max_local": float(displacement.max()),
            "displacement_rms_local": float(np.sqrt(np.mean(displacement ** 2))),
        }
        return after, report
    finally:
        bm.free()


def smooth_object(obj, **parameters):
    """Replace one local Object's raw Mesh with a coordinate-only copy.

    Other instances keep their original data. Object transforms, modifiers, UVs,
    materials, weights, attributes and face order remain. Shape keys are rejected
    because changing only their basis would change the meaning of every key.
    """
    if obj.type != "MESH" or obj.mode != "OBJECT" or obj.library is not None:
        raise ValueError("Expected a local mesh object in Object Mode")
    if obj.data.shape_keys is not None:
        raise ValueError("Shape keys require an explicit deformation policy; use a static copy")
    source = obj.data
    topology = mesh_topology(source)
    positions, report = taubin_positions(source, **parameters)
    duplicate = source.copy()
    try:
        duplicate.vertices.foreach_set("co", positions.ravel())
        duplicate.update()
        if mesh_topology(duplicate) != topology:
            raise RuntimeError("Smoothing changed topology")
        obj.data = duplicate
    except BaseException:
        bpy.data.meshes.remove(duplicate)
        raise
    return dict(report, object=obj.name, topology_unchanged=True)


def select_meshes(objects, *, object_names=(), all_meshes=False):
    """Resolve explicit targets; a lone mesh may be selected automatically."""
    meshes = {obj.name: obj for obj in objects if obj.type == "MESH"}
    names = list(object_names)
    if not meshes or (all_meshes and names) or len(set(names)) != len(names):
        raise ValueError("Choose unique mesh names or all_meshes, with at least one mesh")
    if names:
        if any(name not in meshes for name in names):
            raise ValueError("Unknown mesh name; available: " + ", ".join(sorted(meshes)))
        return [meshes[name] for name in names]
    if len(meshes) > 1 and not all_meshes:
        raise ValueError("Multiple meshes: specify --object or --all-meshes; available: " + ", ".join(sorted(meshes)))
    return list(meshes.values())


def run_asset(source, output_dir, *, object_names=(), all_meshes=False, **parameters):
    """Load in an isolated Blender process, smooth, save/reopen, then write report.

    output_dir must be new. Failure after saving can leave an incomplete revision;
    report.json exists only after the saved coordinates/topology pass readback.
    This function replaces the current scene. Source bytes are never written.
    """
    source = Path(source).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if source.suffix.lower() not in {".blend", ".glb", ".gltf", ".obj", ".ply"}:
        raise ValueError("Supported inputs: BLEND, GLB, GLTF, OBJ, PLY")
    validate_parameters(parameters.get("iterations", 10), parameters.get("lambda_", 0.5),
                        parameters.get("mu", -0.53))
    root = validate_write_roots(
        {"output": output_dir}, package_root=Path(__file__).resolve().parents[1],
        protected_inputs=(source,),
    )["output"]
    if root.exists():
        raise FileExistsError("Use a new output directory: " + str(root))
    source_hash = file_digest(source)
    objects = open_asset(source) if source.suffix.lower() in {".blend", ".glb"} else import_objects(source, reset=True)
    targets = select_meshes(objects, object_names=object_names, all_meshes=all_meshes)
    records = [smooth_object(obj, **parameters) for obj in targets]
    expected = {
        obj.name: (mesh_positions(obj.data), mesh_topology(obj.data), np.array(obj.matrix_world))
        for obj in targets
    }
    root.mkdir(parents=True, exist_ok=False)
    output = root / "smoothed.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(output), check_existing=False, copy=True, relative_remap=True)
    open_asset(output)
    for name, (positions, topology, transform) in expected.items():
        obj = bpy.context.scene.objects.get(name)
        if (obj is None or obj.type != "MESH" or mesh_topology(obj.data) != topology
                or not np.array_equal(mesh_positions(obj.data), positions)
                or not np.allclose(np.array(obj.matrix_world), transform, rtol=1e-6, atol=1e-7)):
            raise RuntimeError("Saved mesh failed readback: " + name)
    if file_digest(source) != source_hash:
        raise RuntimeError("Source changed during the run")
    report = {
        "schema": "taubin-smooth.v1", "blender_version": bpy.app.version_string,
        "source": str(source), "source_sha256": source_hash,
        "output": str(output), "output_sha256": file_digest(output),
        "objects": records, "saved_mesh_readback": True, "source_unchanged": True,
        "limitations": "Float32 local raw-mesh coordinates; modifiers remain unapplied. No exact volume, feature, self-intersection or visual quality guarantee.",
    }
    write_json(root / "report.json", report)
    write_json(root / "tool_result.json", result_from_report(root / "report.json"))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path, help="New directory for BLEND, report.json and PCG tool_result.json")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--object", action="append", default=[], help="Exact mesh object name; repeat to select several")
    selection.add_argument("--all-meshes", action="store_true")
    parser.add_argument("--iterations", type=int, default=10, help="Number of lambda/mu pairs (default: 10)")
    parser.add_argument("--lambda", dest="lambda_", type=float, default=0.5)
    parser.add_argument("--mu", type=float, default=-0.53)
    parser.add_argument("--pin-boundary", action="store_true", help="Fix vertices on edges with exactly one face")
    args = parser.parse_args(argv)
    try:
        run_asset(args.input, args.output_dir, object_names=args.object,
                  all_meshes=args.all_meshes, iterations=args.iterations,
                  lambda_=args.lambda_, mu=args.mu, pin_boundary=args.pin_boundary)
    except Exception as exc:
        # Do not overwrite an earlier revision's successful receipt on failure.
        result = tool_result(status="failed", summary="光顺未完成；检查错误并从原始输入选择新输出目录。",
                             next_checkpoint="input", error=type(exc).__name__)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        raise
    result = json.loads((Path(args.output_dir) / "tool_result.json").read_text(encoding="utf-8"))
    print(json.dumps(result, ensure_ascii=False, allow_nan=False), flush=True)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
