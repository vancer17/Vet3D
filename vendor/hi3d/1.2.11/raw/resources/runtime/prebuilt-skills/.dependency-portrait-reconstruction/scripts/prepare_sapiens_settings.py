"""Prepare source-derived sample exclusions and reusable template masks."""

import sys, json, hashlib
from pathlib import Path
import numpy as np
from scipy.spatial import ConvexHull
from PIL import Image, ImageDraw


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def prepare(config):
    config = dict(config)
    source_has_hair = config.get("source_has_hair", True)
    config["source_has_hair"] = True  # Always use visibility for local face fitting.
    out = Path(config["output"])
    skill = Path(__file__).resolve().parents[1]
    from surface import smooth_samples

    camera = json.loads((out / "camera.json").read_text())
    binding = json.loads((out / "service_binding.json").read_text())
    if (
        digest(out / "front.png") != camera["image_sha256"]
        or binding["image_sha256"] != camera["image_sha256"]
    ):
        raise ValueError("Sapiens2 invocation is not bound to this render")
    invocation = json.loads((out / "service/invocation.json").read_text())
    if not (invocation["status"] == "SUCCEEDED"):
        raise ValueError("Invalid input: prepare_sapiens_settings contract")
    files = {
        x["field_path"][0]: out / "service/artifacts" / x["file"]
        for x in invocation["files"]
    }
    for x in invocation["files"]:
        if not (digest(out / "service/artifacts" / x["file"]) == x["sha256"]):
            raise ValueError("Invalid input: prepare_sapiens_settings contract")
    pose = np.load(files["pose_data"])
    xy = pose["keypoints"]
    scores = pose["scores"]
    labels = np.load(files["seg_data"])["labels"]
    if not (
        xy.shape == (1, 308, 2)
        and scores.shape == (1, 308)
        and labels.shape == (1024, 1024)
        and np.isfinite(xy).all()
    ):
        raise ValueError("Invalid input: prepare_sapiens_settings contract")
    mapping = json.loads((skill / "assets/taro/sapiens2_mapping.json").read_text())
    camera = json.loads((out / "camera.json").read_text())
    data = dict(np.load(out / "surface_raw.npz"))
    if not (
        str(data["source_sha256"])
        == digest(config["source"])
        == camera["source_sha256"]
    ):
        raise ValueError("Invalid input: prepare_sapiens_settings contract")
    p = data["vertices"]
    n = data["normals"]
    matrix = np.array(camera["camera_matrix_world"])
    local = np.einsum("ij,jk->ik", p - matrix[:3, 3], matrix[:3, :3])
    uv = np.column_stack(
        [
            (local[:, 0] / camera["ortho_scale"] + 0.5) * 1024,
            (0.5 - local[:, 1] / camera["ortho_scale"]) * 1024,
        ]
    )
    px = np.clip(np.rint(uv).astype(int), 0, 1023)
    # Semantic skin coverage; eye/pupil attraction is separately removed below.
    keep = labels[px[:, 1], px[:, 0]] == 3
    if config.get("source_has_hair"):
        from scipy.ndimage import binary_erosion

        visibility = np.load(out / "visibility.npz")
        if not (str(visibility["source_sha256"]) == digest(config["source"])):
            raise ValueError("Invalid input: prepare_sapiens_settings contract")
        skin = binary_erosion(labels == 3, iterations=3)
        keep = skin[px[:, 1], px[:, 0]] & visibility["visible"]
    forbidden = Image.new("L", (1024, 1024))
    draw = ImageDraw.Draw(forbidden)
    for group in ["left_eye", "right_eye", "lips"]:
        rows = [
            r
            for r in mapping["records"]
            if r["default_enabled"]
            and (
                ("left_eye" if r["name"].startswith("l_") else "right_eye")
                if r["region"] == "eyes"
                else "lips"
            )
            == group
        ]
        ids = [r["keypoint_id"] for r in rows if scores[0, r["keypoint_id"]] >= 0.7]
        if not (len(ids) >= 8):
            raise ValueError(f"Insufficient detection in {group}")
        pts = xy[0, ids]
        h = pts[ConvexHull(pts).vertices]
        draw.polygon([tuple(map(float, v)) for v in h], fill=255)
    # Only front-facing surfaces under the eye/lip outline are excluded, not
    # the unrelated back of the head with the same image coordinates.
    blocked = np.array(forbidden) > 0
    facing = np.einsum("ij,j->i", n, matrix[:3, 2]) > 0.15
    keep &= ~(blocked[px[:, 1], px[:, 0]] & facing)
    pp, nn = smooth_samples(p[keep], n[keep], 0.004)
    np.savez_compressed(
        out / "target.npz",
        vertices=pp,
        normals=nn,
        source_triangle_indices=data["source_triangle_indices"][keep],
        source_sha256=data["source_sha256"],
    )
    regions = json.loads((skill / "assets/taro/regions.json").read_text())
    settings = {k: regions[k] for k in ["fit_indices", "mobility"]}
    settings.update(
        template_sha256=digest(skill / "assets/taro/template.npz"),
        target_sha256=digest(out / "target.npz"),
        target_smooth_iterations=0,
        brush_stages=[
            {"sigma_edges": 12, "iterations": 30},
            {"sigma_edges": 7, "iterations": 30},
            {"sigma_edges": 4, "iterations": 25},
        ],
        landmarks=[],
        provenance={
            "source_sha256": digest(config["source"]),
            "method": "Bundled template exterior mask + source Sapiens2 segmentation and detected eye/lip exclusions; no per-person hand landmarks or regions.",
        },
    )
    (out / "masks.json").write_text(json.dumps(settings))
    project = {
        "high_glb": config["source"],
        "image": str(out / "front.png"),
        "pose": str(files["pose_data"]),
        "camera": str(out / "camera.json"),
        "target": str(out / "target.npz"),
        "settings": str(out / "masks.json"),
        "output_settings": str(out / "settings.json"),
    }
    (out / "project.json").write_text(json.dumps(project, indent=2))
    registration = {
        "target": str(out / "target.npz"),
        "settings": str(out / "settings.json"),
        "hair_state": "bald",
        "target_parts": "skin",
        "output": str(out / "fit"),
    }
    (out / "registration.json").write_text(json.dumps(registration, indent=2))
    report = {
        "source_sha256": digest(config["source"]),
        "pose_sha256": digest(files["pose_data"]),
        "image_sha256": digest(out / "front.png"),
        "raw_samples": len(p),
        "selected_samples": len(pp),
        "manual_target_landmarks": False,
        "source_specific_hand_regions": False,
    }
    (out / "input_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))
    if config.get("source_has_hair"):
        registration.update(
            hair_state="present" if source_has_hair else "bald",
            target_parts="visible_semantic_face_skin",
            source=config["source"],
            source_sha256=digest(config["source"]),
            skill=str(skill),
            visibility=str(out / "visibility.npz"),
        )
        (out / "registration.json").write_text(json.dumps(registration, indent=2))
        overlay = Image.open(out / "front.png").convert("RGB")
        pixels = np.array(overlay)
        mask = skin
        pixels[mask] = (pixels[mask] * 0.55 + np.array([30, 200, 100]) * 0.45).astype(
            np.uint8
        )
        Image.fromarray(pixels).save(out / "skin-mask.png")


if __name__ == "__main__":
    from timing import stage

    c = json.loads(Path(sys.argv[1]).read_text())
    with stage(Path(c["output"]) / "timings.jsonl", "semantic_target"):
        prepare(c)
