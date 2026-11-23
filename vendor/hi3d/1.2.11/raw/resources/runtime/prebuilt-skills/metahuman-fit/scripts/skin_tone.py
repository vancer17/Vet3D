"""Match a supplied template skin tone, then Poisson-blend baked GLB color into it."""

import json
import sys
import time
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw


def template_color_mask(data, indices, size):
    """Rasterize explicitly annotated oral/other template-only faces in their native UVs."""
    mask = np.zeros(len(data["vertices"]), bool)
    mask[indices] = True
    faces = mask[data["quads"]].sum(1) >= 3
    image = Image.new("L", size, 0)
    draw = ImageDraw.Draw(image)
    for uv in data["quad_uvs"][faces]:
        draw.polygon(
            [(float(u * size[0]), float((1 - v) * size[1])) for u, v in uv], fill=255
        )
    return np.asarray(image)


def rgb_image(path, size):
    return np.asarray(
        Image.open(path).convert("RGB").resize(size, Image.Resampling.LANCZOS)
    )


def match_tone(template, source, mask):
    """Robust Lab offset; preserves template variations without inventing native Creator U/V values."""
    a = cv2.cvtColor(template.astype(np.float32) / 255, cv2.COLOR_RGB2Lab)
    b = cv2.cvtColor(source.astype(np.float32) / 255, cv2.COLOR_RGB2Lab)
    valid = mask > 0
    if valid.sum() < 100:
        raise ValueError("Too few observed skin pixels to estimate tone")
    lo, hi = np.percentile(b[:, :, 0][valid], [30, 80])
    sample = valid & (b[:, :, 0] >= lo) & (b[:, :, 0] <= hi)
    median_source = np.median(b[sample], axis=0)
    median_template = np.median(a[sample], axis=0)
    offset = median_source - median_template
    adjusted = a + offset
    rgb = np.clip(cv2.cvtColor(adjusted, cv2.COLOR_Lab2RGB) * 255, 0, 255).astype(
        np.uint8
    )
    tone = cv2.cvtColor(median_source.reshape(1, 1, 3), cv2.COLOR_Lab2RGB)[0, 0]
    return rgb, dict(
        mode="robust_template_Lab_offset",
        lab_offset=offset.tolist(),
        skin_tone_rgb=tone.tolist(),
        sample_pixels=int(sample.sum()),
        native_creator_uv=None,
        note="Texture-space tone parameterization; native MetaHuman Creator Skin Tone U/V was not invoked",
    )


