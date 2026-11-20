"""Blender adapter: one source, exact front camera and area-weighted samples."""

import sys, json, hashlib, time
from pathlib import Path
import bpy, numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_engine import set_engine

from blender_io import load_source, coordinates
from head_preview import studio, render_view
from surface import sample_surface


def run(c):
    start = time.perf_counter()
    out = Path(c["output"])
    out.mkdir(exist_ok=True, parents=True)
    ob = load_source(c["source"], c.get("source_object"))
    mesh = ob.data
    mesh.calc_loop_triangles()
    v = coordinates(ob)
    f = np.empty((len(mesh.loop_triangles), 3), np.int32)
    mesh.loop_triangles.foreach_get("vertices", f.ravel())
    n = np.empty_like(v)
    mesh.vertices.foreach_get("normal", n.ravel())
    p, normal, ids, bary = sample_surface(
        v, f, n, count=c.get("sample_count", 150000), seed=914
    )
    np.savez_compressed(
        out / "surface_raw.npz",
        vertices=p,
        normals=normal,
        source_triangle_indices=ids,
        source_vertex_indices=f[ids],
        barycentric=bary,
        source_sha256=hashlib.sha256(Path(c["source"]).read_bytes()).hexdigest(),
    )
    if c.get("source_has_hair"):
        from mathutils import Vector

        visible = np.zeros(len(p), bool)
        inv = ob.matrix_world.inverted()
        direction = inv.to_3x3() @ Vector((0, 1, 0))
        eps = float(np.ptp(v, axis=0).max()) * 0.001
        ray_y = float(v[:, 1].min() - 1)
        for i in np.where(normal[:, 1] < -0.05)[0]:
            hit, point, _, _ = ob.ray_cast(
                inv @ Vector((float(p[i, 0]), ray_y, float(p[i, 2]))), direction
            )
            if hit:
                visible[i] = abs((ob.matrix_world @ point).y - p[i, 1]) < eps
        np.savez_compressed(
            out / "visibility.npz",
            visible=visible,
            source_sha256=hashlib.sha256(Path(c["source"]).read_bytes()).hexdigest(),
            depth_tolerance=eps,
        )
    for poly in mesh.polygons:
        poly.use_smooth = True
    camera, center, span = studio([v.min(0), v.max(0)], size=1024)
    scene = bpy.context.scene
    mode = c.get("render_mode", "textured")
    if mode not in {"textured", "gray"}:
        raise ValueError("render_mode must be textured or gray")
    if mode == "textured":
        set_engine(scene)
        scene.render.film_transparent = False
        scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.5, .5, .5, 1)
        scene.world.node_tree.nodes["Background"].inputs[1].default_value = .7
        scene.view_settings.view_transform = "AgX"
        for light in bpy.data.lights:
            light.energy *= .45
        # Detection render only: retain base color; suppress glare and bump cues.
        for mat in mesh.materials:
            if mat and mat.use_nodes:
                for node in mat.node_tree.nodes:
                    if node.type == "BSDF_PRINCIPLED":
                        for name, value in [("Metallic", 0), ("Roughness", 1),
                                            ("Specular IOR Level", 0)]:
                            if name in node.inputs:
                                for link in list(node.inputs[name].links):
                                    mat.node_tree.links.remove(link)
                                node.inputs[name].default_value = value
                        for link in list(node.inputs["Normal"].links):
                            mat.node_tree.links.remove(link)
    else:
        scene.render.engine = "BLENDER_WORKBENCH"
        scene.display.shading.light = "STUDIO"
        scene.display.shading.studiolight_rotate_z = 0.3
        scene.display.shading.color_type = "SINGLE"
        scene.display.shading.single_color = (0.62, 0.62, 0.62)
        scene.display.shading.show_cavity = False
        scene.display.shading.show_shadows = False
        scene.display.shading.background_type = "WORLD"
        scene.world.color = (0.85, 0.85, 0.85)
    render_view(camera, center, span, [0, -3, 0], out / "front.png")
    bpy.context.view_layer.update()
    meta = {
        "projection": "orthographic",
        "render_mode": mode,
        "width": 1024,
        "height": 1024,
        "ortho_scale": camera.data.ortho_scale,
        "camera_matrix_world": [list(row) for row in camera.matrix_world],
        "source_sha256": hashlib.sha256(Path(c["source"]).read_bytes()).hexdigest(),
        "image_sha256": hashlib.sha256((out / "front.png").read_bytes()).hexdigest(),
        "coordinates": "Blender Z-up, -Y-front; GLB(x,y,z) -> Blender(x,-z,y)",
        "seconds": time.perf_counter() - start,
    }
    (out / "camera.json").write_text(json.dumps(meta, indent=2))
    print(
        json.dumps(
            {
                "samples": len(p),
                "seconds": meta["seconds"],
                "image": str(out / "front.png"),
            }
        )
    )


if __name__ == "__main__":
    from timing import stage

    c = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text())
    with stage(Path(c["output"]) / "timings.jsonl", "render_samples"):
        run(c)
