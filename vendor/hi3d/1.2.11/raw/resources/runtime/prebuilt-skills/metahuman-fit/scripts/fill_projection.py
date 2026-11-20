"""Propagate observed UV colors into projection gaps without changing visible pixels."""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import cv2
import numpy as np


def fill_unobserved(color, coverage, edge_pixels=1):
    """Return inferred gap colors and the retained observation mask; no geometry edits."""
    if color.dtype != np.uint8 or color.ndim != 3 or color.shape[2] != 3:
        raise ValueError('Expected uint8 RGB/BGR color array')
    if coverage.shape != color.shape[:2] or coverage.dtype != np.uint8:
        raise ValueError('Coverage must be a same-size uint8 grayscale array')
    if type(edge_pixels) is not int or not 0 <= edge_pixels <= 8:
        raise ValueError('edge_pixels must be an integer in 0..8')
    valid = (coverage > 127).astype(np.uint8)
    if edge_pixels:
        width = 2 * edge_pixels + 1
        valid = cv2.erode(valid, np.ones((width, width), np.uint8))
    valid = valid.astype(bool)
    if not valid.any():
        raise ValueError('No reliable projected colors remain; do not invent a texture')
    _, labels = cv2.distanceTransformWithLabels(
        (~valid).astype(np.uint8), cv2.DIST_L2, 5,
        labelType=cv2.DIST_LABEL_PIXEL,
    )
    result = color[valid][labels - 1]
    result[valid] = color[valid]
    return result, valid


def run(color_path, coverage_path, output, edge_pixels=1):
    """Write a separate PNG and inference/timing report, preserving service artifacts."""
    start = time.monotonic()
    started = datetime.now(timezone.utc).isoformat()
    output = Path(output).resolve()
    report = output.with_suffix('.json')
    if output.suffix.lower() != '.png' or output.exists() or report.exists():
        raise ValueError('Choose a new PNG output and report path')
    color = cv2.imread(str(color_path), cv2.IMREAD_COLOR)
    coverage = cv2.imread(str(coverage_path), cv2.IMREAD_GRAYSCALE)
    if color is None or coverage is None:
        raise ValueError('Unable to read projection color or coverage')
    filled, valid = fill_unobserved(color, coverage, edge_pixels)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), filled):
        raise RuntimeError('Unable to save filled texture')
    data = dict(stage='projection_gap_fill', status='completed', started_at=started,
                ended_at=datetime.now(timezone.utc).isoformat(),
                seconds=time.monotonic()-start, edge_pixels=edge_pixels,
                retained_atlas_fraction=float(valid.mean()),
                method='Nearest observed UV color propagation',
                scope='Gap colors are inferred. Atlas fraction includes unused UV space; '
                      'this is not visible surface coverage. Geometry and observed colors '
                      'are unchanged. Review large unseen areas and cross-island bleeding.')
    report.write_text(json.dumps(data, indent=2))
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('color', type=Path)
    parser.add_argument('coverage', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--edge-pixels', type=int, default=1)
    args = parser.parse_args()
    print(json.dumps(run(args.color, args.coverage, args.output, args.edge_pixels)))
