"""Source-derived remeshing and anatomical aperture loops."""

import json
import math
import sys
import time
import tempfile
from pathlib import Path
from collections import defaultdict
import bpy
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_io import coordinates, make_mesh, material, render_view
from mdf_handoff import resolve_result, digest, unpack_geometry


def working_surface(config):
    root = Path(config["output"])
    bpy.ops.wm.open_mainfile(filepath=str(root / "source.blend"), load_ui=False)
    source = bpy.data.objects["Source_High"]
    work = source.copy()
    work.data = source.data.copy()
    bpy.context.scene.collection.objects.link(work)
    work.name = "Retopology_Working_Surface"
    work.data.materials.clear()
    bpy.ops.object.select_all(action="DESELECT")
    work.select_set(True)
    bpy.context.view_layer.objects.active = work
    height = max(work.dimensions)
    bm = bmesh.new()
    bm.from_mesh(work.data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=height * 1e-7)
    bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=height * 1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(work.data)
    bm.free()
    budget = config["working_triangles"]
    if len(work.data.polygons) > budget:
        modifier = work.modifiers.new(
            "Working density only; bake from untouched high", "DECIMATE"
        )
        modifier.ratio = budget / len(work.data.polygons)
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    if config.get("retopology_backend") == "runtime":
        bpy.ops.export_scene.gltf(filepath=str(root / "working_surface.glb"),
                                  export_format="GLB", use_selection=True)
    else:
        bpy.ops.wm.obj_export(
            filepath=str(root / "working_surface.obj"),
            export_selected_objects=True,
            export_uv=False,
            export_normals=False,
            forward_axis="NEGATIVE_Y",
            up_axis="Z",
        )
    (root / "working_surface_report.json").write_text(
        json.dumps(
            {
                "triangles": len(work.data.polygons),
                "bounds": [coordinates(work).min(0).tolist(), coordinates(work).max(0).tolist()],
                "purpose": "remesher working geometry; detail baking and feature projection use original high",
            },
            indent=2,
        )
    )


def import_retopology(config):
    """Import the verified API artifact; require native quads without guessing face pairs."""
    root = Path(config['output'])
    path = resolve_result(config)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with tempfile.TemporaryDirectory(prefix='mdf-obj-') as temporary:
        obj_path = unpack_geometry(path, Path(temporary) / 'geometry.obj')
        # Interpret OBJ in the input GLB's Y-up frame; bounds below reject a mismatch.
        bpy.ops.wm.obj_import(filepath=str(obj_path), forward_axis='NEGATIVE_Z', up_axis='Y')
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    if len(meshes) != 1:
        raise ValueError('Retopology must return exactly one head mesh; inspect the saved result')
    obj = meshes[0]
    transform = obj.matrix_world.copy()
    obj.parent = None
    obj.matrix_world.identity()
    obj.data.transform(transform)
    vertices = coordinates(obj)
    if not len(vertices) or not np.isfinite(vertices).all():
        raise ValueError('Retopology returned empty or non-finite geometry')
    source_bounds = np.asarray(json.loads((root / 'working_surface_report.json').read_text())['bounds'])
    bounds = np.array([vertices.min(0), vertices.max(0)])
    span = float(np.max(source_bounds[1] - source_bounds[0]))
    if span <= 0 or np.max(np.abs(bounds - source_bounds)) > span * 0.1:
        raise ValueError('Retopology changed coordinate frame or head extent; inspect before fitting, no automatic realignment')
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        before = len(bm.faces)
        # OBJ preserves server connectivity; never infer pairs from GLB triangles.
        if not bm.faces or any(len(face.verts) != 4 or face.calc_area() <= span * span * 1e-14 for face in bm.faces):
            raise ValueError('Service OBJ does not expose nondegenerate native quads; retain result for inspection, do not resubmit automatically')
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(obj.data)
    finally:
        bm.free()
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.wm.obj_export(filepath=str(root / 'source_quads.obj'),
                          export_selected_objects=True, export_uv=False, export_normals=False,
                          forward_axis='NEGATIVE_Y', up_axis='Z')
    (root / 'retopology_import_report.json').write_text(json.dumps({
        'artifact_sha256': digest(path), 'imported_faces': before,
        'quads': len(obj.data.polygons), 'vertices': len(obj.data.vertices),
        'bounds': bounds.tolist(), 'topology_source': 'native faces exposed by the service artifact importer',
        'baked': False, 'bake_source': 'full original high in source.blend'
    }, indent=2), encoding='utf-8')


