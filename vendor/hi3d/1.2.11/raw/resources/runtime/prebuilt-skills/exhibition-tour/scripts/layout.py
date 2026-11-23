"""Place exhibits in a unit hall. Virtual layout is not a surveyed site."""
from __future__ import annotations


def auto_layout(count):
    if not isinstance(count, int) or count < 1:
        raise ValueError('need at least one exhibit')
    spots = []
    cols = min(count, 4)
    for index in range(count):
        col = index % cols
        row = index // cols
        x = 12 + (76 * col / max(cols - 1, 1) if cols > 1 else 38)
        y = 22 + row * 28
        spots.append({'x': round(x, 2), 'y': round(min(y, 82), 2)})
    return spots
