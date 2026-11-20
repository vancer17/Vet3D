"""Local worker. Launch through workflow.py for budgets, timing and cache checks."""
import argparse
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from apply_labels import run as apply_labels
from graphcut import solve
from label_texture import sample
from timing import write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--label-mesh", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threshold", type=float, required=True)
    parser.add_argument("--confirmed-cut", action="store_true", required=True)
    parser.add_argument("--tolerance", type=float, default=1e-6)
    args = parser.parse_args()
    vertices, faces, initial, report = sample(args.label_mesh, args.threshold)
    labels, cut = solve(vertices, faces, initial)
    args.output.mkdir(parents=True, exist_ok=False)
    label_path = args.output / "labels.npy"
    np.save(label_path, labels)
    write_json(args.output / "graphcut.json", dict(report, **cut))
    apply_labels(SimpleNamespace(source=args.source, label_mesh=args.label_mesh,
        labels=label_path, output_dir=args.output / "parts", tolerance=args.tolerance))


if __name__ == "__main__":
    main()