def ordered_cut(vertices, faces, patch, front_depth):
    """Cut one connected front patch and return its single oriented edge loop."""
    cx, cz = patch["center"]
    rx, rz = patch["outer_radii"]
    if len({len(face) for face in faces}) == 1:
        centers = vertices[np.asarray(faces)].mean(1)
    else:
        centers = np.array([vertices[face].mean(0) for face in faces])
    candidates = set(
        np.where(
            (((centers[:, 0] - cx) / rx) ** 2 + ((centers[:, 2] - cz) / rz) ** 2 < 1)
            & (centers[:, 1] < front_depth)
        )[0]
    )
    if not candidates:
        raise ValueError("No source faces inside " + patch["name"])
    edge_faces = defaultdict(list)
    for i, face in enumerate(faces):
        for a, b in zip(face, face[1:] + face[:1]):
            edge_faces[tuple(sorted((a, b)))].append(i)
    seed = min(
        candidates,
        key=lambda i: ((centers[i, 0] - cx) / rx) ** 2
        + ((centers[i, 2] - cz) / rz) ** 2,
    )
    removed = {seed}
    stack = [seed]
    while stack:
        face = faces[stack.pop()]
        for a, b in zip(face, face[1:] + face[:1]):
            for neighbor in edge_faces[tuple(sorted((a, b)))]:
                if neighbor in candidates and neighbor not in removed:
                    removed.add(neighbor)
                    stack.append(neighbor)
    boundary = [
        edge
        for edge, linked in edge_faces.items()
        if len(linked) == 2 and sum(i in removed for i in linked) == 1
    ]
    graph = defaultdict(list)
    for a, b in boundary:
        graph[a].append(b)
        graph[b].append(a)
    if not graph or any(len(v) != 2 for v in graph.values()):
        raise ValueError(
            patch["name"] + " cut is not a simple boundary; adjust the patch"
        )
    first = max(graph, key=lambda i: vertices[i, 0])
    loop = [first]
    prev = None
    current = first
    while True:
        nxt = next(i for i in graph[current] if i != prev)
        if nxt == first:
            break
        if nxt in loop:
            raise ValueError("Boundary ordering revisits a vertex")
        loop.append(nxt)
        prev, current = current, nxt
    if len(loop) != len(graph):
        raise ValueError("Multiple boundary loops in " + patch["name"])
    p = vertices[loop][:, [0, 2]]
    area = np.sum(p[:, 0] * np.roll(p[:, 1], -1) - np.roll(p[:, 0], -1) * p[:, 1])
    if area < 0:
        loop = [loop[0]] + list(reversed(loop[1:]))
    return removed, loop


def build_patch(vertices, faces, metadata, patch, region, surface, front_depth):
    arr = np.array(vertices)
    removed, loop = ordered_cut(arr, faces, patch, front_depth)
    points = arr[loop]
    lengths = np.linalg.norm(np.roll(points, -1, axis=0) - points, axis=1)
    arc = np.r_[0, np.cumsum(lengths[:-1])] / lengths.sum()
    cx, cz = patch["center"]
    rx, rz = patch["outer_radii"]
    ix, iz = patch["inner_radii"]
    theta = (
        math.atan2((points[0, 2] - cz) / rz, (points[0, 0] - cx) / rx)
        + arc * 2 * math.pi
    )
    inner_x = cx + ix * np.cos(theta)
    if patch["kind"] == "mouth":
        inner_z = (
            patch["seam_z"]
            - patch["corner_drop"] * np.abs(np.cos(theta)) ** 1.6
            + iz * np.sin(theta)
        )
    else:
        inner_z = cz + iz * np.sign(np.sin(theta)) * np.abs(np.sin(theta)) ** 0.75
    faces = [face for i, face in enumerate(faces) if i not in removed]
    previous = loop
    for ring in range(1, patch["rings"] + 1):
        t = 1 - (1 - ring / patch["rings"]) ** 1.35
        xx = points[:, 0] * (1 - t) + inner_x * t
        zz = points[:, 2] * (1 - t) + inner_z * t
        current = []
        for i, (x, z) in enumerate(zip(xx, zz)):
            point = surface(x, z)
            if patch["kind"] == "eye" and ring == patch["rings"]:
                point[1] -= patch.get("lid_clearance", 0)
            current.append(len(vertices))
            vertices.append(point.tolist())
            metadata.append((region, t, float(theta[i])))
        for i in range(len(loop)):
            nxt = (i + 1) % len(loop)
            faces.append([previous[i], previous[nxt], current[nxt], current[i]])
        previous = current
    return faces, {
        "name": patch["name"],
        "removed_faces": len(removed),
        "boundary_vertices": len(loop),
        "rings": patch["rings"],
        "new_faces": len(loop) * patch["rings"],
    }


