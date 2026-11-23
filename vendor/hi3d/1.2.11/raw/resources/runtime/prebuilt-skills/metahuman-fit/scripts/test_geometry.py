"""Run in Blender: verify a tiny contact is repaired and a large crossing is retained as failure."""

import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collision import crossing_pairs
from contact_repair import repair

vertices = np.array(
    [
        [0.0, 0, 0],
        [1.0, 0, 0],
        [0.0, 1, 0],
        [0.2, 0.2, -1e-6],
        [0.4, 0.2, 1e-6],
        [0.2, 0.4, 1e-6],
    ]
)
triangles = np.array([[0, 1, 2], [3, 4, 5]])
assert len(crossing_pairs(vertices, triangles)) == 1
fixed, report = repair(vertices, triangles, set())
assert report["new_crossings"] == 0
assert (
    np.linalg.norm(fixed - vertices, axis=1).max()
    <= 1e-4 * np.ptp(vertices, axis=0).max()
)
large = vertices.copy()
large[3, 2] = -0.2
large[4:, 2] = 0.2
unchanged, failed = repair(large, triangles, set(), budget_fraction=0)
assert failed["new_crossings"] == 1
np.testing.assert_array_equal(unchanged, large)
print(
    "Contact repair: tiny correction passes; over-budget crossing remains a reported failure."
)
