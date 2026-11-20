"""Pure height normalization and explicit low-outlier repair profiles."""
import numpy as np


def subtract_baseline(raw, baseline):
    """Missed rays become zero; retain the input floating-point precision."""
    if not np.isfinite(baseline):
        raise ValueError("baseline must be finite")
    return np.maximum(np.nan_to_num(raw, nan=baseline) - baseline, 0)


def normalize_height(height, *, percentile=99.9, mask=None, positive_only=True):
    """Return clamped normalized array and physical scale; never infer baseline."""
    height = np.asarray(height)
    if not np.isfinite(height).all() or not 0 < percentile <= 100:
        raise ValueError("finite height and percentile in (0,100] required")
    values = height if mask is None else height[np.asarray(mask, dtype=bool)]
    values = values[values > 0] if positive_only else values.ravel()
    if not values.size:
        raise ValueError("No measured relief above source baseline")
    scale = float(np.percentile(values, percentile))
    if scale <= 0:
        raise ValueError("Source has no positive relief above backing")
    return np.clip(height / scale, 0, 1), scale


def median_filter(array, kernel=5, *, dtype=float):
    a=np.asarray(array, dtype=dtype)
    if a.ndim != 2 or kernel < 3 or kernel % 2 != 1:
        raise ValueError('A 2D field and odd kernel >=3 are required')
    h,w=a.shape; pad=np.pad(a,kernel//2,mode='edge')
    return np.median(np.stack([pad[y:y+h,x:x+w] for y in range(kernel) for x in range(kernel)]),axis=0)

def repair_pits(array, *, kernel=5, threshold=0.12, median_floor=0.2, iterations=3, dtype=float):
    """Repair only local low outliers; return field, mask and quantitative delta.

    This heuristic cannot decide artistic holes. Inspect raw/repaired/mask before
    accepting; threshold has the same units as `array` (normalized or source).
    """
    a=np.asarray(array,dtype=dtype).copy(); original=a.copy()
    if not np.isfinite(a).all() or threshold < 0 or not 0 <= iterations <= 8:
        raise ValueError('Finite field, nonnegative threshold, and 0..8 iterations required')
    for _ in range(iterations):
        med=median_filter(a,kernel,dtype=a.dtype)
        a=np.where((a < med-threshold)&(med > median_floor),med,a)
    mask=a!=original
    return a,mask,{'modified_samples':int(mask.sum()),'max_delta':float(np.max(a-original)),
        'kernel':kernel,'threshold':threshold,'median_floor':median_floor,'iterations':iterations}
