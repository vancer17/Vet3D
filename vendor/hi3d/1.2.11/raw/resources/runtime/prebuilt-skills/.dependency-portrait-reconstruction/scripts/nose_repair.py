"""Run the local nose subflow from a reviewed, source-bound profile."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from timing import stage
from prepare_nose import run as prepare
from prepare_nose import digest


def check_result(root):
    """Require hash-current local audit and preserved vertices; return evidence."""
    import numpy as np
    import trimesh
    root = Path(root)
    p = json.loads((root / "profile.json").read_text())
    audit = json.loads((root / "geometry_validation.json").read_text())
    if digest(p["source"]["path"]) != p["source"]["sha256"]:
        raise ValueError("Source changed")
    if audit["repaired_sha256"] != digest(root / "repaired.glb"):
        raise ValueError("Stale audit")
    if audit["original_sha256"] != p["source"]["sha256"]:
        raise ValueError("Audit belongs to another source")
    local = audit["repaired"]["nose"]
    if not local["finite"] or any(local[k] for k in
        ["crossing_pairs", "degenerate_triangles", "boundary_edges", "nonmanifold_edges", "winding_conflicts"]):
        raise ValueError("Local nose checks failed")
    source = trimesh.load(p["source"]["path"], process=False, force="scene").to_geometry()
    mesh = trimesh.load(root / "repaired.glb", process=False, force="scene").to_geometry()
    donor = np.load(root / "fit/structural_prior.npz")
    if digest(root / "fit/structural_prior.npz") != p["donor_sha256"]:
        raise ValueError("Donor changed")
    v, q = donor["vertices"], donor["quads"]
    f = np.concatenate([q[:, [0, 1, 2]], q[:, [0, 2, 3]]])
    n = p["nose"]
    radius = np.linalg.norm((v[:, :2]-n["center"])/(np.array(n["radii"])*.75), axis=1)
    f = f[(radius[f].max(1)<1) & (v[f,2].min(1)>n["min_z"])]
    part = trimesh.Trimesh(v, f, process=False)
    components = trimesh.graph.connected_components(part.face_adjacency, nodes=np.arange(len(f)), min_len=1)
    f = f[max(components, key=len)]
    report = json.loads((root / "repair_report.json").read_text())
    removed = report["regions"][0]["removed_triangles"]
    start = len(source.faces)-removed
    error = np.linalg.norm(mesh.vertices[mesh.faces[start:start+len(f)]]-v[f], axis=2)
    exact = len(np.unique(f[error<1e-7]))
    if exact == 0 or removed <= 0:
        raise ValueError("No exact donor core / excision evidence")
    prov = np.load(root / "repair_provenance.npz")
    si, oi = prov["source_vertex_indices"], prov["output_vertex_indices"]
    adjusted = prov["adjusted_source_vertex_indices"]
    if (root / "contact_global_delta.npz").exists():
        delta = np.load(root / "contact_global_delta.npz")
        adjusted = np.union1d(adjusted, si[np.isin(oi, delta["ids"])])
    outside = ~np.isin(si, adjusted)
    change = float(np.linalg.norm(mesh.vertices[oi[outside]]-source.vertices[si[outside]], axis=1).max())
    if change > 1e-7:
        raise ValueError("Vertices outside repair changed")
    proof = dict(status="passed_local_checks", result_sha256=audit["repaired_sha256"],
                 source_sha256=p["source"]["sha256"], removed_triangles=removed,
                 donor_triangles=len(f), exact_donor_vertices=exact, tolerance=1e-7,
                 outside_change_max=change, local_checks=local, scope=audit["scope"],
                 texture="gray geometry; old UV not transferred", visual_review="required")
    (root / "transplant-proof.json").write_text(json.dumps(proof, indent=2))
    return proof



def apply_contact(root):
    """Apply a successful, hash-bound delta and retain the previous GLB."""
    import numpy as np
    import trimesh
    import shutil
    root = Path(root)
    a = np.load(root/"contact_delta.npz")
    if digest(root/"repaired.glb") != str(a["source_sha256"]):
        raise ValueError("Stale contact delta")
    mesh = trimesh.load(root/"repaired.glb", process=False, force="scene").to_geometry()
    ids = np.unique(mesh.faces[a["global_face_indices"]])[a["ids"]]
    if not np.allclose(mesh.vertices[ids], a["before"], atol=1e-7, rtol=0):
        raise ValueError("Contact vertex mapping differs")
    backup = root/"repaired_before_contact.glb"
    if backup.exists():
        raise FileExistsError(backup)
    shutil.copy2(root/"repaired.glb", backup)
    mesh.vertices[ids] = a["after"]
    scene = trimesh.Scene()
    scene.add_geometry(mesh, geom_name="repaired_skin", node_name="repaired_skin")
    scene.export(root/"repaired.glb")
    np.savez(root/"contact_global_delta.npz", ids=ids, before=a["before"], after=a["after"])


def run(root, blender, correct_contacts=False):
    """Execute one reviewed attempt, never overwrite an existing result."""
    root = Path(root).resolve()
    if (root / "repaired.glb").exists():
        raise FileExistsError("Use a new attempt directory; previous result is preserved")
    scripts = Path(__file__).resolve().parent
    records = root / "workflow-timings.jsonl"
    def call(name, command, allow_failure=False):
        try:
            with stage(records, name, task_id=str(root), parent_id="nose_repair") as row:
                with (root / (name+".log")).open("w") as log:
                    result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
                row["returncode"] = result.returncode
                if result.returncode:
                    raise subprocess.CalledProcessError(result.returncode, command)
            return 0
        except subprocess.CalledProcessError as error:
            if allow_failure:
                return error.returncode
            raise
    def b(script):
        return [blender, "--background", "--factory-startup", "--python-exit-code", "1",
                "--python", str(scripts/script), "--", str(root)]
    with stage(records, "nose_repair", task_id=str(root)):
        call("heightfield", b("nose_heightfield.py"))
        call("transplant", [sys.executable, str(scripts/"transplant_nose.py"), str(root)])
        failed = call("audit", b("audit_nose.py"), allow_failure=True)
        if failed:
            if not correct_contacts:
                raise RuntimeError("Local audit failed; inspect before adjusting the ROI")
            call("contact_correction", b("nose_contact.py"))
            with stage(records, "apply_contact", task_id=str(root)):
                apply_contact(root)
            call("audit_after_contact", b("audit_nose.py"))
        else:
            with stage(records, "contact_correction", task_id=str(root)) as row:
                row["outcome"] = "skipped"
                row["reason"] = "audit already passed"
        with stage(records, "source_and_donor_verification", task_id=str(root)):
            return check_result(root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    prep = subs.add_parser("prepare")
    prep.add_argument("config", type=Path)
    go = subs.add_parser("run")
    go.add_argument("output", type=Path)
    go.add_argument("--blender", required=True)
    go.add_argument("--correct-small-contacts", action="store_true")
    check = subs.add_parser("verify")
    check.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        config = json.loads(args.config.read_text())
        with stage(Path(config["output"]).parent/"timings.jsonl", "nose_profile"):
            result = prepare(config)
    elif args.command == "verify":
        result = check_result(args.output)
    else:
        result = run(args.output, args.blender, args.correct_small_contacts)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
