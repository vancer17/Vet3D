"""Offline numerical and CLI regressions; no Blender or account needed."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import numpy as np
from .weight_graph import mesh_digest, solve_weights, calibration_digest


def fixture():
    v = np.array([(x, y, 0) for x in np.linspace(0, 1, 101) for y in [0, 0.02]])
    f = np.array(
        [
            face
            for i in range(100)
            for face in [
                (2 * i, 2 * i + 1, 2 * i + 2),
                (2 * i + 1, 2 * i + 3, 2 * i + 2),
            ]
        ]
    )
    initial = np.zeros((len(v), 2))
    initial[:, 0] = v[:, 0] < 0.5
    initial[:, 1] = 1 - initial[:, 0]
    return v, f, initial


class Tests(unittest.TestCase):
    def test_cg_matches_direct_and_preserves_anchors(self):
        args = (*fixture(), 0.10, 0.05, 1e-6)
        direct, fixed = solve_weights(*args)
        report = {}
        cg, anchors = solve_weights(*args, method="cg", rtol=1e-9, diagnostics=report)
        self.assertTrue(np.array_equal(fixed, anchors))
        self.assertTrue(np.array_equal(cg[fixed], args[2][fixed]))
        self.assertTrue(np.allclose(cg, direct, atol=1e-7, rtol=0))
        self.assertTrue(np.all(cg >= 0))
        self.assertTrue(np.allclose(cg.sum(1), 1))
        self.assertLess(np.max(abs(np.diff(cg[::2, 0]))), 0.5)
        self.assertTrue(
            all(
                c["info"] == 0 and c["relative_residual"] < 1e-8
                for c in report["columns"]
            )
        )

    def test_unconverged_solve_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "did not converge"):
            solve_weights(
                *fixture(), 0.45, 0.3, 1e-6, method="cg", rtol=1e-12, maxiter=1
            )

    def test_invalid_weights_and_faces_are_rejected(self):
        v, f, initial = fixture()
        bad = initial.copy()
        bad[0, 0] = np.nan
        with self.assertRaises(ValueError):
            solve_weights(v, f, bad, 0.1, 0.05, 1e-6)
        f[0, 0] = len(v)
        with self.assertRaises(ValueError):
            solve_weights(v, f, initial, 0.1, 0.05, 1e-6)

    def test_isolated_anchor_and_calibration_fingerprint(self):
        v, f, initial = fixture()
        v = np.vstack([v, [5, 0, 0]])
        initial = np.vstack([initial, [1, 0]])
        weights, fixed = solve_weights(v, f, initial, 0.1, 0.05, 1e-6)
        self.assertTrue(fixed[-1])
        self.assertTrue(np.array_equal(weights[-1], [1, 0]))
        p = dict(bones=[], default_bone="root", weight_regions=[])
        self.assertNotEqual(calibration_digest(p, 1), calibration_digest(p, 2))
        self.assertEqual(
            calibration_digest(p, 1), calibration_digest(dict(p, animations=[]), 1)
        )

    def test_cli_success_failure_and_fingerprints(self):
        v, f, initial = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "input.npz"
            output = root / "weights.npz"

            def save(fingerprint):
                np.savez(
                    source,
                    vertices=v,
                    faces=f,
                    initial=initial,
                    bone_names=np.array(["A", "B"]),
                    mesh_sha256=fingerprint,
                    calibration_sha256="synthetic-calibration",
                )

            save(mesh_digest(v, f))
            cmd = [
                sys.executable,
                str(Path(__file__).resolve().parents[1] / "run.py"),
                "weight_graph",
                "--input",
                str(source),
                "--output",
                str(output),
                "--radius",
                ".1",
                "--fidelity-length",
                ".05",
                "--edge-floor",
                "1e-6",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            with np.load(output, allow_pickle=False) as data:
                self.assertEqual(str(data["mesh_sha256"]), mesh_digest(v, f))
                self.assertEqual(
                    str(data["calibration_sha256"]), "synthetic-calibration"
                )
            self.assertTrue(
                json.loads(output.with_suffix(".solver.json").read_text())["passed"]
            )
            self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)
            output.unlink()
            output.with_suffix(".solver.json").unlink()
            result = subprocess.run(
                cmd + ["--maxiter", "1", "--rtol", "1e-12"], capture_output=True
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())
            self.assertFalse(
                json.loads(output.with_suffix(".solver.json").read_text())["passed"]
            )
            output.with_suffix(".solver.json").unlink()
            save("stale")
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertIn("fingerprint mismatch", result.stderr)
            self.assertFalse(output.exists())


def main(argv=None):
    unittest.main(module=__name__, argv=[__file__, *(argv or [])])


if __name__ == "__main__":
    main()
