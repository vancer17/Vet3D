"""Read-only normalized NPZ heightfield input."""

def load_heightfield(path, key):
    """Read a finite normalized 2D NPZ array without pickle or source mutation."""
    import numpy as np
    with np.load(path, allow_pickle=False) as archive:
        if key not in archive:
            raise ValueError(f'Missing heightfield key: {key}')
        field = np.asarray(archive[key])
        if field.ndim != 2 or min(field.shape) < 8 or field.dtype.kind not in 'fiu':
            raise ValueError('Heightfield must be a numeric 2D array of at least 8×8')
        if not np.isfinite(field).all() or field.min() < 0 or field.max() > 1:
            raise ValueError('Heightfield must be finite and normalized in [0, 1]')
        return field.copy()
