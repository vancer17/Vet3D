"""Blender adapter for checked ear arrays and a topology-preserving OBJ."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from ear_guard import guard_ears
from registered_geometry import native_coordinates
from mesh_io import write_obj


def run(config):
    root = Path(config["output"])
    original = dict(np.load(config["registered"], allow_pickle=False))
    baseline = (
        np.load(config["face_fit"], allow_pickle=False)["vertices"]
        if config.get("face_fit")
        else original["vertices"]
    )
    candidate = dict(np.load(root / "candidate.npz", allow_pickle=False))
    initial = np.load(root / "initial.npz", allow_pickle=False)["vertices"]
    regions = json.loads(Path(config["regions"]).read_text())
    settings = json.loads(Path(config["settings"]).read_text())
    if any(
        not np.array_equal(candidate[k], original[k]) for k in ("quads", "quad_uvs")
    ):
        raise ValueError("Candidate topology/UV changed")
    vertices, report = guard_ears(
        original["rest"],
        baseline,
        initial,
        candidate["vertices"],
        original["quads"],
        sum(
            [r["core_indices"] + r["blend_indices"] for r in regions["ear_regions"]], []
        ),
        [r["vertex_index"] for r in settings["landmarks"]],
    )
    report["topology_uv_identical"] = True
    result = dict(
        original,
        vertices=vertices,
        native_vertices=native_coordinates(
            vertices, original["linear"], original["offset"]
        ),
    )
    np.savez_compressed(root / "checked.npz", **result)
    write_obj(
        root / "MetaHuman_Ears.obj", vertices, original["quads"], original["quad_uvs"]
    )
    (root / "geometry.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    run(json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text()))
