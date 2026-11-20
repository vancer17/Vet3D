"""Project visible 2D semantic skin into bounded per-vertex smoothing weights."""

import numpy as np
from scipy.ndimage import distance_transform_edt


def project_weights(
    pixel_xy, visible, labels, protected, *, skin_label=3, erosion=3, feather=8
):
    """Return weights for one camera; caller supplies actual ray-tested visibility.

    protected is a same-size boolean mask covering eyes, lips, nose transplant,
    accessories and any folds to retain. No service/model inference or file I/O.
    For multiple views take max only after applying a global 3D protection mask.
    """
    xy = np.asarray(pixel_xy, float)
    visible = np.asarray(visible, bool)
    labels, protected = np.asarray(labels), np.asarray(protected, bool)
    if (
        xy.ndim != 2
        or xy.shape[1] != 2
        or not np.isfinite(xy).all()
        or visible.shape != (len(xy),)
        or labels.ndim != 2
        or protected.shape != labels.shape
        or not np.isfinite([erosion, feather]).all()
        or erosion < 0
        or feather <= 0
    ):
        raise ValueError("Invalid semantic projection inputs")
    # Padding guarantees background even if the skin touches every image border.
    distance = distance_transform_edt(np.pad((labels == skin_label) & ~protected, 1))[
        1:-1, 1:-1
    ]
    t = np.clip((distance - erosion) / feather, 0, 1)
    field = t * t * (3 - 2 * t)
    h, w = labels.shape
    valid = (
        visible & (xy[:, 0] >= 0) & (xy[:, 0] < w) & (xy[:, 1] >= 0) & (xy[:, 1] < h)
    )
    out = np.zeros(len(xy))
    px = np.floor(xy[valid]).astype(int)
    out[valid] = field[px[:, 1], px[:, 0]]
    return out
