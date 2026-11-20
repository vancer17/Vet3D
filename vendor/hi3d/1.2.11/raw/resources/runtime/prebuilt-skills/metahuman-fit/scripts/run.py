"""Independent, resumable registration workflow. Exit 2 retains a failed geometry review."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone
from uuid import uuid4

from fit import digest, read_inputs, run as fit
from refine import run as refine
from template_defaults import resolve_template_config
from contact_sheet import make_sheet, make_expression_sheet

from content_journal import Journal
from process_run import run_process

def execute(command, log, env=None):
    return run_process(command, log, env=env, error_prefix="Stage process exited")

SCRIPTS = Path(__file__).resolve().parent


def brush_settings(settings):
    return {
        k: v
        for k, v in settings.items()
        if not k.startswith(("bake_", "neck_", "ear_"))
        and k not in ["provenance", "identity_protected_indices"]
    }


def utc():
    return datetime.now(timezone.utc).isoformat()


def signature(values, files):
    files = list(files)
    shared = {"contact_sheet.py": "image_sheet.py", "preview_export.py": "glb_clips.py"}
    files += [Path(p).with_name(shared[Path(p).name]) for p in files
              if Path(p).name in shared]
    files += [Path(p).with_name("triangle_arrays.py") for p in files
              if Path(p).name == "collision.py"]
    files += [Path(p).with_name("scene_io.py") for p in files
              if Path(p).name == "blender_io.py"]
    if any(Path(p).name in {"review.py", "render_expressions.py"} for p in files):
        files += [SCRIPTS / name for name in
                  ("head_preview.py", "preview_scene.py", "scene_io.py", "material_nodes.py", "render_engine.py")]
    return hashlib.sha256(
        json.dumps(
            [values, {str(p): digest(p) for p in files}], sort_keys=True
        ).encode()
    ).hexdigest()


def run(config):
    config = resolve_template_config(config)
    root = Path(config["output"]).resolve()
    config = dict(config, output=str(root))
    config.setdefault("texture_python", sys.executable)
    if root.exists() and any(root.iterdir()) and not (root / "workflow.json").exists():
        raise ValueError(
            "Choose an empty output directory or resume one owned by this workflow"
        )
    root.mkdir(parents=True, exist_ok=True)
    journal = Journal(root)
    started = utc()
    start = time.monotonic()
    config_path = root / "run_config.json"
    config_path.write_text(json.dumps(config, indent=2))
    status = "failed"
    stages = [
        "preflight",
        "fit",
        "refine",
        "geometry",
        "dna",
        "bake",
        "review",
        "overview",
        "expressions",
        "expression_review",
    ]
    try:
        journal.stage("preflight", None, [], lambda: read_inputs(config))
        settings = json.loads(Path(config["settings"]).read_text())
        fit_settings = brush_settings(settings)
        key = signature(
            fit_settings,
            [config[k] for k in ["template", "target"]]
            + [SCRIPTS / p for p in ["fit.py", "brush.py"]],
        )
        journal.stage(
            "fit",
            key,
            [root / p for p in ["brush_fit.npz", "brush_report.json"]],
            lambda: fit(config),
        )
        key = signature(
            {k: v for k, v in settings.items() if not k.startswith("bake_")},
            [root / "brush_fit.npz", root / "brush_report.json", config["target"]]
            + [
                SCRIPTS / p
                for p in ["fit.py", "refine.py", "neck.py", "ears.py", "brush.py"]
            ],
        )
        journal.stage(
            "refine",
            key,
            [root / "fitted.npz", root / "fit_report.json"],
            lambda: refine(config),
        )
        geometry_input = root / "fitted.npz"
        if config.get("ear_registration"):
            from ear_run import run as fit_ears
            geometry_input = fit_ears(dict(config["ear_registration"],
                registered=str(root / "brush_fit.npz"), face_fit=str(geometry_input),
                settings=config["settings"], template=config["template"],
                blender=config["blender"], output=str(root / "ear_registration")))
        blender = config["blender"]
        registered = root / "registered.npz"
        command = [blender, "-b", "--python-exit-code", "1", "--python"]
        key = signature(
            dict(blender=blender, repair=not bool(config.get("ear_registration"))),
            [geometry_input]
            + [
                SCRIPTS / p
                for p in [
                    "collision.py",
                    "check_geometry.py",
                    "registered_geometry.py",
                    "geometry_compare.py",
                    "contact_repair.py",
                    "mesh_io.py",
                ]
            ],
        )
        journal.stage(
            "geometry",
            key,
            [
                root / "geometry_report.json",
                registered,
                root / "MetaHuman_Registered.obj",
            ],
            lambda: execute(
                command
                + [
                    str(SCRIPTS / "check_geometry.py"),
                    "--",
                    str(geometry_input),
                    str(root / "geometry_report.json"),
                    str(registered),
                ] + (["--no-repair"] if config.get("ear_registration") else []),
                root / "geometry.log",
            ),
        )
        dna = config.get("dna")
        dna_files = [
            root / p
            for p in [
                "MetaHuman_Review.dna",
                "MetaHuman_Review.json",
                "MetaHuman_Review.preview.npz",
            ]
        ]
        key = (
            signature(
                {k: config.get(k) for k in ["dna_python", "dna_module_path"]},
                [registered, dna]
                + [SCRIPTS / p for p in ["dna_io.py", "transport.py", "brush.py"]],
            )
            if dna
            else None
        )

        def calibrate():
            env = os.environ.copy()
            if config.get("dna_module_path"):
                env["PYTHONPATH"] = config["dna_module_path"]
            execute(
                [
                    config.get("dna_python", sys.executable),
                    str(SCRIPTS / "dna_io.py"),
                    "calibrate",
                    dna,
                    str(registered),
                    str(dna_files[0]),
                ],
                root / "dna.log",
                env,
            )

        journal.stage("dna", key, dna_files, calibrate, bool(dna))
        review = bool(config.get("source_scene"))
        files = (
            [registered, config["target"], config["settings"], config["source_scene"]]
            + [
                SCRIPTS / p
                for p in ["review.py", "texture_bake.py", "cycles_device.py", "blender_io.py", "skin_tone.py", "neck.py"]
            ]
            + ([config["template_albedo"]] if config.get("template_albedo") else [])
            if review
            else []
        )
        key = (
            signature(
                {
                    k: config.get(k)
                    for k in [
                        "source_object",
                        "texture_size",
                        "cycles_device",
                        "cage_fraction",
                        "ray_fraction",
                        "blender",
                        "template_albedo",
                        "texture_python",
                        "poisson_resolution",
                        "normal_feather_pixels",
                    ]
                },
                files,
            )
            if review
            else None
        )
        outputs = [root / "bake_report.json"] + [
            root / "textures" / ("MetaHuman_" + n + ".png")
            for n in ["Albedo", "Normal"]
        ]
        if config.get("template_albedo"):
            outputs += [root / "skin_tone_report.json"] + [
                root / "textures" / ("MetaHuman_" + n + ".png")
                for n in ["Coverage", "Template_Toned", "Albedo_Fused", "Normal_Fused"]
            ]
        journal.stage(
            "bake",
            key,
            outputs,
            lambda: execute(
                command + [str(SCRIPTS / "review.py"), "--", str(config_path), "bake"],
                root / "bake.log",
            ),
            review,
        )
        render_outputs = [
            root / "renders" / (mode + "_" + angle + ".png")
            for mode in ["highpoly", "lowpoly", "geometry", "detail"]
            for angle in ["front", "side", "threequarter"]
        ]
        preview_outputs = [
            root / p
            for p in [
                "MetaHuman_Review.blend",
                "MetaHuman_Review.glb",
                "glb_report.json",
            ]
        ] + render_outputs
        if config.get("template_eye_albedo"):
            preview_outputs += [
                root / "eye_report.json",
                root / "textures/MetaHuman_Eyes.png",
            ]
        if dna and config.get("template_teeth_albedo"):
            preview_outputs.append(root / "textures/MetaHuman_Teeth.png")
        preview_key = (
            signature(
                {
                    k: config.get(k)
                    for k in [
                        "source_object",
                        "render_size",
                        "template_albedo",
                        "texture_python",
                        "template_eye_albedo",
                        "template_teeth_albedo",
                        "eye_parameters",
                        "blender",
                    ]
                },
                [
                    registered,
                    config["target"],
                    config["settings"],
                    config["source_scene"],
                ]
                + outputs
                + [
                    SCRIPTS / p
                    for p in [
                        "review.py",
                        "blender_io.py",
                        "preview_export.py",
                        "eyes.py",
                        "neck.py",
                    ]
                ]
                + ([dna_files[2]] if dna else [])
                + (
                    [config["template_eye_albedo"]]
                    if config.get("template_eye_albedo")
                    else []
                )
                + (
                    [config["template_teeth_albedo"]]
                    if config.get("template_teeth_albedo")
                    else []
                ),
            )
            if review
            else None
        )
        journal.stage(
            "review",
            preview_key,
            preview_outputs,
            lambda: execute(
                command
                + [str(SCRIPTS / "review.py"), "--", str(config_path), "preview"],
                root / "review.log",
            ),
            review,
        )
        key = (
            signature(
                [
                    config.get("review_title", "MetaHuman registration review"),
                    config.get("source_geometry", False),
                ],
                render_outputs + [SCRIPTS / "contact_sheet.py"],
            )
            if review
            else None
        )
        journal.stage(
            "overview",
            key,
            [root / "overview.jpg"],
            lambda: make_sheet(
                root,
                config.get("review_title", "MetaHuman registration review"),
                source_geometry=config.get("source_geometry", False),
            ),
            review,
        )
        expressions = config.get("expression_presets") is not None
        if expressions and not dna:
            raise ValueError("Expression evaluation requires calibrated DNA")
        pose_outputs = [root / "expression_poses.npz", root / "expression_report.json"]
        key = (
            signature(
                {
                    k: config.get(k)
                    for k in [
                        "expression_presets",
                        "riglogic_python",
                        "riglogic_module_path",
                    ]
                },
                [
                    dna_files[0],
                    registered,
                    SCRIPTS / "expression_smoke.py",
                    SCRIPTS / "dna_io.py",
                    SCRIPTS / "brush.py",
                    SCRIPTS / "transport.py",
                ],
            )
            if expressions
            else None
        )

        def evaluate():
            env = os.environ.copy()
            if config.get("riglogic_module_path"):
                env["PYTHONPATH"] = config["riglogic_module_path"]
            execute(
                [
                    config.get("riglogic_python", sys.executable),
                    str(SCRIPTS / "expression_smoke.py"),
                    str(config_path),
                ],
                root / "expressions.log",
                env,
            )

        journal.stage("expressions", key, pose_outputs, evaluate, expressions)
        pose_renders = [
            root / "expressions" / f"pose_{i:02d}.png"
            for i in range(1 + len(config.get("expression_presets") or []))
        ]
        expression_review = expressions and review
        key = (
            signature(
                {
                    k: config.get(k)
                    for k in ["expression_render_size", "review_title", "blender"]
                },
                pose_outputs
                + [
                    root / "MetaHuman_Review.blend",
                    config["target"],
                    SCRIPTS / "render_expressions.py",
                    SCRIPTS / "blender_io.py",
                    SCRIPTS / "contact_sheet.py",
                ],
            )
            if expression_review
            else None
        )

        def review_poses():
            execute(
                command
                + [str(SCRIPTS / "render_expressions.py"), "--", str(config_path)],
                root / "expression_review.log",
            )
            make_expression_sheet(
                root, config.get("review_title", "MetaHuman registration review")
            )

        journal.stage(
            "expression_review",
            key,
            pose_renders + [root / "expressions.jpg"],
            review_poses,
            expression_review,
        )
        status = "completed"
    except BaseException:
        finished = {r["stage"] for r in journal.records}
        for name in stages:
            if name not in finished:
                journal.stage(name, None, [], lambda: None, False)
        raise
    finally:
        summary = dict(
            task_id=journal.state["task_id"],
            attempt_id=journal.attempt,
            execution_status=status,
            started_at=started,
            ended_at=utc(),
            wall_seconds=time.monotonic() - start,
            stages=journal.records,
            timing_scope="One workflow attempt including hashes/process startup/wait; stage times are contained in wall time. Environment setup, template extraction and annotation are outside this run.",
        )
        if status == "completed":
            geometry = json.loads((root / "geometry_report.json").read_text())
            summary.update(
                quality_status=(
                    "geometry_failed"
                    if not geometry["geometry_passed"]
                    else "runtime_and_visual_review_required"
                ),
                production_ready=False,
                runtime_validation=(
                    "openriglogic_sampled_poses"
                    if config.get("expression_presets") is not None
                    else "not_performed"
                ),
                geometry=geometry,
            )
            if config.get("expression_presets") is not None:
                summary["expressions"] = json.loads(
                    (root / "expression_report.json").read_text()
                )
                if geometry["geometry_passed"]:
                    summary["quality_status"] = (
                        "sampled_runtime_evaluated_visual_review_required"
                    )
        (root / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))
    return 2 if summary["quality_status"] == "geometry_failed" else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config")
    args = parser.parse_args()
    sys.exit(run(json.loads(Path(args.config).read_text())))
