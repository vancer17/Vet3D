"""Blender: turn source-bound orthographic Sapiens2 detections into fit settings."""

import hashlib
import argparse
import json
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from blender_io import load_source
from sapiens2_landmarks import build_landmarks
from camera_ray import pixel_ray
from template_defaults import resolve_template_config


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(config):
    config = resolve_template_config(config)
    assets = Path(__file__).resolve().parents[1] / "assets/taro"
    mapping = Path(config.get("mapping", assets / "sapiens2_mapping.json"))
    names = json.loads(
        Path(config.get("names", assets / "sapiens2_keypoint_names.json")).read_text()
    )
    camera = json.loads(Path(config["camera"]).read_text())
    if camera.get("projection") != "orthographic":
        raise ValueError("Supply a recorded orthographic render camera")
    for key, path in [
        ("source_sha256", config["high_glb"]),
        ("image_sha256", config["image"]),
    ]:
        if camera.get(key) != digest(path):
            raise ValueError(f"Camera/render provenance mismatch: {key}")
    settings = json.loads(Path(config["settings"]).read_text())
    if settings.get("template_sha256") != digest(config["template"]) or settings.get(
        "target_sha256"
    ) != digest(config["target"]):
        raise ValueError(
            "Existing masks must match this template and target sample file"
        )
    pose = np.load(config["pose"], allow_pickle=False)
    xy, scores = pose["keypoints"], pose["scores"]
    if xy.shape != (1, 308, 2) or scores.shape != (1, 308) or not np.isfinite(xy).all():
        raise ValueError("Expected one person's 308 original-image keypoints")
    matrix = np.asarray(camera["camera_matrix_world"], float)
    width, height, scale = camera["width"], camera["height"], camera["ortho_scale"]
    if (
        matrix.shape != (4, 4)
        or not np.isfinite(matrix).all()
        or width != height
        or width <= 0
        or not np.isfinite(scale)
        or scale <= 0
    ):
        raise ValueError("Use a valid square orthographic render and camera")
    source = load_source(config["high_glb"], config.get("source_object"))
    tree = BVHTree.FromObject(source, bpy.context.evaluated_depsgraph_get())
    points = np.full((308, 3), np.nan)
    for i, (x, y) in enumerate(xy[0]):
        if not (0 <= x < width and 0 <= y < height):
            continue
        origin, direction = pixel_ray(matrix, width, height, scale, [x, y])
        hit = tree.ray_cast(Vector(origin), Vector(direction))[0]
        if hit is not None:
            points[i] = hit
    settings["landmarks"] = build_landmarks(
        config["template"], mapping, points, scores[0], names
    )
    settings["landmark_group_budgets"] = {"left_eye": 6, "right_eye": 6, "lips": 6}
    settings["landmark_huber_fraction"] = 0.025
    settings["provenance"] = dict(
        method="Sapiens2 eye/lip IDs raycast onto the source mesh using its recorded render camera; inspect visible eyelid/lip boundaries before fitting",
        source_sha256=digest(config["high_glb"]),
        image_sha256=digest(config["image"]),
        pose_sha256=digest(config["pose"]),
        mapping_sha256=digest(mapping),
        camera=camera,
    )
    Path(config["output_settings"]).write_text(json.dumps(settings, indent=2))
    print(
        json.dumps(
            {
                "landmarks": len(settings["landmarks"]),
                "output": config["output_settings"],
            }
        )
    )


def main(argv=None):
    values = list(argv) if argv is not None else sys.argv[1:]
    if "--" in values:
        values = values[values.index("--") + 1:]
    parser = argparse.ArgumentParser(description="Project source-verified Sapiens2 landmarks onto a mesh")
    parser.add_argument("config", type=Path, help="JSON camera, input mesh, pose and output-settings configuration")
    args = parser.parse_args(values)
    return run(json.loads(args.config.read_text()))


if __name__ == "__main__":
    main()
