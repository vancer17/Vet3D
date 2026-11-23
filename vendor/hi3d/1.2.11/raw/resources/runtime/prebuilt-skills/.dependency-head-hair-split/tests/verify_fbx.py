"""Blender importer check for a synthetic page/export; caller supplies a budget.

Usage: blender -b --factory-startup --python-exit-code 1 --python verify_fbx.py
       -- PAGE.html EXPORTED.fbx THRESHOLD
Not part of the normal HTML-delivery route; no user model is cut here.
"""
import base64
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys

import bpy
import numpy as np

page_path, fbx_path, threshold = sys.argv[sys.argv.index("--") + 1:]
page = Path(page_path).read_text()
def content(name):
    return re.search(r'<script id="' + name + r'"[^>]*>([\s\S]*?)</script>', page).group(1)
meta = json.loads(content("metadata"))
raw = gzip.decompress(base64.b64decode(content("payload")))
def array(name):
    f = meta["fields"][name]
    return np.frombuffer(raw, dtype=f["dtype"], count=f["length"], offset=f["offset"]).reshape(f["shape"])
positions, faces, uv = (array(k) for k in ("positions", "faces", "uv"))
# This symmetric grid fixture's mincut equals its threshold labels (checked by parity test).
labels = array("lum") > float(threshold)
expected = positions[:, [0, 2, 1]].copy()
expected[:, 1] *= -1
image_hash = hashlib.sha256(base64.b64decode(content("texture"))).hexdigest()
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.fbx(filepath=fbx_path, use_custom_normals=True)
objects = [o for o in bpy.context.scene.objects if o.type == "MESH"]
assert sorted(o.name for o in objects) == ["Hair", "Head"]
report = []
for obj in objects:
    mesh = obj.data
    target = faces[labels == (obj.name == "Hair")]
    assert len(mesh.polygons) == len(target)
    assert all(len(p.vertices) == 3 for p in mesh.polygons)
    co = np.empty(len(mesh.vertices)*3, dtype=np.float32)
    mesh.vertices.foreach_get("co", co)
    matrix = np.asarray(obj.matrix_world)
    co = co.reshape(-1, 3) @ matrix[:3, :3].T + matrix[:3, 3]
    indices = np.empty(len(mesh.loops), dtype=np.int32)
    mesh.loops.foreach_get("vertex_index", indices)
    error = float(np.max(np.abs(co[indices].reshape(-1, 3, 3) - expected[target])))
    assert error < 1e-5, error
    values = np.empty(len(mesh.loops)*2, dtype=np.float32)
    mesh.uv_layers.active.data.foreach_get("uv", values)
    expected_uv = uv[target.reshape(-1)].copy()
    expected_uv[:, 1] = 1 - expected_uv[:, 1]
    assert np.max(np.abs(values.reshape(-1, 2) - expected_uv)) < 1e-6
    images = [n.image for n in mesh.materials[0].node_tree.nodes if n.type == "TEX_IMAGE" and n.image]
    assert images
    image = images[0]
    data = bytes(image.packed_file.data) if image.packed_file else Path(bpy.path.abspath(image.filepath)).read_bytes()
    assert hashlib.sha256(data).hexdigest() == image_hash
    report.append(dict(name=obj.name, faces=len(target), max_position_error=error))
print(json.dumps(dict(passed=True, objects=report, original_image_preserved=True)))
