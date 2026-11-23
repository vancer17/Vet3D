"""Parameterize a matching template eye atlas without changing the sclera or eye mesh."""

import json, sys, time
from pathlib import Path
import numpy as np
import cv2
from PIL import Image


def adjust_eye(
    image,
    center_uv,
    iris_radius,
    pupil_radius,
    pupil_scale=1.0,
    iris_color_rgb=None,
    pupil_color_rgb=None,
):
    if not (0 < pupil_radius < iris_radius < 0.5) or not (0.3 <= pupil_scale <= 2.5):
        raise ValueError("Invalid iris/pupil radius or scale")
    radius = pupil_radius * pupil_scale
    if radius >= iris_radius * 0.85:
        raise ValueError("Pupil must leave a visible iris annulus")
    center = np.asarray(center_uv, float)
    if (
        center.shape != (2,)
        or not np.isfinite(center).all()
        or (center <= iris_radius).any()
        or (center >= 1 - iris_radius).any()
    ):
        raise ValueError("Eye iris must fit inside the declared UV atlas")
    for color in [iris_color_rgb, pupil_color_rgb]:
        if color is not None and (
            np.asarray(color).shape != (3,)
            or not np.isfinite(color).all()
            or np.min(color) < 0
            or np.max(color) > 1
        ):
            raise ValueError("Eye colors must be finite sRGB triplets in [0,1]")
    h, w = image.shape[:2]
    yy, xx = np.mgrid[:h, :w].astype(np.float32)
    dx = (xx + 0.5) / w - center[0]
    dy = (yy + 0.5) / h - (1 - center[1])
    r = np.sqrt(dx * dx + dy * dy)
    source_r = np.where(
        r <= radius,
        r * pupil_radius / radius,
        pupil_radius
        + (r - radius) * (iris_radius - pupil_radius) / (iris_radius - radius),
    )
    ratio = np.where(r < iris_radius, source_r / np.maximum(r, 1e-12), 1)
    warped = cv2.remap(
        image,
        ((center[0] + dx * ratio) * w - 0.5).astype(np.float32),
        (((1 - center[1]) + dy * ratio) * h - 0.5).astype(np.float32),
        cv2.INTER_LINEAR,
    ).astype(float)
    feather = max(2 / min(h, w), 0.006 * iris_radius)
    if iris_color_rgb is not None:
        lum = warped @ np.array([0.2126, 0.7152, 0.0722])
        annulus = (r > radius + feather) & (r < iris_radius - feather)
        if annulus.sum() < 20:
            raise ValueError("Insufficient iris pixels")
        detail = lum / max(float(np.median(lum[annulus])), 1)
        tinted = np.asarray(iris_color_rgb) * 255 * detail[:, :, None]
        alpha = (
            np.clip((r - radius) / feather, 0, 1)
            * np.clip((iris_radius - r) / (feather * 3), 0, 1)
        )[:, :, None]
        warped = warped * (1 - alpha) + tinted * alpha
    if pupil_color_rgb is not None:
        alpha = np.clip((radius - r) / feather, 0, 1)[:, :, None]
        warped = warped * (1 - alpha) + np.asarray(pupil_color_rgb) * 255 * alpha
    result = np.clip(np.rint(warped), 0, 255).astype(np.uint8)
    result[r >= iris_radius] = image[r >= iris_radius]
    return result


def run(config):
    start = time.monotonic()
    root = Path(config["output"])
    image = np.asarray(Image.open(config["template_eye_albedo"]).convert("RGB"))
    parameters = config.get("eye_parameters", {})
    result = adjust_eye(image, **parameters) if parameters else image
    path = root / "textures/MetaHuman_Eyes.png"
    path.parent.mkdir(exist_ok=True)
    Image.fromarray(result).save(path)
    report = dict(
        seconds=time.monotonic() - start,
        parameters=parameters,
        scope="Template eye UV/color only; iris texture modulation and radial pupil warp, no eyeball deformation",
    )
    (root / "eye_report.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    run(json.loads(Path(sys.argv[1]).read_text()))