def create_controls(vertices, metadata, patches, controls, surface):
    """Build explicit per-case displacement fields and aperture-aware eyelids/jaw."""
    front = np.clip(
        (controls["front_mask_start"] - vertices[:, 1]) / controls["front_mask_width"],
        0,
        1,
    )

    def field(spec):
        x, z = spec["center"]
        sx, sz = spec["sigma"]
        return (
            np.exp(
                -0.5 * ((vertices[:, 0] - x) / sx) ** 2
                - 0.5 * ((vertices[:, 2] - z) / sz) ** 2
            )
            * front
        )

    result = {}
    for name, spec in controls["fields"].items():
        delta = np.zeros_like(vertices)
        for term in spec:
            weight = field(term)
            displacement = np.tile(
                np.array(term["delta"], dtype=float), (len(vertices), 1)
            )
            if term.get("radial_x"):
                displacement[:, 0] *= np.sign(vertices[:, 0] - term["center"][0])
            if "attract_to" in term:
                displacement += (np.array(term["attract_to"]) - vertices) * np.array(
                    term["attract_axes"]
                )
            delta += weight[:, None] * displacement
        result[name] = delta
    for region, patch in enumerate(patches, 1):
        ids = np.where(metadata[:, 0] == region)[0]
        t = metadata[ids, 1]
        theta = metadata[ids, 2]
        if patch["kind"] == "eye":
            cx, cz = patch["center"]
            ix, iz = patch["inner_radii"]
            side = patch["side"]
            blink = vertices.copy()
            original_z = (
                cz + iz * np.sign(np.sin(theta)) * np.abs(np.sin(theta)) ** 0.75
            )
            middle = patch["blink_seam_z"] + patch.get("blink_slope", 0) * np.cos(theta)
            blink[ids, 2] += (middle - original_z) * t**1.4
            for i in ids:
                hit = surface(blink[i, 0], blink[i, 2])
                blink[i, 1] = min(
                    blink[i, 1],
                    hit[1] - patch.get("blink_clearance", 0) * metadata[i, 1],
                )
            result["eyeBlink_" + side] = blink - vertices
            delta = np.zeros_like(vertices)
            delta[ids, 2] = patch["wide_amplitude"] * np.sin(theta) * t**1.4
            result["eyeWide_" + side] = delta
        else:
            jaw = controls["jaw"]
            lower = 1 / (
                1
                + np.exp(
                    np.clip(
                        (vertices[:, 2] - jaw["seam_z"]) / jaw["transition"], -40, 40
                    )
                )
            )
            weight = field(jaw) * lower
            move = weight[:, None] * np.array(jaw["delta"])
            ring_weight = (
                t * np.maximum(0, -np.sin(theta)) ** 0.7 + (1 - t) * weight[ids]
            )
            move[ids] = ring_weight[:, None] * np.array(jaw["delta"])
            result["jawOpen"] = move
    return result


