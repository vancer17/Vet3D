#!/usr/bin/env python3
"""Fit mm/model-unit scale from corresponding straight landmark distances."""
import argparse
import json
import math
from pathlib import Path


def positive(value, label):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{label} must be numeric")
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be finite and positive")
    return value


def calibrate(data):
    """Pure weighted scale fit; reject invalid/arc measurements with ValueError."""
    if not isinstance(data, dict):
        raise ValueError("Input must be a JSON object")
    rows = data.get("measurements", [])
    if not isinstance(rows, list) or not rows:
        raise ValueError("At least one measured landmark distance is required")
    clean = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each measurement must be a JSON object")
        name = row.get("name")
        if not isinstance(name, str) or not name.strip() or name in seen:
            raise ValueError("Each measurement needs a unique nonempty name")
        seen.add(name)
        if row.get("kind") != "straight":
            raise ValueError(f"{name}: only corresponding straight distances are accepted; exclude head circumference")
        d = positive(row.get("model_distance"), name + ".model_distance")
        m = positive(row.get("measured_mm"), name + ".measured_mm")
        sigma = positive(row.get("uncertainty_mm"), name + ".uncertainty_mm")
        clean.append((name, d, m, sigma))
    scale = sum(d*m/(s*s) for _, d, m, s in clean) / sum(d*d/(s*s) for _, d, m, s in clean)
    result = []
    for name, d, m, sigma in clean:
        residual = scale*d - m
        threshold = max(2.0, 2*sigma)
        result.append({"name": name, "predicted_mm": scale*d, "measured_mm": m,
                       "residual_mm": residual, "review_threshold_mm": threshold,
                       "within_project_review_threshold": abs(residual) <= threshold})
    status = "single_dimension_only" if len(clean) == 1 else (
        "landmark_scale_consistent" if all(r["within_project_review_threshold"] for r in result) else "review_required")
    return {"status": status, "scale_mm_per_model_unit": scale, "landmarks": result,
            "rms_residual_mm": math.sqrt(sum(r["residual_mm"]**2 for r in result)/len(result)),
            "method": "weighted least squares, weights 1/uncertainty_mm^2, no shape deformation",
            "limits": "Sparse landmark consistency only. Model landmark error is not estimated. This is not full-face fit or comfort validation.",
            "personal_wear_test": "not_tested"}


def calibrate_file(source, destination):
    """Read measurements and write a new report without replacing prior files."""
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve() or destination.exists():
        raise FileExistsError("Choose a new report path; preserve input and previous reports")
    report = calibrate(json.loads(source.read_text(encoding="utf-8")))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = calibrate_file(args.input, args.out)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.error(str(exc))
    print(json.dumps({"status": report["status"], "report": str(args.out)}, ensure_ascii=False))
    return 2 if report["status"] == "review_required" else 0


if __name__ == "__main__":
    raise SystemExit(main())
