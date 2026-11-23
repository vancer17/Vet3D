"""Render actually evaluated poses using the packed static review materials."""

import json, sys
from pathlib import Path
import bpy, numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from head_preview import studio, render_view


def run(config):
    root = Path(config["output"])
    data = np.load(root / "expression_poses.npz", allow_pickle=False)
    bpy.ops.wm.open_mainfile(filepath=str(root / "MetaHuman_Review.blend"))
    head = next(
        o
        for o in bpy.context.scene.objects
        if o.name.startswith("MetaHuman registered")
    )
    meshes = {"head_lod0_mesh": head}
    for o in bpy.context.scene.objects:
        if o.type == "MESH" and o.name.startswith(("eyeLeft_", "eyeRight_", "teeth_")):
            meshes[o.name] = o
    target = np.load(config["target"], allow_pickle=False)["vertices"]
    for obj in list(bpy.context.scene.objects):
        if obj.type in ["LIGHT", "CAMERA"]:
            bpy.data.objects.remove(obj, do_unlink=True)
    camera, center, span = studio(
        [target.min(0), target.max(0)], config.get("expression_render_size", 640)
    )
    folder = root / "expressions"
    folder.mkdir(exist_ok=True)
    for i, name in enumerate(data["pose_names"]):
        for mesh, obj in meshes.items():
            obj.data.vertices.foreach_set("co", data[mesh + "_poses"][i].ravel())
            obj.data.update()
        render_view(camera, center, span, (0, -3, 0), folder / f"pose_{i:02d}.png")


if __name__ == "__main__":
    run(json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text()))