def facial_topology(config):
    root = Path(config["output"])
    face = json.loads(Path(config["face_config"]).read_text())
    from run import digest

    if face.get("source_sha256") != digest(config["source"]):
        raise ValueError("Facial patch source hash mismatch")
    bpy.ops.wm.open_mainfile(filepath=str(root / "source.blend"), load_ui=False)
    high = bpy.data.objects["Source_High"]
    bvh = BVHTree.FromObject(high, bpy.context.evaluated_depsgraph_get())
    bounds = np.array(json.loads((root / "source_report.json").read_text())["bounds"])
    span = max(bounds[1] - bounds[0])

    def surface(x, z):
        hit, _, _, _ = bvh.ray_cast(
            Vector((x, bounds[0, 1] - span, z)), Vector((0, 1, 0)), span * 3
        )
        if hit is None:
            raise ValueError("Missing high surface for facial patch")
        return np.array(hit)

    bpy.ops.wm.obj_import(
        filepath=str(root / "source_quads.obj"), forward_axis="NEGATIVE_Y", up_axis="Z"
    )
    obj = bpy.context.object
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    vertices = coordinates(obj).tolist()
    faces = [list(p.vertices) for p in obj.data.polygons]
    metadata = [(0, 0, 0)] * len(vertices)
    report = []
    for region, patch in enumerate(face["patches"], 1):
        faces, record = build_patch(
            vertices, faces, metadata, patch, region, surface, face["front_depth"]
        )
        report.append(record)
    active = np.unique(np.concatenate(faces))
    inverse = np.full(len(vertices), -1, int)
    inverse[active] = np.arange(len(active))
    vertices = np.array(vertices)[active]
    metadata = np.array(metadata)[active]
    faces = [inverse[f].tolist() for f in faces]
    bpy.data.objects.remove(obj, do_unlink=True)
    low = make_mesh("Lowpoly_Head", vertices, faces)
    low.data.materials.append(material("Lowpoly clay"))
    deltas = create_controls(
        vertices, metadata, face["patches"], face["controls"], surface
    )
    low.shape_key_add(name="Basis")
    for name, delta in deltas.items():
        key = low.shape_key_add(name=name)
        key.data.foreach_set("co", np.asarray(vertices + delta, np.float32).ravel())
    # Neck/jaw weights use smooth explicit anatomical fields; they sum to one.
    rig = face["weights"]
    nw = np.clip((rig["neck_start_z"] - vertices[:, 2]) / rig["neck_transition"], 0, 1)
    nw = nw * nw * (3 - 2 * nw)
    cx, cz = rig["jaw_center"]
    sx, sz = rig["jaw_sigma"]
    lower = 1 / (
        1
        + np.exp(
            np.clip(
                (vertices[:, 2] - rig["jaw_seam_z"]) / rig["jaw_transition"], -40, 40
            )
        )
    )
    front = np.clip(
        (face["controls"]["front_mask_start"] - vertices[:, 1])
        / face["controls"]["front_mask_width"],
        0,
        1,
    )
    jw = (
        rig["jaw_strength"]
        * np.exp(
            -0.5 * ((vertices[:, 0] - cx) / sx) ** 2
            - 0.5 * ((vertices[:, 2] - cz) / sz) ** 2
        )
        * front
        * lower
        * (1 - nw)
    )
    for name, weights in [("Neck", nw), ("Jaw", jw), ("Head", 1 - nw - jw)]:
        vg = low.vertex_groups.new(name=name)
        for i in np.where(weights > 0)[0]:
            vg.add([int(i)], float(weights[i]), "REPLACE")
    for edge in low.data.edges:
        a, b = vertices[list(edge.vertices)]
        if a[0] * b[0] <= 0 and (a[1] + b[1]) * 0.5 > face["uv_back_depth"]:
            edge.use_seam = True
    bpy.ops.object.select_all(action="DESELECT")
    low.select_set(True)
    bpy.context.view_layer.objects.active = low
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    uv_started = time.monotonic()
    uv_method = config.get("uv_method", "CONFORMAL")
    bpy.ops.uv.unwrap(method=uv_method, margin=0.02)
    uv_seconds = time.monotonic() - uv_started
    bpy.ops.object.mode_set(mode="OBJECT")
    np.savez_compressed(
        root / "lowpoly_patch_data.npz", vertices=vertices, metadata=metadata
    )
    (root / "lowpoly_report.json").write_text(
        json.dumps(
            {
                "vertices": len(vertices),
                "faces": len(faces),
                "quads": sum(len(f) == 4 for f in faces),
                "patches": report,
                "blendshapes": list(deltas),
                "method": ("MDF native quads" if config.get("retopology_backend") == "runtime" else "source-derived Instant Meshes quads") + " plus explicitly rebuilt eye/lip rings",
                "uv_method": uv_method,
                "uv_seconds": uv_seconds,
            },
            indent=2,
        )
    )
    high.hide_render = True
    high.hide_set(True)
    for obj in bpy.context.scene.objects:
        if obj.name.startswith("Source_Hair_"):
            obj.hide_render = True
            obj.hide_set(True)
    bpy.ops.wm.save_as_mainfile(filepath=str(root / "Lowpoly_Unbaked.blend"))
    for view, direction in ([("front", (0, -3, 0)), ("side", (3, 0, 0))] if config.get("diagnostic_previews", False) else []):
        render_view(
            bpy.context.scene.camera,
            bounds.mean(0),
            span,
            direction,
            root / f"lowpoly_{view}.png",
        )
    print("LOWPOLY_READY", len(vertices), len(faces), flush=True)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1 :]
    config = json.loads(Path(args[1]).read_text())
    {"working": working_surface, "import": import_retopology, "facial": facial_topology}[args[0]](config)
