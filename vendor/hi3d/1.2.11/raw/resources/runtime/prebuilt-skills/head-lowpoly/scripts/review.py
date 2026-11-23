"""Render comparable views and matched-control frames from the delivered scene."""

import json
import sys
from pathlib import Path
import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_engine import set_engine

from blender_io import render_view


def select_variant(scene, variant):
    for obj in scene.objects:
        if obj.type == "MESH":
            visible = (
                obj.name == "Source_High" or obj.name.startswith("Source_Hair_")
                if variant == "high"
                else (
                    obj.name.startswith("Lowpoly_")
                    if variant == "lowpoly"
                    else False
                )
            )
            obj.hide_render = not visible
            obj.hide_set(not visible)


def render_review(config):
    root = Path(config["output"])
    dest = root / "review"
    dest.mkdir(exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(root / "Heads_Rigged.blend"), load_ui=False)
    scene = bpy.context.scene
    scene.frame_set(1)
    set_engine(scene)
    scene.render.resolution_x = scene.render.resolution_y = config.get(
        "review_size", 640
    )
    source_report = json.loads((root / "source_report.json").read_text())
    bounds = np.array(source_report.get("review_bounds", source_report["bounds"]))
    center = bounds.mean(0)
    span = max(bounds[1] - bounds[0])
    heads = [bpy.data.objects["Lowpoly_Head"]]
    for obj in heads:
        obj.data.shape_keys.animation_data_clear()
        for key in obj.data.shape_keys.key_blocks:
            key.value = 0

    def controls(name=None, value=0):
        for obj in heads:
            for key in obj.data.shape_keys.key_blocks:
                key.value = value if key.name == name else 0

    for variant in ["high", "lowpoly"]:
        select_variant(scene, variant)
        for label, direction in [
            ("front", (0, -3, 0)),
            ("threequarter", (1.7, -3, 0)),
            ("side", (3, 0, 0)),
        ]:
            render_view(
                scene.camera, center, span, direction, dest / f"{variant}_{label}.png"
            )
        if variant == "high":
            continue
        for name, value in [("eyeBlink_L", 1), ("mouthSmile", 0.75), ("jawOpen", 1)]:
            controls(name, value)
            render_view(
                scene.camera, center, span, (0, -3, 0), dest / f"{variant}_{name}.png"
            )
            controls()
    # Neutral wireframe exposes actual topology with identical cameras.
    obj = heads[0]
    select_variant(scene, "lowpoly")
    wire = obj.modifiers.new("Review wire only", "WIREFRAME")
    wire.thickness = span * 0.00022
    wire.use_replace = True
    render_view(scene.camera, center, span, (0, -3, 0), dest / "lowpoly_wire.png")
    obj.modifiers.remove(wire)
    if config.get("video_frames_per_control", 0):
        names = np.load(root / "lowpoly_data.npz")["expression_names"].tolist()
        frames = []
        for i, name in enumerate(names):
            for k in range(config["video_frames_per_control"]):
                value = (
                    0.75
                    * np.sin(np.pi * k / (config["video_frames_per_control"] - 1)) ** 2
                )
                controls(name, value)
                index = len(frames)
                frames.append({"index": index, "control": name, "weight": float(value)})
                for variant in ["lowpoly"]:
                    select_variant(scene, variant)
                    render_view(
                        scene.camera,
                        center,
                        span,
                        (0, -3, 0),
                        dest / f"{variant}_{index:04d}.png",
                    )
        (dest / "frames.json").write_text(json.dumps(frames, indent=2))
    print("REVIEW_READY", dest, flush=True)


if __name__ == "__main__":
    render_review(json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text()))
