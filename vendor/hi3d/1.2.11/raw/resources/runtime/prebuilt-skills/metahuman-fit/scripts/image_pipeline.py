"""Image/Hi3D high GLB to MetaHuman topology and textures, with resumable annotation handoff."""

import argparse, json, shutil, subprocess, sys, time
from pathlib import Path
import numpy as np
from run import Journal, signature, execute, utc
from fit import digest, read_inputs
from surface import smooth_samples
from template_defaults import resolve_template_config

SCRIPTS = Path(__file__).resolve().parent
GENERATION = {
    "model": "hi3dv3.0",
    "resolution": "2048quality",
    "request_type": 3,
    "face": 5000000,
    "format": 2,
    "pbr": 1,
    "shading": "0.5",
}


def api_command(config, arguments):
    script = Path(config["hi3d_api_script"]).resolve()
    if not script.is_file():
        raise ValueError(
            "Provide the installed hi3d-api/scripts/hi3d_api.py explicitly"
        )
    return [config.get("hi3d_python", sys.executable), str(script)] + arguments


def invoke(command):
    result = subprocess.run(command, capture_output=True, text=True)
    try:
        payload = json.loads(result.stdout)
    except ValueError:
        raise RuntimeError(
            "Hi3D CLI returned no structured result; inspect its job checkpoint"
        ) from None
    if payload.get("result") == "waiting_choice":
        return payload
    if result.returncode or payload.get("error_type"):
        raise RuntimeError(
            "Hi3D operation needs attention; preserve the job and do not resubmit"
        )
    return payload


def submit_arguments(config, job):
    views = config.get("gray_views")
    if views is not None:
        if config.get("image") or not isinstance(views, dict) or "front" not in views:
            raise ValueError("Provide gray_views with front, or one image, not both")
        if set(views) - {"front", "right", "back", "left"}:
            raise ValueError("Unknown gray view direction")
        names = [name for name in ("front", "right", "back", "left") if name in views]
        args = ["submit", "model"]
        for name in names:
            args += ["--image", str(Path(views[name]).resolve())]
        if len(names) > 1:
            args += ["--views", ",".join(names)]
        args += ["--job", str(job)]
    else:
        args = ["submit", "model", "--image", str(Path(config["image"]).resolve()),
                "--job", str(job)]
    for key, value in generation_options(config).items():
        args += ["--set", f"{key}={value}"]
    return args


def consent_arguments(config):
    """Persisted parameter selections are per run and never enter the job fingerprint."""
    args = []
    if config.get("hi3d_session"):
        args += ["--session", str(Path(config["hi3d_session"]).resolve())]
    return args


def generation_options(config):
    """Keep the legacy textured path; separated gray references need geometry only."""
    mode = config.get("generation_mode", "geometry_texture")
    if mode not in ("geometry", "geometry_texture"):
        raise ValueError("generation_mode must be geometry or geometry_texture")
    options = dict(GENERATION)
    if mode == "geometry":
        options["request_type"] = 1
        options.pop("pbr")
    return options


def select_glb(artifact, name=None):
    candidates = [
        Path(item["path"])
        for item in artifact["files"]
        if Path(item["path"]).suffix.lower() == ".glb"
    ]
    if name:
        candidates = [p for p in candidates if p.name == name]
    if len(candidates) != 1:
        raise ValueError("Select one downloaded GLB using artifact_name")
    return candidates[0].resolve()


def generation_tick(config, root, call=invoke):
    """One bounded polling slice; all protocol/auth/recovery belongs to explicit hi3d-api."""
    job = root / "hi3d_job.json"
    args = submit_arguments(config, job)
    planned = call(api_command(config, args + ["--dry-run"]))
    if job.exists():
        state = json.loads(job.read_text())
        if not planned.get("fingerprint") or state.get("fingerprint") != planned["fingerprint"]:
            raise ValueError("Existing job belongs to another plan; preserve it")
        if state.get("state") in ("failed", "submission_rejected", "submitting", "submission_uncertain"):
            raise RuntimeError("Existing submission needs attention; do not resubmit")
        # A failed GET must resume through wait/query, not the submit CLI's error exit.
    else:
        result = call(api_command(config, args + consent_arguments(config)))
        if result.get("result") == "waiting_choice":
            return dict(status="waiting_choice", stage=result.get("stage"), consent=result)
        state = result["job"]
    if not state.get("task_id"):
        raise RuntimeError(
            "No confirmed task ID; recover the original job before continuing"
        )
    if state.get("state") != "success" or state.get("last_query_error"):
        result = call(
            api_command(
                config,
                [
                    "wait",
                    "--job",
                    str(job),
                    "--seconds",
                    str(config.get("poll_seconds", 45)),
                    "--interval",
                    "10",
                ],
            )
        )
        if result["result"] != "success":
            return dict(status="waiting_generation", task_id=state["task_id"])
    result = call(
        api_command(
            config, ["download", "--job", str(job), "--out", str(root / "generation")]
        )
    )
    path = select_glb(result["artifact"], config.get("artifact_name"))
    return dict(
        status="completed",
        task_id=state["task_id"],
        high_glb=str(path),
        sha256=digest(path),
        requested=generation_options(config),
    )


