"""Frozen template ear correspondences and orthographic target-view fusion."""

import numpy as np
from camera_ray import pixel_ray


def validate_mapping(mapping, template_hash):
    if (
        mapping.get("index_base") != 0
        or mapping.get("template_sha256") != template_hash
    ):
        raise ValueError("Ear mapping does not match this zero-based template")
    seen = set()
    for row in mapping["records"]:
        if row["id"] in seen or row["ear"] not in ("left", "right"):
            raise ValueError("Duplicate ear landmark or invalid side")
        seen.add(row["id"])
        bc = np.asarray(row["barycentric"], float)
        tri = np.asarray(row["triangle"])
        if (
            tri.shape != (3,)
            or tri.dtype.kind not in "iu"
            or (tri < 0).any()
            or bc.shape != (3,)
            or not np.isfinite(bc).all()
            or (bc < 0).any()
            or not np.isclose(bc.sum(), 1)
            or row["vertex_index"] not in tri
        ):
            raise ValueError("Invalid frozen ear correspondence")
    if not seen:
        raise ValueError("Empty ear mapping")


def orthographic_ray(camera, xy):
    """Return world-space ray; square unshifted orthographic pixels only."""
    m = np.asarray(camera["camera_matrix_world"], float)
    width, height = camera["width"], camera["height"]
    scale = camera["ortho_scale"]
    x, y = np.asarray(xy, float)
    if (
        camera.get("projection", "orthographic") != "orthographic"
        or width != height
        or width <= 0
        or not np.isfinite(scale)
        or scale <= 0
        or m.shape != (4, 4)
        or not np.isfinite(m).all()
        or not np.allclose(m[3], [0, 0, 0, 1])
        or not np.allclose(m[:3, :3].T @ m[:3, :3], np.eye(3), atol=1e-5)
        or not np.isclose(np.linalg.det(m[:3, :3]), 1, atol=1e-5)
        or camera.get("shift_x", 0) != 0
        or camera.get("shift_y", 0) != 0
        or not (0 <= x < width and 0 <= y < height)
    ):
        raise ValueError("Invalid pixel or unsupported camera")
    return pixel_ray(m, width, height, scale, [x, y])


def fuse_observations(observations, extent):
    """Fuse visible first hits; disagreement uses a fraction of source extent.

    The caller snaps the result to the source surface. A single view receives
    reduced confidence; incompatible surfaces choose the best-facing view.
    """
    if not observations or not np.isfinite(extent) or extent <= 0:
        raise ValueError("Observations and positive extent required")
    points = np.asarray([o["point"] for o in observations], float)
    if points.shape != (len(observations), 3) or not np.isfinite(points).all():
        raise ValueError("Invalid ray hits")
    weights = np.asarray(
        [
            max(0.1, o["facing"]) * (1 if o["view"] == "front" else 2)
            for o in observations
        ]
    )
    if not np.isfinite(weights).all():
        raise ValueError("Invalid facing weights")
    disagreement = float(
        np.linalg.norm(points[:, None] - points[None, :], axis=2).max()
    )
    if disagreement > 0.025 * extent:
        return (
            points[weights.argmax()],
            0.2,
            disagreement,
            "best_visible_disagreement_downweighted",
        )
    return (
        np.average(points, axis=0, weights=weights),
        1.0 if len(points) > 1 else 0.45,
        disagreement,
        "consistent_views_surface_snap",
    )
