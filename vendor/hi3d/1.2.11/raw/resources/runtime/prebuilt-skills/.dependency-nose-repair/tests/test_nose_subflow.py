"""No-network failure contracts for the nose subflow."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from nose_repair import run, check_result, apply_contact
from prepare_nose import digest, derive_profile, protect_lips

class NoseSubflow(unittest.TestCase):
    def test_lip_guard_keeps_core_and_rejects_impossible_region(self):
        v = np.zeros((24049, 3))
        v[[15849,17088,2917,7193,18576]] = [[0,.18,.25],[0,.09,.29],[0,.06,.26],[.025,.07,.24],[-.025,.07,.24]]
        settings = {"provenance":{"source_sha256":"source", "camera":{"coordinates":"Blender Z-up, -Y-front; GLB(x,y,z) -> Blender(x,-z,y)"}}, "landmarks":[{"group":"lips", "target":[x,-.2,.03]} for x in [-.03,0,.03]]}
        p = protect_lips(derive_profile(v), v, settings, "source")
        self.assertGreaterEqual(p["nose"]["center"][1]-1.13*p["nose"]["radii"][1], .03+p["lip_protection"]["margin"]-1e-10)
        with self.assertRaisesRegex(ValueError, "different source"):
            protect_lips(derive_profile(v), v, settings, "other")
        for point in settings["landmarks"]:
            point["target"][2] = .08
        with self.assertRaisesRegex(ValueError, "nasal core"):
            protect_lips(derive_profile(v), v, settings, "source")

    def test_existing_result_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            f = root/"repaired.glb"
            f.write_bytes(b"preserve me")
            with self.assertRaises(FileExistsError):
                run(root, "must-not-launch")
            self.assertEqual(f.read_bytes(), b"preserve me")

    def test_stale_contact_delta_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/"repaired.glb").write_bytes(b"current")
            np.savez(root/"contact_delta.npz", source_sha256="old")
            with self.assertRaisesRegex(ValueError, "Stale contact"):
                apply_contact(root)
            self.assertEqual((root/"repaired.glb").read_bytes(), b"current")

    def test_stale_audit_is_rejected_before_mesh_load(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root/"original.glb"
            src.write_bytes(b"original")
            (root/"repaired.glb").write_bytes(b"changed")
            (root/"profile.json").write_text(json.dumps({"source":{"path":str(src),"sha256":digest(src)}}))
            (root/"geometry_validation.json").write_text(json.dumps({"repaired_sha256":"old"}))
            with self.assertRaisesRegex(ValueError, "Stale audit"):
                check_result(root)

if __name__ == "__main__":
    unittest.main()