def prepare_samples(root, fraction):
    data = dict(np.load(root / "surface_raw.npz", allow_pickle=False))
    data["vertices"], data["normals"] = smooth_samples(
        data["vertices"], data["normals"], fraction
    )
    np.savez_compressed(root / "target.npz", **data)


def bind_annotations(
    annotation_path,
    source,
    template,
    target,
    output,
    source_object=None,
    polygon_count=None,
):
    """Accept source-bound 3D annotations; never reuse another asset's lowpoly indices."""
    data = json.loads(Path(annotation_path).read_text())
    if data.get("source_object") != source_object:
        raise ValueError(
            "Annotations must name the same explicitly selected source object"
        )
    if data.get("source_sha256") != digest(source) or data.get(
        "template_sha256"
    ) != digest(template):
        raise ValueError(
            "Annotations must match the exact high GLB and template hashes"
        )
    if data.get("coordinate_space") != "blender_world_z_up":
        raise ValueError(
            "Annotations must use the prepared Blender world coordinate frame"
        )
    if "target_fit_indices" in data or "target_sha256" in data:
        raise ValueError(
            "Use source polygon exclusions, not indices from a previous lowpoly/sample array"
        )
    settings = dict(data["settings"])
    if "target_fit_indices" in settings or "target_sha256" in settings:
        raise ValueError("Remove stale target indices/hashes from annotation settings")
    samples = np.load(target, allow_pickle=False)
    excluded = data.get("source_exclude_polygon_indices", [])
    if not isinstance(excluded, list) or any(
        type(i) is not int
        or i < 0
        or (polygon_count is not None and i >= polygon_count)
        for i in excluded
    ):
        raise ValueError("Invalid source polygon exclusions")
    selected = np.flatnonzero(~np.isin(samples["source_polygon_indices"], excluded))
    if len(selected) < 100:
        raise ValueError("Not enough observed skin samples")
    settings.update(
        template_sha256=digest(template),
        target_sha256=digest(target),
        target_fit_indices=selected.tolist(),
    )
    Path(output).write_text(json.dumps(settings, indent=2))


def deliver(registration, root, template):
    config = json.loads((registration / "run_config.json").read_text())
    data = np.load(registration / "registered.npz", allow_pickle=False)
    base = np.load(template, allow_pickle=False)
    for key in ["quads", "quad_uvs"]:
        if not np.array_equal(data[key], base[key]):
            raise ValueError("Registered topology/UV differs from the template")
    if len(data["vertices"]) != len(base["vertices"]):
        raise ValueError("Template vertex count changed")
    root.mkdir(exist_ok=True)
    files = [
        registration / p
        for p in [
            "MetaHuman_Registered.obj",
            "registered.npz",
            "MetaHuman_Review.glb",
            "overview.jpg",
            "summary.json",
        ]
    ]
    texture_names = ["Albedo", "Normal"]
    if config.get("template_albedo"):
        texture_names += ["Coverage", "Template_Toned", "Albedo_Fused", "Normal_Fused"]
    if config.get("dna"):
        files.append(registration / "MetaHuman_Review.dna")
        if config.get("template_eye_albedo"):
            texture_names.append("Eyes")
        if config.get("template_teeth_albedo"):
            texture_names.append("Teeth")
    files += [
        registration / "textures" / f"MetaHuman_{name}.png" for name in texture_names
    ]
    files.append(registration / "MetaHuman_Review.blend")
    if "expression_presets" in config:
        files += [
            registration / name
            for name in ["expressions.jpg", "expression_report.json"]
        ]
    records = []
    for path in files:
        relative = path.relative_to(registration)
        dest = root / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        records.append(
            dict(
                path=str(dest.resolve()),
                relative_path=str(relative),
                bytes=dest.stat().st_size,
                sha256=digest(dest),
            )
        )
    manifest = dict(
        vertices=len(data["vertices"]),
        quads=len(data["quads"]),
        topology_and_uv_preserved=True,
        template_sha256=digest(template),
        target_sha256=digest(config["target"]),
        textures={
            name.lower(): f"textures/MetaHuman_{name}.png" for name in texture_names
        },
        files=records,
        scope="MetaHuman template topology and baked textures. Static GLB; optional DNA and sampled runtime review are separate.",
    )
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2))


