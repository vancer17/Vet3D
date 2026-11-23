"""Blender CLI: render the two near-ear views and save their actual cameras."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy
import numpy as np
from blender_io import load_source, coordinates
from head_preview import studio, render_view
from checkpoints import digest


def run(source, output, source_object=None):
    obj = load_source(str(source), source_object)
    matrix = np.asarray(obj.matrix_world)
    vertices = coordinates(obj) @ matrix[:3, :3].T + matrix[:3, 3]
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    camera, center, span = studio([vertices.min(0), vertices.max(0)], size=1536)
    for name, direction, side in [
        ("left_oblique", [2.5, -3, 0], "left"),
        ("right_oblique", [-2.5, -3, 0], "right"),
    ]:
        folder = output / name
        folder.mkdir(parents=True, exist_ok=True)
        image = folder / "color.png"
        render_view(camera, center, span, direction, image)
        bpy.context.view_layer.update()
        meta = dict(
            projection="orthographic",
            width=1536,
            height=1536,
            ortho_scale=camera.data.ortho_scale,
            camera_matrix_world=[list(r) for r in camera.matrix_world],
            image_sha256=digest(image),
            source_sha256=digest(source),
            visible_ear=side,
            direction=direction,
        )
        (folder / "camera.json").write_text(json.dumps(meta, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--source-object")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    run(args.source.resolve(), args.output.resolve(), args.source_object)
