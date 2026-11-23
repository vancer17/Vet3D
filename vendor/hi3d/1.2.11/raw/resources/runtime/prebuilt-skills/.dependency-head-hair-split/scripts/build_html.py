"""Prepare a self-contained, user-operated page. Never run mincut here.

Use workflow.py html so preparation has a wall-clock budget and heartbeat.
"""
import argparse
import base64
import gzip
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.spatial.transform import Rotation
from apply_labels import transfer_labels
from checkpoints import digest
from graphcut import prepare_graph
from label_texture import sample
from partition import access, read, validate

ASSETS = Path(__file__).resolve().parents[1] / "assets/viewer"


def world_matrix(doc):
    """Resolve the single static mesh instance; reject cycles/ambiguous parents."""
    nodes = doc["nodes"]
    parents = {}
    for i, node in enumerate(nodes):
        for child in node.get("children", []):
            if child in parents or not isinstance(child, int) or not 0 <= child < len(nodes):
                raise ValueError("Ambiguous or invalid node hierarchy")
            parents[child] = i
    index = next(i for i, n in enumerate(nodes) if n.get("mesh") == 0)
    result, seen = np.eye(4), set()
    while True:
        if index in seen:
            raise ValueError("Cyclic node hierarchy")
        seen.add(index)
        node = nodes[index]
        if node.get("extensions"):
            raise ValueError("Node extensions are unsupported in the HTML exporter")
        if "matrix" in node:
            if any(k in node for k in ("rotation", "scale", "translation")):
                raise ValueError("Node cannot combine matrix and TRS")
            local = np.asarray(node["matrix"], dtype=float).reshape(4, 4, order="F")
        else:
            local = np.eye(4)
            local[:3, :3] = Rotation.from_quat(node.get("rotation", [0, 0, 0, 1])).as_matrix() * node.get("scale", [1, 1, 1])
            local[:3, 3] = node.get("translation", [0, 0, 0])
        if not np.isfinite(local).all() or not np.allclose(local[3], [0, 0, 0, 1]):
            raise ValueError("Invalid affine node transform")
        result = local @ result
        if index not in parents:
            break
        index = parents[index]
    roots = doc["scenes"][doc.get("scene", 0)]["nodes"]
    if roots.count(index) != 1 or any(i in seen for i in roots if i != index):
        raise ValueError("Mesh must occur once in the default scene")
    if abs(np.linalg.det(result[:3, :3])) < 1e-15:
        raise ValueError("Singular node transform")
    return result


def diffuse(doc, binary, prim, count):
    """Extract the referenced diffuse image, not images[0]; no PBR conversion."""
    material = doc["materials"][prim["material"]]
    if material.get("alphaMode", "OPAQUE") != "OPAQUE" or material.get("extensions"):
        raise ValueError("HTML FBX supports opaque standard diffuse materials only")
    pbr = material["pbrMetallicRoughness"]
    info = pbr["baseColorTexture"]
    if info.get("extensions"):
        raise ValueError("Texture transforms are unsupported")
    texture = doc["textures"][info["index"]]
    uv = access(doc, binary, prim["attributes"]["TEXCOORD_" + str(info.get("texCoord", 0))])
    if uv.shape != (count, 2) or not np.isfinite(uv).all():
        raise ValueError("Invalid source UV")
    sampler = doc.get("samplers", [])[texture["sampler"]] if "sampler" in texture else {}
    wrap = {k: sampler.get(k, 10497) for k in ("wrapS", "wrapT")}
    if any(v not in (10497, 33071) for v in wrap.values()):
        raise ValueError("HTML FBX supports repeat/clamp, not mirrored wrapping")
    factor = np.asarray(pbr.get("baseColorFactor", [1, 1, 1, 1]), dtype=float)
    if factor.shape != (4,) or not np.isfinite(factor).all() or np.any(factor < 0) or np.any(factor > 1):
        raise ValueError("Invalid source color factor")
    if "COLOR_0" in prim["attributes"]:
        raise ValueError("Vertex colors cannot be preserved by this diffuse FBX exporter")
    img = doc["images"][texture["source"]]
    view = doc["bufferViews"][img["bufferView"]]
    offset = view.get("byteOffset", 0)
    if view.get("buffer", 0) != 0 or offset < 0 or offset + view["byteLength"] > len(binary):
        raise ValueError("Invalid source image range")
    image = binary[offset:offset + view["byteLength"]]
    with Image.open(io.BytesIO(image)) as im:
        if im.format not in ("JPEG", "PNG"):
            raise ValueError("HTML FBX supports embedded PNG/JPEG only")
        filename = "original.jpg" if im.format == "JPEG" else "original.png"
        im.verify()
    return uv, image, dict(filename=filename, factor=factor[:3].tolist(), **wrap)


