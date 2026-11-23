"""Blender worker: propose bounded corrections only for <=4 local crossings."""
import json
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from contact_repair import repair
import hashlib

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def propose(root):
    root = Path(root)
    source_hash = digest(root/"repaired.glb")
    a = np.load(root/"repaired_nose_crossings.npz")
    if str(a["mesh_sha256"]) != source_hash:
        raise ValueError("Stale crossing data")
    if not 0 < len(a["pairs"]) <= 4:
        raise ValueError("Requires review: not a small-contact case")
    v, report = repair(a["vertices"], a["faces"], set(), max_trials=1000)
    report["source_sha256"] = source_hash
    (root/"contact_report.json").write_text(json.dumps(report, indent=2))
    if report["new_crossings"]:
        raise ValueError("Bounded correction failed; result was not changed")
    ids = np.flatnonzero(np.any(v != a["vertices"], axis=1))
    np.savez(root/"contact_delta.npz", ids=ids, before=a["vertices"][ids],
             after=v[ids], global_face_indices=a["global_face_indices"], source_sha256=source_hash)


if __name__ == "__main__":
    propose(Path(sys.argv[sys.argv.index("--")+1]))
