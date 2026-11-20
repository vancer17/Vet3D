"""Exercise the local-only reviewed view handoff."""

import hashlib
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from reviewed_submit import reviewed_handoff
from view_contract import API_ORDER, CAMERA_DIRECTIONS, CONVENTION, SCREEN_FRONT


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.manifest = self.root / "views.json"
        self.params = self.root / "quality.json"
        self.data = {"convention": CONVENTION, "views": {}}

        def chunk(name, data):
            return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data))

        for index, slot in enumerate(API_ORDER):
            raw = (
                b"\x89PNG\r\n\x1a\n"
                + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(bytes([0, index * 60, 100, 200])))
                + chunk(b"IEND", b"")
            )
            path = self.root / (slot + ".png")
            path.write_bytes(raw)
            self.data["views"][slot] = {
                "path": path.name,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "camera_position_direction": list(CAMERA_DIRECTIONS[slot]),
                "camera_up": [0, 0, 1],
                "observed_front_direction": SCREEN_FRONT[slot],
                "direction_reviewed": True,
                "direction_evidence": "Synthetic asymmetric view fixture",
            }
        self._write_manifest()
        self.params.write_text(
            json.dumps({"model": "hi3dv3.0", "resolution": "2048quality", "face": 2000000, "request_type": 3}),
            encoding="utf-8",
        )

    def _write_manifest(self):
        self.manifest.write_text(json.dumps(self.data), encoding="utf-8")

    def _handoff(self):
        return reviewed_handoff(self.manifest, self.params, self.root / "job.json", self.root / "download")

    def test_emits_runtime_tool_arguments_without_network(self):
        result = self._handoff()
        self.assertEqual(result["runtimeTool"], "hi3d_api")
        self.assertTrue(result["dryRunFirst"])
        self.assertEqual(result["arguments"]["views"], list(API_ORDER))
        self.assertFalse((self.root / "job.json").exists())

    def test_two_views_preserve_api_order(self):
        self.data["views"] = {key: self.data["views"][key] for key in ["right", "front"]}
        self._write_manifest()
        self.assertEqual(self._handoff()["arguments"]["views"], ["front", "right"])

    def test_camera_reversal_is_rejected_locally(self):
        self.data["views"]["left"]["camera_position_direction"] = [1, 0, 0]
        self._write_manifest()
        with self.assertRaises(ValueError):
            self._handoff()

    def test_changed_image_is_rejected_locally(self):
        (self.root / "left.png").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            self._handoff()


if __name__ == "__main__":
    unittest.main(verbosity=2)
