"""Camera-space square orthographic pixel to world-space ray."""

import numpy as np


def pixel_ray(matrix, width, height, scale, xy):
    """Caller validates camera convention and pixel visibility before tracing."""
    m = np.asarray(matrix, float)
    x, y = xy
    local = [(x / width - 0.5) * scale, (0.5 - y / height) * scale, 0]
    direction = -m[:3, 2]
    norm = np.linalg.norm(direction)
    if not np.isfinite(norm) or norm <= 0:
        raise ValueError("Invalid camera direction")
    return m[:3, :3] @ local + m[:3, 3], direction / norm
