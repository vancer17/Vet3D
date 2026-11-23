"""Apply independently cached template priors after brush registration."""

import json, time
from pathlib import Path
import numpy as np
from fit import read_inputs, metrics
from brush import target_surface
from neck import fair_neck
from ears import restore_ears


def run(config):
    start = time.monotonic()
    _, target, settings = read_inputs(config)
    root = Path(config["output"])
    data = dict(np.load(root / "brush_fit.npz", allow_pickle=False))
    v = data["vertices"]
    neck_report = None
    ear_report = []
    if settings.get("ear_regions"):
        v, ear_report = restore_ears(
            data["rest"],
            v,
            data["quads"],
            settings["ear_regions"],
            settings.get("ear_max_fraction", 0.05),
        )
    if settings.get("neck_fairing_indices"):
        v, neck_report = fair_neck(
            data["rest"],
            v,
            data["quads"],
            settings["neck_fairing_indices"],
            settings["identity_protected_indices"],
            settings.get("neck_fairing_max_fraction", 0.2),
        )
    data["vertices"] = v
    data["native_vertices"] = (v - data["offset"]) @ np.linalg.inv(data["linear"]).T
    np.savez_compressed(root / "fitted.npz", **data)
    excluded = settings.get("neck_fairing_indices", []) + [
        i
        for region in settings.get("ear_regions", [])
        for key in ["core_indices", "blend_indices"]
        for i in region[key]
    ]
    mask = np.setdiff1d(settings["fit_indices"], excluded)
    smooth, _ = target_surface(
        target["vertices"],
        target.get("quads"),
        settings.get("target_smooth_iterations", 12),
        target.get("normals"),
    )
    if "target_fit_indices" in settings:
        smooth = smooth[settings["target_fit_indices"]]
    report = json.loads((root / "brush_report.json").read_text())
    report["brush_seconds"] = report.pop("seconds")
    report.update(metrics(v, data["rest"], smooth, settings, mask))
    report.update(
        neck=neck_report, ears=ear_report, refine_seconds=time.monotonic() - start
    )
    (root / "fit_report.json").write_text(json.dumps(report, indent=2))
