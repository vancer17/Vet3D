"""Measure frontmost 3D surface heights on a local transition grid."""

import bpy, numpy as np, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mathutils import Vector
import hashlib


def run(root):
    cfg = json.loads((root / "render_original.json").read_text())
    profile = json.loads((root / "profile.json").read_text())
    grid = profile["heightfield"]
    x = np.linspace(*grid["x"])
    y = np.linspace(*grid["y"])
    fields = {}
    for kind in ["source", "template"]:
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)
        if kind == "source":
            bpy.ops.import_scene.gltf(filepath=cfg["source"])
            objects = [o for o in bpy.context.scene.objects if o.type == "MESH"]
            if len(objects) != 1:
                raise ValueError("Expected one source mesh")
            ob = objects[0]
        else:
            d = np.load(root / "fit/structural_prior.npz")
            v = d["vertices"]
            q = d["quads"]
            m = bpy.data.meshes.new("Template")
            m.from_pydata(np.c_[v[:, 0], -v[:, 2], v[:, 1]].tolist(), [], q.tolist())
            m.update()
            ob = bpy.data.objects.new("Template", m)
            bpy.context.collection.objects.link(ob)
        ray_y = min(
            (ob.matrix_world @ Vector(corner)).y for corner in ob.bound_box
        ) - max(grid["x"][1] - grid["x"][0], grid["y"][1] - grid["y"][0])
        inv = ob.matrix_world.inverted()
        direction = inv.to_3x3() @ Vector((0, 1, 0))
        a = np.empty((len(y), len(x)))
        for iy, yy in enumerate(y):
            for ix, xx in enumerate(x):
                hit, p, n, f = ob.ray_cast(inv @ Vector((xx, ray_y, yy)), direction)
                a[iy, ix] = -(ob.matrix_world @ p).y if hit else np.nan
        fields[kind] = a
        print(kind, np.isfinite(a).sum(), flush=True)
    np.savez_compressed(
        root / "heightfields.npz",
        x=x,
        y=y,
        **fields,
        source_sha256=hashlib.sha256(Path(cfg["source"]).read_bytes()).hexdigest(),
        donor_sha256=hashlib.sha256(
            (root / "fit/structural_prior.npz").read_bytes()
        ).hexdigest(),
        profile_sha256=hashlib.sha256((root / "profile.json").read_bytes()).hexdigest(),
    )


if __name__ == "__main__":
    from timing import stage

    root = Path(sys.argv[sys.argv.index("--") + 1])
    with stage(root / "timings.jsonl", "nose_heightfield"):
        run(root)
