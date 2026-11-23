"""Export an embedded-texture static GLB and verify its round-trip in Blender."""

import time
from pathlib import Path
import bpy, numpy as np
from mathutils.kdtree import KDTree
from glb_clips import read_glb


def export_preview(objects, head, path):
    start = time.monotonic()
    path = Path(path)
    original = set(bpy.data.objects)
    points = np.asarray([head.matrix_world @ v.co for v in head.data.vertices])
    expected_triangles = sum(len(p.vertices) - 2 for p in head.data.polygons)
    textured_materials = set()
    for obj in objects:
        for mat in obj.data.materials:
            if mat.use_nodes:
                for node in mat.node_tree.nodes:
                    if node.type == "BSDF_PRINCIPLED" and any(
                        link.from_node.type == "TEX_IMAGE"
                        for link in node.inputs["Base Color"].links
                    ):
                        textured_materials.add(mat.name)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.hide_set(False)
        obj.select_set(True)
        obj["review_scope"] = (
            "Static neutral GLB; expression evaluation is reported separately."
        )
    bpy.context.view_layer.objects.active = head
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        use_selection=True,
        export_skins=False,
        export_morph=False,
        export_animations=False,
        export_normals=True,
        export_texcoords=True,
        export_tangents=True,
        export_extras=True,
    )
    blob = path.read_bytes()
    doc, _ = read_glb(blob)
    if not doc.get("images") or any(
        "bufferView" not in im or "uri" in im for im in doc["images"]
    ):
        raise ValueError("Preview GLB must embed all textures")
    if not any(m.get("normalTexture") for m in doc["materials"]):
        raise ValueError("Preview GLB lost its normal map")
    exported_textures = {
        m.get("name")
        for m in doc["materials"]
        if m.get("pbrMetallicRoughness", {}).get("baseColorTexture")
    }
    if not textured_materials.issubset(exported_textures):
        raise ValueError("GLB lost a skin, eye or oral material texture")
    try:
        bpy.ops.import_scene.gltf(filepath=str(path))
        imported = [
            o for o in bpy.data.objects if o not in original and o.type == "MESH"
        ]
        target = next(o for o in imported if o.name.startswith(head.name))
        tree = KDTree(len(points))
        for i, p in enumerate(points):
            tree.insert(p, i)
        tree.balance()
        error = max(
            tree.find(target.matrix_world @ v.co)[2] for v in target.data.vertices
        )
        reverse = KDTree(len(target.data.vertices))
        for i, v in enumerate(target.data.vertices):
            reverse.insert(target.matrix_world @ v.co, i)
        reverse.balance()
        error = max(error, max(reverse.find(p)[2] for p in points))
        if sum(len(p.vertices) - 2 for p in target.data.polygons) != expected_triangles:
            raise ValueError("GLB changed the head triangle count")
        if error > max(np.ptp(points, axis=0).max(), 1) * 1e-6:
            raise ValueError("GLB round-trip changed head geometry")
        if len(imported) != len(objects):
            raise ValueError("GLB lost an attachment")
    finally:
        for obj in list(bpy.data.objects):
            if obj not in original:
                bpy.data.objects.remove(obj, do_unlink=True)
    return dict(
        seconds=time.monotonic() - start,
        bytes=len(blob),
        meshes=len(objects),
        embedded_images=len(doc["images"]),
        textured_materials=sorted(exported_textures),
        head_position_error_max=error,
        scope="Neutral mesh and embedded textures; no animation or RigLogic inside GLB",
    )
