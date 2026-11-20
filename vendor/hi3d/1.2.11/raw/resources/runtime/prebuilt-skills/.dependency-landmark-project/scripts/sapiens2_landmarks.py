"""Reuse calibrated template IDs with independently raycast target 3D points."""

import hashlib
import json
from pathlib import Path
import numpy as np


def build_landmarks(template, mapping, target_points, scores, names, min_score=0.7):
    """target_points is [308,3] in target world space; missing hits are NaN.

    The caller must use the target's own camera and visibility checks. This
    function does not interpret image xy or predicted pointmaps as world points.
    """
    data = json.loads(Path(mapping).read_text())
    if (
        hashlib.sha256(Path(template).read_bytes()).hexdigest()
        != data["template_sha256"]
    ):
        raise ValueError("Template hash mismatch; recalibrate the mapping")
    points, scores = np.asarray(target_points), np.asarray(scores)
    if points.shape != (308, 3) or scores.shape != (308,):
        raise ValueError("Expected target world points [308,3] and scores [308]")
    result = []
    for row in data["records"]:
        if not row["default_enabled"]:
            continue
        i = row["keypoint_id"]
        name = names.get(str(i), names.get(i))
        if name != row["name"]:
            raise ValueError(f"Keypoint definition mismatch at {i}")
        if (
            not np.isfinite(points[i]).all()
            or not np.isfinite(scores[i])
            or scores[i] < min_score
        ):
            continue
        result.append(
            dict(
                name=name,
                vertex_index=row["vertex_index"],
                target=points[i].tolist(),
                weight=1.0,
                group=(
                    ("left_eye" if name.startswith("l_") else "right_eye")
                    if row["region"] == "eyes"
                    else "lips"
                ),
            )
        )
    if (
        len(result) < 4
        or np.linalg.matrix_rank(
            np.asarray([x["target"] for x in result])
            - np.mean([x["target"] for x in result], axis=0)
        )
        < 2
    ):
        raise ValueError("Insufficient valid, non-collinear target landmarks")
    return result
