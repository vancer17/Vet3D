"""Fit an intact MetaHuman template to annotated quads or oriented surface samples."""

import json, sys, hashlib, time
from pathlib import Path
import numpy as np
from brush import fit_brush
from template_defaults import resolve_template_config
from neck import validate_neck_mask
from scipy.spatial import cKDTree


from fit_metrics import metrics, distance_stats

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_inputs(config):
    config = resolve_template_config(config)
    if config.get("hair_state") != "bald":
        raise ValueError(
            "MetaHuman registration currently requires a confirmed bald target"
        )
    if config.get("target_parts") != "skin":
        raise ValueError(
            "Provide a skin-only target with eye/teeth meshes excluded, and declare target_parts=skin"
        )
    template = dict(np.load(config["template"], allow_pickle=False))
    target = dict(np.load(config["target"], allow_pickle=False))
    settings = json.loads(Path(config["settings"]).read_text())
    if settings.get("template_sha256") != digest(config["template"]) or settings.get(
        "target_sha256"
    ) != digest(config["target"]):
        raise ValueError("Settings must match both template and target content hashes")
    for label, m in [("template", template), ("target", target)]:
        v = m["vertices"]
        q = m.get("quads")
        if (
            v.ndim != 2
            or v.shape[1] != 3
            or len(v) < 4
            or not np.isfinite(v).all()
            or np.ptp(v, axis=0).max() <= 0
        ):
            raise ValueError(label + " has invalid vertices")
        if label == "target" and "normals" in m:
            normals = m["normals"]
            if (
                normals.shape != v.shape
                or not np.isfinite(normals).all()
                or not np.allclose(np.linalg.norm(normals, axis=1), 1, atol=1e-3)
            ):
                raise ValueError("Invalid oriented surface sample normals")
            continue
        if q is None or (
            q.ndim != 2
            or q.shape[1] != 4
            or len(q) == 0
            or not np.issubdtype(q.dtype, np.integer)
            or q.min() < 0
            or q.max() >= len(v)
        ):
            raise ValueError(label + " has invalid quad topology")
    uv = template["quad_uvs"]
    if uv.shape != (len(template["quads"]), 4, 2) or not np.isfinite(uv).all():
        raise ValueError("Invalid per-corner template UV")
    ids = (
        [p["vertex_index"] for p in settings["landmarks"]]
        + settings["fit_indices"]
        + settings.get("bake_indices", [])
        + settings.get("bake_template_color_indices", [])
        + settings.get("neck_fairing_indices", [])
        + settings.get("identity_protected_indices", [])
        + [
            i
            for region in settings.get("ear_regions", [])
            for key in ["core_indices", "blend_indices", "anchor_indices"]
            for i in region[key]
        ]
    )
    if (
        not ids
        or not all(isinstance(i, int) for i in ids)
        or min(ids) < 0
        or max(ids) >= len(template["vertices"])
    ):
        raise ValueError("Template mask/landmark index outside topology")
    if not settings["fit_indices"]:
        raise ValueError("The observed exterior mask cannot be empty")
    if "target_fit_indices" in settings:
        ti = settings["target_fit_indices"]
        if not ti or not all(
            isinstance(i, int) and 0 <= i < len(target["vertices"]) for i in ti
        ):
            raise ValueError("Invalid source skin observation indices")
    if settings.get("ear_policy") == "template_rigid" and not settings.get(
        "ear_regions"
    ):
        raise ValueError("Rigid template ear policy requires explicit ear_regions")
    ear_active = []
    for region in settings.get("ear_regions", []):
        ear_active += region["core_indices"] + region["blend_indices"]
    ear_cores = [
        i for region in settings.get("ear_regions", []) for i in region["core_indices"]
    ]
    if np.intersect1d(ear_cores, settings["fit_indices"]).size:
        raise ValueError(
            "Template ear cores must be excluded from source fitting attraction"
        )
    if settings.get("bake_template_color_indices") and not config.get(
        "template_albedo"
    ):
        raise ValueError("Preserving template oral color requires template_albedo")
    if np.intersect1d(ear_active, settings.get("neck_fairing_indices", [])).size:
        raise ValueError("Ear and neck correction regions must be disjoint")
    if np.intersect1d(
        ear_active, [p["vertex_index"] for p in settings["landmarks"]]
    ).size:
        raise ValueError("Template ear regions overlap facial landmarks")
    if settings.get("neck_fairing_indices"):
        # A neck mask must be reviewed independently of the identity mask.
        if not settings.get("identity_protected_indices"):
            raise ValueError("Neck repair requires identity_protected_indices")
        validate_neck_mask(
            settings["neck_fairing_indices"],
            settings["identity_protected_indices"]
            + [p["vertex_index"] for p in settings["landmarks"]],
        )
    if settings.get("neck_fairing_max_fraction", 0.2) <= 0:
        raise ValueError("Invalid neck distance budget")
    goals = np.array([p["target"] for p in settings["landmarks"]], float)
    if goals.shape != (len(settings["landmarks"]), 3) or not np.isfinite(goals).all():
        raise ValueError("Invalid 3D landmarks")
    weights = np.array([p.get("weight", 1) for p in settings["landmarks"]], float)
    if not np.isfinite(weights).all() or (weights <= 0).any():
        raise ValueError("Invalid landmark weights")
    iterations = settings.get("target_smooth_iterations", 12)
    if not isinstance(iterations, int) or iterations < 0:
        raise ValueError("Invalid target smoothing iterations")
    if "brush_stages" in settings and not settings["brush_stages"]:
        raise ValueError("Empty brush schedule")
    for stage in settings.get("brush_stages", []):
        if (
            stage["sigma_edges"] <= 0
            or not isinstance(stage["iterations"], int)
            or stage["iterations"] < 1
        ):
            raise ValueError("Invalid brush schedule")
    if "mobility" in settings:
        mask = np.asarray(settings["mobility"])
        if (
            mask.shape != (len(template["vertices"]),)
            or not np.isfinite(mask).all()
            or (mask < 0).any()
            or (mask > 1).any()
        ):
            raise ValueError("Invalid mobility weights")
    return template, target, settings






def run(config):
    config = resolve_template_config(config)
    template, target, settings = read_inputs(config)
    root = Path(config["output"])
    root.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    v, linear, offset, rest, smooth, history = fit_brush(
        template["vertices"],
        template["quads"],
        target["vertices"],
        target.get("quads"),
        settings,
        target_normals=target.get("normals"),
    )
    native = (v - offset) @ np.linalg.inv(linear).T
    data = dict(
        vertices=v,
        quads=template["quads"],
        quad_uvs=template["quad_uvs"],
        rest=rest,
        native_vertices=native,
        linear=linear,
        offset=offset,
    )
    data["dna_sha256"] = template.get("dna_sha256", np.array(""))
    np.savez_compressed(root / "brush_fit.npz", **data)
    report = dict(
        seconds=time.monotonic() - start,
        stages=history,
        **metrics(v, rest, smooth, settings, settings["fit_indices"]),
        template_sha256=digest(config["template"]),
        target_sha256=digest(config["target"]),
        vertices=len(v),
        quads=len(template["quads"]),
        topology_preserved=True,
        ear_policy=settings.get("ear_policy", "template"),
        units="target coordinates; distances are sampled only on the configured observed exterior mask",
        detail_policy="smoothed target for registration; untouched high mesh for normal baking",
        status="fitted_pending_geometry_and_runtime_review",
    )
    (root / "brush_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == "__main__":
    run(json.loads(Path(sys.argv[1]).read_text()))
