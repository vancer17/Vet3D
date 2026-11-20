"""Calibrate Sapiens2 IDs on the fixed template, not on arbitrary target geometry."""

import json, sys, hashlib
from pathlib import Path
import numpy as np, bpy
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
import argparse

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument(
    "--assets", type=Path, default=Path(__file__).resolve().parents[1] / "assets/taro"
)
ap.add_argument("--output", type=Path, required=True)
args = ap.parse_args(sys.argv[sys.argv.index("--") + 1 :])
r = args.assets
p = r / "template.npz"
d = np.load(p)
meta = json.loads((r / "sapiens2_camera.json").read_text())
assert (
    hashlib.sha256(p.read_bytes()).hexdigest() == meta["template_sha256"]
), "Template hash mismatch"
if (meta["width"], meta["height"]) != (1024, 1024):
    raise ValueError(
        "This calibration uses the packaged 1024-square orthographic camera"
    )
v = d["vertices"]
w = v @ np.array(meta["native_to_world"]).T
q = d["quads"]
cam = Matrix(meta["camera_matrix_world"])
inv = np.array(cam.inverted())
local = w @ inv[:3, :3].T + inv[:3, 3]
size = meta["ortho_scale"]
pixels = np.column_stack(
    ((local[:, 0] / size + 0.5) * 1024, (0.5 - local[:, 1] / size) * 1024)
)
regions = json.loads((p.parent / "regions.json").read_text())
mask = np.zeros(len(v), bool)
mask[regions["bake_indices"]] = True
faces = q[mask[q].sum(1) >= 3]
bvh = BVHTree.FromPolygons([Vector(x) for x in w], faces.tolist(), all_triangles=False)
dir = cam.to_3x3() @ Vector((0, 0, -1))
origin0 = cam.translation
# Restrict snapping to visible exterior vertices; reject internal eyelid/neck/back surfaces.
visible = []
for idx in np.flatnonzero(mask):
    point = Vector(w[idx])
    hit = bvh.ray_cast(point - dir * 0.5, dir, 1)[0]
    if hit is not None and (hit - point).length < 0.0002:
        visible.append(idx)
visible = np.array(visible)
kp = np.load(r / "sapiens2_pose.npz")
assert kp["keypoints"].shape == (1, 308, 2)
assert np.isfinite(kp["keypoints"]).all()
names = json.loads((r / "sapiens2_keypoint_names.json").read_text())
records = []
ids = (
    list(range(96, 105))
    + list(range(120, 129))
    + list(range(144, 153))
    + list(range(161, 170))
    + list(range(188, 220))
    + list(range(71, 76))
    + list(range(178, 188))
    + [77]
)
for i in ids:
    xy = kp["keypoints"][0, i]
    origin = cam @ Vector(((xy[0] / 1024 - 0.5) * size, (0.5 - xy[1] / 1024) * size, 0))
    hit, normal, face, dist = bvh.ray_cast(origin, dir, 2)
    method = "ray_hit_nearest_3d_vertex"
    idx = None
    if hit is not None:
        dd = np.linalg.norm(w[visible] - np.array(hit), axis=1)
        idx = int(visible[dd.argmin()])
        distance = float(dd.min())
        pixelerr = float(np.linalg.norm(pixels[idx] - xy))
    else:
        pixelerr = float("inf")
    if pixelerr > 6:
        # At the eye/lip aperture, snap only to a visible exterior point within six pixels.
        pp = np.linalg.norm(pixels[visible] - xy, axis=1)
        j = pp.argmin()
        idx = int(visible[j])
        pixelerr = float(pp[j])
        distance = None
        method = "aperture_visible_vertex_snap"
    region = (
        "eyes"
        if i < 178 and i >= 96
        else ("lips" if 188 <= i <= 219 else ("contour" if i == 77 else "nose"))
    )
    accepted = pixelerr <= 6 and float(kp["scores"][0, i]) >= 0.7
    records.append(
        {
            "keypoint_id": i,
            "name": names[str(i)],
            "region": region,
            "score": float(kp["scores"][0, i]),
            "detected_xy": xy.tolist(),
            "vertex_index": idx,
            "vertex_native": v[idx].tolist(),
            "vertex_xy": pixels[idx].tolist(),
            "pixel_error": pixelerr,
            "hit_to_vertex_world": distance,
            "method": method,
            "accepted": accepted,
            "default_enabled": accepted and region in ["eyes", "lips"],
        }
    )
out = {
    "schema_version": 1,
    "template_sha256": meta["template_sha256"],
    "template_vertices": len(v),
    "upstream_commit": "7e5bae88456ac418ff0e58e74106c9fe192055d4",
    "keypoint_count": 308,
    "coordinate_semantics": "Sapiens2 original raster xy pixels; zero-based template vertex_index",
    "camera": meta,
    "max_pixel_error": 6,
    "records": records,
    "reuse_scope": "Only identical template content and unchanged Sapiens2 keypoint definition. Re-detect and raycast each new target; never reuse target coordinates.",
}
args.output.write_text(json.dumps(out, indent=2))
print(
    json.dumps(
        {
            "visible_vertices": len(visible),
            "counts": {
                g: sum(a["accepted"] and a["region"] == g for a in records)
                for g in ["eyes", "lips", "nose", "contour"]
            },
            "rejected": [
                (a["keypoint_id"], a["pixel_error"])
                for a in records
                if not a["accepted"]
            ],
        }
    )
)
