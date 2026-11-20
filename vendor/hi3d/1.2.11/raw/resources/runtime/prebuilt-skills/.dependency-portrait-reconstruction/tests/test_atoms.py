"""Offline behavior tests; no model service or credentials."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from brush import fit_brush, similarity
from denoise_semantic_face import denoise, run, digest
from semantic_weights import project_weights
from nose_operators import poisson_reference, loops, triangulate_annulus
from timing import stage
from sapiens2_landmarks import build_landmarks


def grid(n=17):
    x, z = np.meshgrid(np.linspace(-1, 1, n), np.linspace(-1, 1, n))
    v = np.c_[x.ravel(), np.zeros(n * n), z.ravel()]
    i = np.arange(n * n).reshape(n, n)[:-1, :-1].ravel()
    q = np.c_[i, i + 1, i + n + 1, i + n]
    f = np.concatenate([q[:, [0, 1, 2]], q[:, [0, 2, 3]]])
    return v, q, f


class Atoms(unittest.TestCase):
    def test_denoise_fixed_mask_cap_and_noise(self):
        v, q, f = grid()
        weight = ((abs(v[:, 0]) < 0.8) & (abs(v[:, 2]) < 0.8)).astype(float)
        v[:, 1] = np.random.default_rng(4).normal(0, 0.018, len(v)) * weight
        original = v.copy()
        result, metrics = denoise(v, f, weight, max_displacement=0.04)
        np.testing.assert_array_equal(v, original)
        np.testing.assert_array_equal(result[weight == 0], v[weight == 0])
        self.assertLess(np.std(result[:, 1]), np.std(v[:, 1]))
        self.assertLessEqual(metrics["displacement_max"], 0.04000001)
        self.assertGreaterEqual(metrics["minimum_signed_area_ratio"], 0.25)

    def test_noop(self):
        v, _, f = grid()
        for weights, iterations in [(np.zeros(len(v)), 80), (np.ones(len(v)), 0)]:
            r, _ = denoise(v, f, weights, iterations=iterations, max_displacement=0.1)
            np.testing.assert_array_equal(r, v)

    def test_bad_weights(self):
        v, _, f = grid()
        for w in [np.full(len(v), np.nan), np.full(len(v), -1), np.ones(len(v) - 1)]:
            with self.assertRaises(ValueError):
                denoise(v, f, w, max_displacement=0.1)

    def test_mask_source_mismatch_and_output_protection(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            v, _, f = grid()
            trimesh.Trimesh(v, f, process=False).export(root / "input.glb")
            np.savez(root / "mask.npz", weights=np.ones(len(v)), source_sha256="wrong")
            config = dict(
                source=str(root / "input.glb"),
                source_sha256=digest(root / "input.glb"),
                mask=str(root / "mask.npz"),
                output=str(root / "result.glb"),
                max_displacement=0.01,
            )
            with self.assertRaises(ValueError):
                run(config)
            self.assertFalse((root / "result.glb").exists())
            np.savez(
                root / "mask.npz",
                weights=np.zeros(len(v)),
                source_sha256=config["source_sha256"],
            )
            report = run(config)
            self.assertEqual(report["affected_vertices"], 0)
            with self.assertRaises(FileExistsError):
                run(config)

    def test_semantic_occlusion_and_protection(self):
        labels = np.full((32, 32), 3)
        protected = np.zeros_like(labels, bool)
        protected[10:14, 10:14] = True
        xy = [[20, 20], [11, 11], [20, 20], [-1, 5], [0, 0]]
        w = project_weights(xy, [True, True, False, True, True], labels, protected)
        self.assertGreater(w[0], 0)
        np.testing.assert_array_equal(w[1:], 0)

    def test_similarity_and_fit(self):
        v, q, _ = grid(9)
        target = v.copy()
        target[:, 1] = -0.05 * np.exp(-3 * (v[:, 0] ** 2 + v[:, 2] ** 2))
        anchors = [
            dict(vertex_index=i, target=target[i].tolist(), weight=1)
            for i in [0, 8, 72, 80]
        ]
        settings = dict(
            landmarks=anchors,
            fit_indices=list(range(len(v))),
            brush_stages=[dict(sigma_edges=2, iterations=8)],
            target_smooth_iterations=0,
        )
        fitted, *_ = fit_brush(v, q, target, q, settings)
        self.assertLess(np.mean((fitted - target) ** 2), np.mean((v - target) ** 2))
        linear, offset = similarity(v, v * 2 + [1, 2, 3])
        np.testing.assert_allclose(v @ linear.T + offset, v * 2 + [1, 2, 3], atol=1e-12)

    def test_poisson_preserves_boundary(self):
        v, _, f = grid(9)
        v = v[:, [0, 2, 1]]
        ids = np.flatnonzero((abs(v[:, 0]) < 0.99) & (abs(v[:, 1]) < 0.99))
        v[:, 2] = v[:, 0] * 0.2 + v[:, 1] * 0.1
        expected = v.copy()
        v[ids, 2] += 0.05
        fixed = np.setdiff1d(np.arange(len(v)), ids)
        before = v.copy()
        poisson_reference(v, f, ids, lambda p: p[:, 0] * 0.2 + p[:, 1] * 0.1)
        np.testing.assert_allclose(v, expected, atol=1e-12)
        np.testing.assert_array_equal(v[fixed], before[fixed])

    def test_annulus_preserves_borders(self):
        angle = np.arange(16) * 2 * np.pi / 16
        ring = np.c_[np.cos(angle), np.sin(angle), np.zeros(16)]
        v = np.vstack([ring, ring * 0.5])
        f = triangulate_annulus(
            v, np.arange(16), np.arange(16, 32), np.array([], int), [0, 0]
        )
        self.assertEqual(sorted(map(len, loops(f))), [16, 16])

    def test_mapping_hash_guard(self):
        mapping = ROOT / "assets/taro/sapiens2_mapping.json"
        names = json.loads(
            (ROOT / "assets/taro/sapiens2_keypoint_names.json").read_text()
        )
        with tempfile.TemporaryDirectory() as folder:
            bad = Path(folder) / "template.npz"
            bad.write_bytes(b"not the correct template")
            with self.assertRaises(ValueError):
                build_landmarks(bad, mapping, np.zeros((308, 3)), np.ones(308), names)

    def test_timing_failure_append(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "timings.jsonl"
            with stage(path, "ok"):
                pass
            with self.assertRaises(ValueError):
                with stage(path, "fail"):
                    raise ValueError("never log this raw message")
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual([r["status"] for r in rows], ["succeeded", "failed"])
            self.assertTrue(
                all(r["seconds"] >= 0 and "+00:00" in r["start"] for r in rows)
            )
            self.assertNotIn("never log", path.read_text())

    def test_packaged_asset_hashes(self):
        root = ROOT / "assets/taro"
        manifest = json.loads((root / "manifest.json").read_text())
        for name, info in manifest["files"].items():
            self.assertEqual(
                hashlib.sha256((root / name).read_bytes()).hexdigest(), info["sha256"]
            )


if __name__ == "__main__":
    unittest.main()