def poisson_blend(source, template, mask):
    """Aligned UV images; pad/crop explicitly so OpenCV does not shift the masked region."""
    pad = 24
    src = cv2.copyMakeBorder(source, pad, pad, pad, pad, cv2.BORDER_REFLECT)
    dst = cv2.copyMakeBorder(template, pad, pad, pad, pad, cv2.BORDER_REFLECT)
    m = cv2.copyMakeBorder(mask, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0)
    x, y, w, h = cv2.boundingRect(m)
    if w < 3 or h < 3:
        raise ValueError("Empty Poisson domain")
    x -= 2
    y -= 2
    w += 4
    h += 4
    patch = np.ascontiguousarray(src[y : y + h, x : x + w, ::-1])
    pm = np.ascontiguousarray(m[y : y + h, x : x + w])
    result = cv2.seamlessClone(
        patch,
        np.ascontiguousarray(dst[:, :, ::-1]),
        pm,
        (x + w // 2, y + h // 2),
        cv2.NORMAL_CLONE,
    )
    return result[pad:-pad, pad:-pad, ::-1].copy()


def multiscale_poisson(source, template, mask, resolution=512):
    size = max(source.shape[:2])
    if size <= resolution:
        return poisson_blend(source, template, mask)
    ratio = resolution / size
    small_size = (round(source.shape[1] * ratio), round(source.shape[0] * ratio))
    a = cv2.resize(source, small_size, interpolation=cv2.INTER_AREA)
    b = cv2.resize(template, small_size, interpolation=cv2.INTER_AREA)
    m = cv2.resize(mask, small_size, interpolation=cv2.INTER_NEAREST)
    coarse = poisson_blend(a, b, m)
    correction = cv2.resize(
        coarse.astype(np.float32) - a.astype(np.float32),
        (source.shape[1], source.shape[0]),
        interpolation=cv2.INTER_LINEAR,
    )
    alpha = np.clip(cv2.distanceTransform(mask, cv2.DIST_L2, 5) / (4 / ratio), 0, 1)[
        :, :, None
    ]
    return np.clip(
        (source.astype(np.float32) + correction) * alpha + template * (1 - alpha),
        0,
        255,
    ).astype(np.uint8)


def run(config):
    start = time.monotonic()
    root = Path(config["output"])
    tex = root / "textures"
    source = np.asarray(Image.open(tex / "MetaHuman_Albedo.png").convert("RGB"))
    template = rgb_image(config["template_albedo"], (source.shape[1], source.shape[0]))
    coverage = np.asarray(Image.open(tex / "MetaHuman_Coverage.png").convert("L"))
    mask = ((coverage > 250) * 255).astype(np.uint8)
    settings = json.loads(Path(config["settings"]).read_text())
    preserve = template_color_mask(
        np.load(root / "registered.npz", allow_pickle=False),
        settings.get("bake_template_color_indices", []),
        (source.shape[1], source.shape[0]),
    )
    mask[preserve > 0] = 0
    # Keep the invalid ray fringe outside the Poisson domain.
    mask = cv2.erode(mask, np.ones((3, 3), np.uint8), iterations=2)
    toned, report = match_tone(template, source, mask)
    fused = multiscale_poisson(
        source, toned, mask, config.get("poisson_resolution", 512)
    )
    # Oral mucosa must not inherit the skin Lab offset or source closed-mouth projection.
    alpha_preserve = np.clip(cv2.distanceTransform(preserve, cv2.DIST_L2, 5) / 3, 0, 1)[
        :, :, None
    ]
    toned = np.rint(toned * (1 - alpha_preserve) + template * alpha_preserve).astype(
        np.uint8
    )
    fused = np.rint(fused * (1 - alpha_preserve) + template * alpha_preserve).astype(
        np.uint8
    )
    Image.fromarray(toned).save(tex / "MetaHuman_Template_Toned.png")
    Image.fromarray(fused).save(tex / "MetaHuman_Albedo_Fused.png")
    normal = cv2.imread(str(tex / "MetaHuman_Normal.png"), cv2.IMREAD_UNCHANGED)
    if normal is None or normal.dtype != np.uint16:
        raise ValueError("Expected 16-bit source normal map")
    # Smooth normals independently; color Poisson gradients must never be applied to XYZ normals.
    distance = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    alpha = np.clip(distance / config.get("normal_feather_pixels", 24), 0, 1)
    xyz = normal[:, :, ::-1].astype(np.float64) / 65535 * 2 - 1
    mixed = xyz * alpha[:, :, None] + np.array([0.0, 0.0, 1.0]) * (
        1 - alpha[:, :, None]
    )
    mixed /= np.maximum(np.linalg.norm(mixed, axis=2, keepdims=True), 1e-12)
    encoded = np.rint((mixed + 1) * 0.5 * 65535).clip(0, 65535).astype(np.uint16)
    cv2.imwrite(str(tex / "MetaHuman_Normal_Fused.png"), encoded[:, :, ::-1])
    band = (cv2.dilate(mask, np.ones((3, 3), np.uint8)) > 0) & (
        cv2.erode(mask, np.ones((3, 3), np.uint8)) == 0
    )

    def gradient(im):
        f = im.astype(float)
        g = np.sqrt(
            np.sum(np.gradient(f, axis=0) ** 2 + np.gradient(f, axis=1) ** 2, axis=2)
        )
        return float(np.mean(g[band]))

    hard = np.where((mask > 0)[:, :, None], source, toned)
    report.update(
        seconds=time.monotonic() - start,
        coverage_fraction=float(np.mean(mask > 0)),
        method="Multiscale Poisson: coarse NORMAL_CLONE correction, full-resolution source detail and a narrow boundary transition",
        poisson_resolution=config.get("poisson_resolution", 512),
        boundary_gradient_hard=gradient(hard),
        boundary_gradient_fused=gradient(fused),
        normal_policy="Renormalized tangent vectors fading to flat template normals at the observed boundary",
        preserved_template_color_pixels=int(np.count_nonzero(preserve)),
    )
    (root / "skin_tone_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == "__main__":
    run(json.loads(Path(sys.argv[1]).read_text()))
