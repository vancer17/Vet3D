"""Distances for fitted prior; not a whole-head quality score."""

import numpy as np
from scipy.spatial import cKDTree


def distance_stats(d):
    return dict(
        rms=float(np.sqrt(np.mean(d * d))),
        p95=float(np.percentile(d, 95)),
        max=float(d.max()),
        count=len(d),
    )


def metrics(v, rest, smooth, settings, mask):
    if not len(mask):
        raise ValueError("No observed skin remains outside the template prior")
    a = settings["landmarks"]
    ids = [x["vertex_index"] for x in a]
    goals = np.array([x["target"] for x in a])
    tree = cKDTree(smooth)
    return dict(
        initial=distance_stats(tree.query(rest[mask])[0]),
        registered=distance_stats(tree.query(v[mask])[0]),
        landmark=distance_stats(np.linalg.norm(v[ids] - goals, axis=1)),
    )