def run(config, dry_run=False):
    runtime = config.get("execution_backend") == "runtime" or (SCRIPTS.parent / ".runtime-profile.json").is_file()
    if runtime and (config.get("image") or config.get("gray_views") or not config.get("high_glb")):
        raise ValueError("Generate with Runtime hi3d_api first, then provide existing high_glb")
    if bool(config.get("image")) == bool(config.get("high_glb")):
        raise ValueError("Provide exactly one image or existing high_glb")
    registration = resolve_template_config(config["registration"])
    if (
        registration.get("hair_state") != "bald"
        or registration.get("target_parts") != "skin"
    ):
        raise ValueError(
            "Confirm a bald head and a skin-only selected object before generation/registration"
        )
    for key in ["template", "blender"]:
        if not Path(registration[key]).is_file():
            raise ValueError(f"Missing registration dependency: {key}")
    if not 5 <= config.get("poll_seconds", 45) <= 50:
        raise ValueError("poll_seconds must be 5..50")
    count = config.get("sample_count", 100000)
    if type(count) is not int or not 1000 <= count <= 1000000:
        raise ValueError("sample_count must be an integer in 1000..1000000")
    if not 0 <= config.get("surface_smooth_fraction", 0.006) <= 0.03:
        raise ValueError("surface_smooth_fraction must be 0..0.03")
    if config.get("high_glb") and not Path(config["high_glb"]).is_file():
        raise ValueError("Missing high_glb")
    root = Path(config["output"]).resolve()
    if dry_run:
        if config.get("image"):
            return invoke(
                api_command(
                    config,
                    submit_arguments(config, root / "hi3d_job.json") + ["--dry-run"],
                )
            )
        return dict(dry_run=True, high_glb=str(Path(config["high_glb"]).resolve()))
    if root.exists() and any(root.iterdir()) and not (root / "workflow.json").exists():
        raise ValueError("Choose an empty pipeline output or resume its own checkpoint")
    root.mkdir(parents=True, exist_ok=True)
    journal = Journal(root)
    start = time.monotonic()
    started = utc()
    status = "failed"
    names = [
        "generation",
        "source",
        "surface",
        "annotations",
        "registration",
        "delivery",
    ]
    result = {}
    source_dir = root / "source"
    source_dir.mkdir(exist_ok=True)
    try:
        generation_file = root / "generation.json"

        def generate():
            if config.get("high_glb"):
                path = Path(config["high_glb"]).resolve()
                record = dict(
                    status="completed",
                    high_glb=str(path),
                    sha256=digest(path),
                    mode="runtime_handoff_complete" if runtime else "reuse_existing_high",
                )
            else:
                record = generation_tick(config, root)
            generation_file.write_text(json.dumps(record, indent=2))

        journal.stage("generation", None, [generation_file], generate)
        generation = json.loads(generation_file.read_text())
        if generation["status"] == "waiting_choice":
            status = "waiting_choice"
            return dict(status=status, stage=generation.get("stage"), consent=generation.get("consent"))
        if generation["status"] != "completed":
            status = "waiting_generation"
            return dict(status=status)
        high = generation["high_glb"]
        prep = dict(
            high_glb=high,
            output=str(source_dir),
            source_object=config.get("source_object"),
            sample_count=config.get("sample_count", 100000),
            sample_seed=config.get("sample_seed", 0),
        )
        prep_path = root / "prepare_config.json"
        prep_path.write_text(json.dumps(prep))
        key = signature(
            {k: v for k, v in prep.items() if k != "output"},
            [
                high,
                SCRIPTS / "prepare_high.py",
                SCRIPTS / "surface.py",
                SCRIPTS / "blender_io.py",
            ],
        )
        outputs = [
            source_dir / n
            for n in ["Source_High.blend", "surface_raw.npz", "source_report.json"]
        ]
        journal.stage(
            "source",
            key,
            outputs,
            lambda: execute(
                [
                    registration["blender"],
                    "-b",
                    "--python-exit-code",
                    "1",
                    "--python",
                    str(SCRIPTS / "prepare_high.py"),
                    "--",
                    str(prep_path),
                ],
                root / "source.log",
            ),
        )
        fraction = config.get("surface_smooth_fraction", 0.006)
        target = source_dir / "target.npz"
        journal.stage(
            "surface",
            signature(
                fraction, [source_dir / "surface_raw.npz", SCRIPTS / "surface.py"]
            ),
            [target],
            lambda: prepare_samples(source_dir, fraction),
        )
        request = dict(
            source_glb=high,
            source_object=config.get("source_object"),
            source_sha256=digest(high),
            source_report=str(source_dir / "source_report.json"),
            source_scene=str(source_dir / "Source_High.blend"),
            template=registration["template"],
            template_sha256=digest(registration["template"]),
            sample_target=str(target),
            coordinate_space="blender_world_z_up",
            required_output=config.get("annotations"),
        )
        (root / "annotation_request.json").write_text(json.dumps(request, indent=2))
        annotation = config.get("annotations")
        if not annotation or not Path(annotation).is_file():
            status = "waiting_annotations"
            return dict(status=status)
        settings = root / "bound_settings.json"
        journal.stage(
            "annotations",
            signature(
                config.get("source_object"),
                [
                    annotation,
                    high,
                    registration["template"],
                    target,
                    SCRIPTS / "image_pipeline.py",
                ],
            ),
            [settings],
            lambda: bind_annotations(
                annotation,
                high,
                registration["template"],
                target,
                settings,
                config.get("source_object"),
                json.loads((source_dir / "source_report.json").read_text())[
                    "source_polygons"
                ],
            ),
        )
        registration.update(
            target=str(target),
            settings=str(settings),
            source_scene=str(source_dir / "Source_High.blend"),
            source_object="Source_High",
            source_geometry=True,
            output=str(root / "registration"),
        )
        read_inputs(registration)
        config_path = root / "registration_config.json"
        config_path.write_text(json.dumps(registration, indent=2))

        def register():
            with (root / "registration.log").open("w") as stream:
                process = subprocess.Popen(
                    [sys.executable, str(SCRIPTS / "run.py"), str(config_path)],
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                )
                try:
                    code = process.wait()
                except BaseException:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    raise
            if code not in [0, 2]:
                raise RuntimeError("Registration failed; inspect the child summary")
            result["geometry_passed"] = code == 0

        journal.stage(
            "registration", None, [root / "registration/summary.json"], register
        )
        if not result["geometry_passed"]:
            status = "geometry_failed"
            return dict(status=status)
        source_files = sorted(
            p
            for p in (root / "registration").rglob("*")
            if p.is_file()
            and p.suffix
            in [".npz", ".obj", ".png", ".glb", ".dna", ".blend", ".jpg", ".json"]
        )

        def publish():
            deliver(root / "registration", root / "delivery", registration["template"])
            delivery_outputs[:] = [old_manifest] + [
                Path(x["path"]) for x in json.loads(old_manifest.read_text())["files"]
            ]

        old_manifest = root / "delivery/manifest.json"
        delivery_outputs = [old_manifest]
        if old_manifest.exists():
            delivery_outputs += [
                Path(x["path"]) for x in json.loads(old_manifest.read_text())["files"]
            ]
        journal.stage(
            "delivery",
            signature(None, source_files + [SCRIPTS / "image_pipeline.py"]),
            delivery_outputs,
            publish,
        )
        status = "completed"
        return dict(status=status, delivery=str(root / "delivery"))
    finally:
        completed = {r["stage"] for r in journal.records}
        for name in names:
            if name not in completed:
                journal.stage(name, None, [], lambda: None, False)
        summary = dict(
            status=status,
            started_at=started,
            ended_at=utc(),
            wall_seconds=time.monotonic() - start,
            stages=journal.records,
            requested_generation=generation_options(config) if config.get("image") else None,
            timing_scope="One invocation. Child registration times are included, not additive. Generation may span multiple polling invocations; keypoint service and manual wait are external.",
            production_ready=False,
        )
        (root / "summary.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    value = run(json.loads(Path(args.config).read_text()), args.dry_run)
    print(json.dumps(value))
    sys.exit(0 if args.dry_run or value["status"] == "completed" else 3)