def prepare(source, label_mesh, threshold=None, tolerance=1e-6):
    doc, binary = read(source)
    vertices, faces = validate(doc, binary)
    lv, lf, _, info, lum = sample(label_mesh, threshold, with_luminance=True)
    mapping, mapping_report = transfer_labels(vertices, faces, lv, lf, np.arange(len(lf)), tolerance)
    graph = prepare_graph(vertices, faces)
    prim = doc["meshes"][0]["primitives"][0]
    uv, image, material = diffuse(doc, binary, prim, len(vertices))
    if "NORMAL" in prim["attributes"]:
        normals = access(doc, binary, prim["attributes"]["NORMAL"]).astype(float)
    else:
        normals = np.zeros_like(vertices, dtype=float)
        tri = vertices[faces].astype(float)
        cross = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        for corner in range(3):
            np.add.at(normals, faces[:, corner], cross)
    if normals.shape != vertices.shape or not np.isfinite(normals).all():
        raise ValueError("Invalid source normals")
    world = world_matrix(doc)
    positions = vertices.astype(float) @ world[:3, :3].T + world[:3, 3]
    normals = normals @ np.linalg.inv(world[:3, :3])
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-30)
    # Bake mirrored transforms for FBX without changing triangle membership.
    display_faces = faces[:, [0, 2, 1]] if np.linalg.det(world[:3, :3]) < 0 else faces
    arrays = {"positions": positions.astype("<f4"), "faces": display_faces.astype("<u4"),
              "normals": normals.astype("<f4"), "uv": uv.astype("<f4"), "lum": lum[mapping].astype("<f8")}
    for name in ("a", "b", "distance", "weight", "area", "component"):
        values = graph[name] / graph[name].mean() if name == "area" else graph[name]
        arrays[name] = values.astype("<u4" if name in ("a", "b", "component") else "<f8")
    metadata = {"schema": 1, "faces": len(faces), "vertices": len(vertices), "threshold": info["threshold"],
                "diagonal": graph["diagonal"], "mainComponent": graph["mainComponent"], "shells": graph["shells"],
                "mapping": mapping_report, "sourceSha256": digest(source), "labelSha256": digest(label_mesh),
                "material": material, "state": "awaiting_user_action", "mincut_executed": False}
    return arrays, metadata, image


def build(source, label_mesh, output, threshold=None, tolerance=1e-6):
    arrays, meta, image = prepare(source, label_mesh, threshold, tolerance)
    output.mkdir(parents=True, exist_ok=False)
    raw, fields = bytearray(), {}
    for name, array in arrays.items():
        raw.extend(b"\0" * (-len(raw) % 8))
        fields[name] = dict(offset=len(raw), length=array.size, dtype=array.dtype.str, shape=list(array.shape))
        raw.extend(array.tobytes())
    meta["fields"] = fields
    compressed = gzip.compress(raw, compresslevel=5, mtime=0)
    escape = lambda text: text.replace("</script", "<\\/script")
    page = (ASSETS / "page.html").read_text()
    for marker, name in (("THREE", "three.min.js"), ("ORBIT", "OrbitControls.js"), ("CUT", "cut.js"), ("APP", "app.js")):
        page = page.replace("/*" + marker + "*/", escape((ASSETS / name).read_text()))
    worker = "\n".join((ASSETS / name).read_text() for name in ("cut.js", "fbx.js", "worker.js"))
    for marker, value in (("META", json.dumps(meta, ensure_ascii=True).replace("<", "\\u003c")),
                          ("PAYLOAD", base64.b64encode(compressed).decode()),
                          ("TEXTURE", base64.b64encode(image).decode()), ("WORKER", escape(worker))):
        page = page.replace(">" + marker + "<", ">" + value + "<")
    page += "\n<!-- Three.js / OrbitControls license:\n" + (ASSETS / "LICENSE-three.txt").read_text().replace("--", "—") + "\n-->\n"
    html = output / "head-hair-split.html"
    html.write_text(page, encoding="utf-8")
    manifest = dict(meta, html=html.name, htmlSha256=digest(html),
                    delivery="Provide this HTML link, open it for the user, then stop. Do not click mincut or download on the user's behalf.")
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return html


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--label-mesh", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threshold", type=float)
    parser.add_argument("--tolerance", type=float, default=1e-6)
    args = parser.parse_args()
    print(build(args.source, args.label_mesh, args.output, args.threshold, args.tolerance))
