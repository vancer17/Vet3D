"""Blender CLI: bound target renders/poses -> frozen-template 3D ear records."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from blender_io import load_source, coordinates
from checkpoints import digest
from ear_projection import validate_mapping, orthographic_ray, fuse_observations


def project(config):
    source_hash = digest(config["source"])
    mapping = json.loads(Path(config["mapping"]).read_text())
    validate_mapping(mapping, digest(config["template"]))
    obj = load_source(config["source"], config.get("source_object"))
    # BVH and actual render camera share world coordinates, even for transformed inputs.
    vertices = (
        coordinates(obj) @ np.asarray(obj.matrix_world)[:3, :3].T
        + np.asarray(obj.matrix_world)[:3, 3]
    )
    tree = BVHTree.FromPolygons(
        vertices.tolist(), [list(p.vertices) for p in obj.data.polygons]
    )
    extent = float(np.ptp(vertices, axis=0).max())
    observations = {r["id"]: [] for r in mapping["records"]}
    rejected = []
    names = set()
    for view in config["views"]:
        name = view["name"]
        if name in names:
            raise ValueError("Duplicate view name")
        names.add(name)
        camera = json.loads(Path(view["camera"]).read_text())
        if camera["source_sha256"] != source_hash or camera["image_sha256"] != digest(
            view["image"]
        ):
            raise ValueError("Camera does not belong to source/image")
        binding = json.loads(Path(view["binding"]).read_text())
        if binding.get("image_sha256") != digest(view["image"]) or binding.get(
            "pose_sha256"
        ) != digest(view["pose"]):
            raise ValueError("Pose binding does not match the rendered image")
        pose = np.load(view["pose"], allow_pickle=False)
        if pose["keypoints"].shape != (1, 308, 2) or pose["scores"].shape != (1, 308):
            raise ValueError("Expected one Sapiens2 subject with 308 keypoints")
        visible = "both" if name == "front" else camera.get("visible_ear")
        if visible not in ("both", "left", "right") or (
            name != "front" and visible == "both"
        ):
            raise ValueError("Oblique camera must declare its near ear")
        # Validate the camera even if every detector confidence is low.
        orthographic_ray(camera, [camera["width"] / 2, camera["height"] / 2])
        for row in mapping["records"]:
            if visible != "both" and row["ear"] != visible:
                continue
            index = row["id"]
            xy = pose["keypoints"][0, index]
            score = float(pose["scores"][0, index])
            if not np.isfinite(score) or score < 0.7 or not np.isfinite(xy).all():
                rejected.append([name, index, "low_or_invalid_score"])
                continue
            try:
                origin, direction = orthographic_ray(camera, xy)
            except ValueError:
                rejected.append([name, index, "pixel_outside_render"])
                continue
            hit, normal, _, _ = tree.ray_cast(Vector(origin), Vector(direction))
            if hit is None or -normal.dot(Vector(direction)) < 0.08:
                rejected.append([name, index, "miss_or_grazing"])
                continue
            observations[index].append(
                dict(
                    view=name,
                    point=list(hit),
                    normal=list(normal),
                    score=score,
                    facing=float(-normal.dot(Vector(direction))),
                    xy=xy.tolist(),
                )
            )
    result = []
    for row in mapping["records"]:
        obs = observations[row["id"]]
        if not obs:
            continue
        point, weight, disagreement, method = fuse_observations(obs, extent)
        hit, normal, _, _ = tree.find_nearest(Vector(point))
        if hit is None:
            raise ValueError("Empty source surface")
        result.append(
            {
                **row,
                "target": list(hit),
                "normal": list(normal),
                "weight": weight,
                "view_disagreement": disagreement,
                "observations": obs,
                "fusion": method,
            }
        )
    for side in ("left", "right"):
        if sum(r["ear"] == side for r in result) < 4:
            raise ValueError("Insufficient visible ear landmarks: " + side)
    return dict(
        source_sha256=source_hash,
        mapping_sha256=digest(config["mapping"]),
        records=result,
        rejected=rejected,
    )


def main():
    config_path, output = sys.argv[sys.argv.index("--") + 1 :]
    result = project(json.loads(Path(config_path).read_text()))
    Path(output).write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
