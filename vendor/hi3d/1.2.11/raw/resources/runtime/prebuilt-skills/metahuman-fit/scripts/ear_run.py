"""Resume local ear registration from bound target evidence; no service submissions."""

import argparse
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
from checkpoints import digest
from content_journal import Journal
from process_run import run_process
from ear_projection import validate_mapping
from ear_fit import initialize, deform

SCRIPTS = Path(__file__).resolve().parent
ASSETS = SCRIPTS.parent / "assets" / "taro"


def signature(values, files):
    return hashlib.sha256(
        json.dumps(
            [values, {str(p): digest(p) for p in files}], sort_keys=True
        ).encode()
    ).hexdigest()


def resolve(config):
    c = dict(config)
    for key, name in [
        ("template", "template.npz"),
        ("regions", "regions.json"),
        ("mapping", "sapiens2_ear_mapping.json"),
    ]:
        c.setdefault(key, str(ASSETS / name))
    for key in (
        "output",
        "registered",
        "face_fit",
        "source",
        "surface",
        "template",
        "mapping",
        "regions",
        "settings",
        "landmarks",
    ):
        if c.get(key):
            c[key] = str(Path(c[key]).resolve())
    c["views"] = [
        dict(
            v,
            **{
                k: str(Path(v[k]).resolve())
                for k in ("camera", "image", "pose", "binding")
            }
        )
        for v in c.get("views", [])
    ]
    if bool(c.get("landmarks")) == bool(c["views"]):
        raise ValueError("Provide either fused landmarks or bound target views")
    return c


def inputs(config, landmark_path):
    mapping = json.loads(Path(config["mapping"]).read_text())
    validate_mapping(mapping, digest(config["template"]))
    template = dict(np.load(config["template"], allow_pickle=False))
    original = dict(np.load(config["registered"], allow_pickle=False))
    face = (
        np.load(config["face_fit"], allow_pickle=False)["vertices"].copy()
        if config.get("face_fit")
        else original["vertices"].copy()
    )
    if any(not np.array_equal(original[k], template[k]) for k in ("quads", "quad_uvs")):
        raise ValueError("Registered topology/UV differs from bound template")
    settings = json.loads(Path(config["settings"]).read_text())
    if settings.get("template_sha256") != digest(config["template"]):
        raise ValueError("Settings belong to another template")
    protected = [r["vertex_index"] for r in settings["landmarks"]]
    if (
        len(protected) < 4
        or face.shape != original["vertices"].shape
        or not np.array_equal(face[protected], original["vertices"][protected])
    ):
        raise ValueError("Face fit must retain original eye/lip anchors")
    surface = dict(np.load(config["surface"], allow_pickle=False))
    source_hash = digest(config["source"])
    if settings.get("provenance", {}).get("source_sha256") != source_hash:
        raise ValueError("Face landmark settings belong to another source")
    if str(surface.get("source_sha256", "")) != source_hash:
        raise ValueError("Surface samples belong to another source")
    landmarks = json.loads(Path(landmark_path).read_text())
    if landmarks.get("source_sha256") != source_hash or landmarks.get(
        "mapping_sha256"
    ) != digest(config["mapping"]):
        raise ValueError("Ear records belong to another source or mapping")
    fixed = {r["id"]: r for r in mapping["records"]}
    for r in landmarks["records"]:
        if r["id"] not in fixed or any(
            r.get(k) != v for k, v in fixed[r["id"]].items()
        ):
            raise ValueError(
                "Runtime ear records changed a frozen template correspondence"
            )
    regions = json.loads(Path(config["regions"]).read_text())
    return (
        original,
        face,
        landmarks["records"],
        regions,
        surface["vertices"],
        surface["normals"],
        protected,
    )


def run(config):
    c = resolve(config)
    root = Path(c["output"])
    marker = root / "ear_config.json"
    if root.exists() and any(root.iterdir()) and not marker.exists():
        raise ValueError("Use an empty output or resume an ear workflow directory")
    root.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(c, indent=2))
    journal = Journal(root)
    local = lambda names: [SCRIPTS / name for name in names]
    common = local(
        ["ear_run.py", "checkpoints.py", "content_journal.py", "stage_events.py"]
    )
    command = [c["blender"], "-b", "--python-exit-code", "1", "--python"]
    landmark_path = (
        Path(c["landmarks"]) if c.get("landmarks") else root / "landmarks.json"
    )
    if c["views"]:
        project_files = [c[k] for k in ("template", "mapping", "source")]
        project_files += [
            v[k] for v in c["views"] for k in ("image", "camera", "pose", "binding")
        ]
        project_files += local(
            [
                "project_ear_landmarks.py",
                "ear_projection.py",
                "camera_ray.py",
                "blender_io.py",
                "scene_io.py",
                "process_run.py",
            ]
        )
        journal.stage(
            "ear_projection",
            signature(c, common + project_files),
            [landmark_path],
            lambda: run_process(
                command
                + [
                    str(SCRIPTS / "project_ear_landmarks.py"),
                    "--",
                    str(marker),
                    str(landmark_path),
                ],
                root / "projection.log",
            ),
        )
    args = inputs(
        c, landmark_path
    )  # Always validate provenance, including on cache hits.
    fit_files = [
        c[k]
        for k in (
            "registered",
            "settings",
            "surface",
            "template",
            "mapping",
            "regions",
            "source",
        )
    ]
    if c.get("face_fit"):
        fit_files.append(c["face_fit"])
    fit_key = signature(
        {},
        common
        + fit_files
        + [landmark_path]
        + local(["ear_projection.py", "ear_fit.py", "brush.py", "surface.py"]),
    )

    def fit():
        data = initialize(*args)
        vertices, report = deform(data)
        original = args[0]
        np.savez_compressed(root / "initial.npz", vertices=data["v"])
        # Native vertices are regenerated only after the geometry acceptance stage.
        np.savez_compressed(
            root / "candidate.npz",
            **{
                **{k: v for k, v in original.items() if k != "native_vertices"},
                "vertices": vertices,
            }
        )
        (root / "fit_report.json").write_text(json.dumps(report, indent=2))

    journal.stage(
        "ear_fit",
        fit_key,
        [root / n for n in ("initial.npz", "candidate.npz", "fit_report.json")],
        fit,
    )
    guard_files = local(
        [
            "ear_check.py",
            "ear_guard.py",
            "registered_geometry.py",
            "contact_repair.py",
            "collision.py",
            "triangle_arrays.py",
            "geometry_compare.py",
            "mesh_io.py",
            "process_run.py",
        ]
    )
    guard_key = signature(
        {"fit_signature": fit_key, "blender": c["blender"]},
        common + guard_files + [root / "initial.npz", root / "candidate.npz"],
    )
    journal.stage(
        "ear_geometry",
        guard_key,
        [root / n for n in ("checked.npz", "geometry.json", "MetaHuman_Ears.obj")],
        lambda: run_process(
            command + [str(SCRIPTS / "ear_check.py"), "--", str(marker)],
            root / "geometry.log",
        ),
    )
    return root / "checked.npz"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    print(run(json.loads(args.config.read_text())))
