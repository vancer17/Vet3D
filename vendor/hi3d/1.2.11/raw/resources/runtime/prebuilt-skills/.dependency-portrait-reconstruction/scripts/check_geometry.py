"""Compare neutral triangle crossings against the exact aligned source template."""

import json
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from geometry_compare import compare_geometry
from registered_geometry import repair_registered_geometry
from mesh_io import write_obj


def check(path, output, registered=None):
    data = dict(np.load(path, allow_pickle=False))
    q = data["quads"]
    correction = None
    if registered:
        data["vertices"], data["native_vertices"], correction = repair_registered_geometry(
            data["rest"], data["vertices"], q, data["linear"], data["offset"]
        )
        np.savez_compressed(registered, **data)
        write_obj(
            Path(registered).parent / "MetaHuman_Registered.obj",
            data["native_vertices"],
            q,
            data["quad_uvs"],
        )
    report = dict(
        **compare_geometry(data["rest"], data["vertices"], q),
        correction=correction,
        scope="Neutral head only, fixed quad triangulation. Excludes coplanar, tangent and shared-vertex contacts; no eyelid closure or accessory clearance claim.",
    )
    Path(output).write_text(json.dumps(report, indent=2))
    print(json.dumps(report))
    return report


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1 :]
    check(*args)
