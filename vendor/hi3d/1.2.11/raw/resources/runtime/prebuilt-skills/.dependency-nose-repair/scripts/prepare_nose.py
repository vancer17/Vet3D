"""Prepare a source-bound nose chart from a fitted Taro anatomical prior."""

import argparse
import json
import shutil
from pathlib import Path
import numpy as np
import hashlib


def digest(path):
    with Path(path).open("rb") as stream:
        value = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def derive_profile(vertices, grid_samples=540):
    """Heuristic frontal nose ROI in GLB Y-up/+Z-front coordinates; review before cutting."""
    v = np.asarray(vertices)
    if v.shape != (24049, 3) or not np.isfinite(v).all():
        raise ValueError("Expected the bundled Taro vertex topology")
    root, tip, bottom, left, right = v[[15849, 17088, 2917, 7193, 18576]]
    height, width = root[1] - bottom[1], abs(left[0] - right[0])
    if height <= 0 or width <= 0 or not 0.2 < width / height < 2:
        raise ValueError("Invalid frontal nose orientation or proportions")
    center = [float((left[0] + right[0]) * 0.5), float(tip[1] + height * 0.04)]
    radii = [float(width * 0.85), float(height * 0.55)]
    min_z = float(min(left[2], right[2]) - height * 0.7)
    nose = dict(
        name="nose",
        center=center,
        radii=radii,
        min_z=min_z,
        band_min_z=min_z + height * 0.11,
    )
    return dict(
        nose=nose,
        eyes=[],
        transition_spacing=float(min(radii) / 90),
        heightfield=dict(
            x=[center[0] - 1.5 * radii[0], center[0] + 1.5 * radii[0], grid_samples],
            y=[center[1] - 1.5 * radii[1], center[1] + 1.5 * radii[1], grid_samples],
        ),
        validation=dict(roi_factor=1.3, min_z=min_z),
    )


def protect_lips(profile, vertices, settings, source_hash, margin_fraction=0.04):
    """Constrain the seam above source-bound lips, retaining nasal anchors."""
    provenance = settings.get("provenance", {})
    if provenance.get("source_sha256") != source_hash:
        raise ValueError("Lip landmarks belong to a different source")
    if provenance.get("camera", {}).get("coordinates") != "Blender Z-up, -Y-front; GLB(x,y,z) -> Blender(x,-z,y)":
        raise ValueError("Unsupported landmark coordinates")
    lips = np.asarray([p["target"] for p in settings.get("landmarks", []) if p.get("group") == "lips"])
    if lips.ndim != 2 or lips.shape[1] != 3 or len(lips) < 3 or not np.isfinite(lips).all():
        raise ValueError("Finite projected lip landmarks required")
    if not np.isfinite(margin_fraction) or not 0 < margin_fraction < 0.2:
        raise ValueError("Lip margin fraction must be between 0 and 0.2")
    nose = profile["nose"]
    v = np.asarray(vertices)
    margin = float((v[15849, 1] - v[2917, 1]) * margin_fraction)
    upper = float(lips[:, 2].max())
    original_rx, original_ry = nose["radii"]
    anchors = v[[17088, 2917, 7193, 18576], :2]
    # A tall template ellipse shrunk only in Y clips the alae. Move toward
    # the tip/base midpoint, then derive just enough width to retain the core.
    height = v[15849, 1] - v[2917, 1]
    lower_center = float((v[17088, 1] + v[2917, 1]) * 0.5 + height * 0.04)
    candidates = np.linspace(nose["center"][1], min(nose["center"][1], lower_center), 9)
    chosen = None
    for cy in candidates:
        ry = min(original_ry, (cy - upper - margin) / 1.13)
        if ry <= 0:
            continue
        dy = (anchors[:, 1] - cy) / (ry * 0.66)
        if np.any(abs(dy) >= 1):
            continue
        needed_rx = float(np.max(abs(anchors[:, 0] - nose["center"][0]) / (0.66 * np.sqrt(1 - dy * dy))))
        rx = max(original_rx, needed_rx * 1.02)
        if rx <= original_rx * 1.5:
            chosen = (float(cy), rx, float(ry))
            break
    if chosen is None:
        raise ValueError("Lip protection would cut the nasal core; review registration/ROI")
    cy, rx, ry = chosen
    nose["center"][1] = cy
    radii = np.array([rx, ry])
    cx = nose["center"][0]
    profile["heightfield"]["x"][:2] = [cx - 1.5 * rx, cx + 1.5 * rx]
    nose["radii"] = radii.tolist()
    profile["heightfield"]["y"][:2] = [cy - 1.5 * ry, cy + 1.5 * ry]
    profile["transition_spacing"] = float(min(radii) / 90)
    profile["lip_protection"] = dict(upper_lip_y=upper, margin=margin, seam_factor=1.13,
                                     margin_fraction=margin_fraction)
    return profile


def run(config):
    source, donor, out = (
        Path(config[k]).resolve() for k in ["source", "donor", "output"]
    )
    if out.exists():
        raise FileExistsError("Use a new nose directory")
    with np.load(donor, allow_pickle=False) as data:
        if str(data["source_sha256"]) != digest(source):
            raise ValueError("Fitted donor belongs to a different highmesh")
        template = np.load(
            Path(__file__).resolve().parents[1] / "assets/taro/template.npz"
        )
        if not np.array_equal(data["quads"], template["quads"]):
            raise ValueError("Donor topology differs from Taro")
        profile = derive_profile(data["vertices"], config.get("grid_samples", 540))
        if config.get("landmark_settings"):
            settings_path = Path(config["landmark_settings"]).resolve()
            protect_lips(profile, data["vertices"], json.loads(settings_path.read_text()),
                         digest(source), config.get("lip_margin_fraction", 0.04))
            profile["lip_protection"]["settings_sha256"] = digest(settings_path)
    profile.update(
        source=dict(path=str(source), sha256=digest(source)), donor_sha256=digest(donor)
    )
    out.mkdir(parents=True)
    (out / "fit").mkdir()
    shutil.copy2(donor, out / "fit/structural_prior.npz")
    (out / "original.glb").symlink_to(source)
    (out / "profile.json").write_text(json.dumps(profile, indent=2))
    (out / "render_original.json").write_text(json.dumps(dict(source=str(source))))
    return profile


if __name__ == "__main__":
    from timing import stage

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    with stage(Path(config["output"]).parent / "timings.jsonl", "nose_roi"):
        print(json.dumps(run(config)))
