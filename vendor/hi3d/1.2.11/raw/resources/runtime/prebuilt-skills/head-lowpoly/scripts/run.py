"""Explicit, resumable local workflow; task outputs never belong in the skill package."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

from checkpoints import digest, artifacts_match
from process_run import run_process
from mdf_handoff import WaitingForRetopology, prepare_handoff

def run_stage(command, log_path):
    return run_process(command, log_path)

SCRIPTS = Path(__file__).resolve().parent


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2))
    temporary.replace(path)


def preflight(config):
    default = "runtime" if (SCRIPTS.parent / ".runtime-profile.json").is_file() else "instant_meshes"
    config.setdefault("retopology_backend", default)
    if config["retopology_backend"] not in {"runtime", "instant_meshes"}:
        raise ValueError("retopology_backend must be runtime or instant_meshes")
    required = ["source", "face_config", "output", "blender"]
    if config["retopology_backend"] == "instant_meshes":
        required.append("instant_meshes")
    for key in required:
        if not config.get(key):
            raise ValueError("Missing config field: " + key)
        config[key] = str(Path(config[key]).expanduser().resolve())
        if key != "output" and not Path(config[key]).is_file():
            raise ValueError("Missing file: " + key)
    if Path(config["source"]).suffix.lower() != ".glb":
        raise ValueError("The workflow expects a self-contained high-poly GLB")
    output = Path(config["output"])
    if config["retopology_backend"] == "runtime":
        config["retopology_job"] = str(Path(config.get("retopology_job", output / "mdf-retopology.json")).resolve())
    if output == SCRIPTS.parent or SCRIPTS.parent in output.parents:
        raise ValueError("Task output must be outside the skill package")
    for key, default in [("working_triangles", 700000), ("remesh_face_goal", 20000),
                         ("texture_size", 4096), ("review_size", 640),
                         ("surface_samples", 250000), ("hair_face_goal", 10000)]:
        config.setdefault(key, default)
        if type(config[key]) is not int or config[key] <= 0:
            raise ValueError("Invalid positive integer: " + key)
    config.setdefault("hair_state", "unknown")
    if config["hair_state"] not in ["bald", "hair", "unknown"]:
        raise ValueError("hair_state must be bald, hair or unknown")
    hair = config.setdefault("hair_objects", [])
    if not isinstance(hair, list) or any(not isinstance(n, str) or not n for n in hair) or len(set(hair)) != len(hair):
        raise ValueError("hair_objects must list unique mesh object names")
    if hair and config["hair_state"] != "hair":
        raise ValueError("Explicit hair objects require hair_state=hair")
    config.setdefault("diagnostic_previews", False)
    config.setdefault("bake_pbr_extras", "auto")
    if type(config["diagnostic_previews"]) is not bool or config["bake_pbr_extras"] not in ["auto", "all"]:
        raise ValueError("diagnostic_previews must be boolean; bake_pbr_extras must be auto or all")
    config.setdefault("uv_method", "CONFORMAL")
    if config["uv_method"] not in ["ANGLE_BASED", "CONFORMAL", "MINIMUM_STRETCH"]:
        raise ValueError("Unsupported UV unwrap method")
    frames = config.setdefault("video_frames_per_control", 0)
    if type(frames) is not int or frames < 0 or frames == 1:
        raise ValueError("Video needs zero or at least two frames per control")
    if frames:
        if not config.get("ffmpeg") or not Path(config["ffmpeg"]).is_file():
            raise ValueError("Video requires an explicit ffmpeg executable")
        config["ffmpeg"] = str(Path(config["ffmpeg"]).resolve())
    face = json.loads(Path(config["face_config"]).read_text())
    if face.get("source_sha256") != digest(config["source"]):
        raise ValueError("face_config source hash mismatch; annotate this input explicitly")
    if sorted(p["kind"] for p in face["patches"]) != ["eye", "eye", "mouth"]:
        raise ValueError("Current adapter requires two eye patches and one mouth patch")
    for patch in face["patches"]:
        if patch["rings"] < 2 or any(v <= 0 for v in patch["inner_radii"] + patch["outer_radii"]):
            raise ValueError("Invalid patch dimensions")
    generated = {str((output / name).resolve()) for stage in stages(config, output / "resolved_config.json") for name in stage["outputs"]}
    if any(config[k] in generated for k in required if k != "output"):
        raise ValueError("An input path collides with a generated output")
    return config


def stages(config, config_path):
    root = Path(config["output"])
    def blender(script, *args):
        return [config["blender"], "-b", "--python-exit-code", "1", "--python", str(SCRIPTS / script), "--", *args, str(config_path)]
    def python(script):
        return [sys.executable, str(SCRIPTS / script), str(config_path)]
    result = []
    def add(name, command, outputs, dependencies=(), keys=(), scripts=()):
        scripts = list(scripts)
        if any(s in scripts for s in ("bake.py", "review.py")):
            scripts.append("render_engine.py")
        if any(name in scripts for name in ("low_rig.py", "validate.py")) and "collision.py" not in scripts:
            scripts.append("collision.py")
        if "collision.py" in scripts:
            scripts.append("triangle_arrays.py")
        if "blender_io.py" in scripts:
            scripts += ["head_io.py", "scene_io.py", "head_preview.py", "preview_scene.py", "material_nodes.py", "render_engine.py"]
        result.append(dict(name=name, command=command, outputs=outputs, dependencies=list(dependencies), keys=list(keys), scripts=list(scripts)))
    preview = ["diagnostic_previews", "preview_size"]
    add("prepare", blender("prepare.py"), ["source.blend", "source_report.json", "source_boundary.json", "surface_samples.npz"], keys=["source", "source_object", "hair_objects", "hair_state", "seed", "surface_samples"] + preview, scripts=["prepare.py", "blender_io.py"])
    if config.get("retopology_backend") == "runtime":
        add("working_surface", blender("retopology.py", "working"), ["working_surface.glb", "working_surface_report.json"], ["prepare"], ["working_triangles", "retopology_backend"], ["retopology.py", "blender_io.py", "mdf_handoff.py"])
        add("remesh", blender("retopology.py", "import"), ["source_quads.obj", "retopology_import_report.json"], ["working_surface"], ["retopology_job", "retopology_obj", "remesh_face_goal", "retopology_backend"], ["retopology.py", "blender_io.py", "mdf_handoff.py"])
    else:
        add("working_surface", blender("retopology.py", "working"), ["working_surface.obj", "working_surface_report.json"], ["prepare"], ["working_triangles"], ["retopology.py", "blender_io.py"])
        add("remesh", [config["instant_meshes"], "-d", "-r", "4", "-p", "4", "-f", str(config["remesh_face_goal"]), "-S", "2", "-o", str(root / "source_quads.obj"), str(root / "working_surface.obj")], ["source_quads.obj"], ["working_surface"], ["instant_meshes", "remesh_face_goal"])
    add("facial_topology", blender("retopology.py", "facial"), ["Lowpoly_Unbaked.blend", "lowpoly_patch_data.npz", "lowpoly_report.json"], ["prepare", "remesh"], ["face_config", "uv_method"] + preview, ["retopology.py", "blender_io.py"])
    add("lowpoly_rig", blender("low_rig.py"), ["Lowpoly_Rigged.blend", "lowpoly_data.npz", "lowpoly_repair.json", "hair_report.json"], ["facial_topology"], ["face_config", "hair_face_goal"], ["low_rig.py", "collision.py", "blender_io.py"])
    add("lowpoly_validate", blender("validate.py", "low"), ["lowpoly_validation.json"], ["lowpoly_rig"], preview, ["validate.py", "collision.py", "low_rig.py", "blender_io.py"])
    bake_outputs = ["Lowpoly_Baked.blend", "bake_report.json"] + ["textures/Lowpoly_" + n + ".png" for n in ["BaseColor", "Normal"]]
    add("bake", blender("bake.py"), bake_outputs, ["lowpoly_rig", "lowpoly_validate"], ["texture_size", "cage_fraction", "ray_fraction", "bake_pbr_extras"], ["bake.py", "texture_bake.py", "cycles_device.py"])
    add("deliver", blender("deliver.py"), ["Heads_Rigged.blend", "Lowpoly_Rigged.glb", "delivery.json"], ["bake"], scripts=["deliver.py", "glb_clips.py", "blender_io.py", "low_rig.py"])
    add("metrics", blender("metrics.py"), ["metrics.json"], ["deliver", "prepare"], ["face_config", "seed"], ["metrics.py", "blender_io.py", "validate.py", "low_rig.py"])
    outputs = [f"review/{v}_{a}.png" for v in ["high", "lowpoly"] for a in ["front", "threequarter", "side"]]
    outputs += [f"review/lowpoly_{s}.png" for s in ["eyeBlink_L", "mouthSmile", "jawOpen", "wire"]]
    if config.get("video_frames_per_control"):
        count = (len(json.loads(Path(config["face_config"]).read_text())["controls"]["fields"]) + 5) * config["video_frames_per_control"]
        outputs += ["review/frames.json"] + [f"review/lowpoly_{i:04d}.png" for i in range(count)]
    add("review", blender("review.py"), outputs, ["deliver"], ["review_size", "video_frames_per_control"], ["review.py", "blender_io.py"])
    package_outputs = ["review/comparison.jpg", "review/expressions.jpg", "REVIEW.md"]
    if config.get("video_frames_per_control"):
        package_outputs += ["review/expressions.mp4", "review/expressions.video.json"]
    add("package_review", python("package_review.py"), package_outputs, ["review", "metrics", "lowpoly_validate", "deliver"], ["video_frames_per_control", "ffmpeg"], ["package_review.py", "image_sheet.py"] + (["encode_sequence.py", "check_media.py", "media_tools.py"] if config.get("video_frames_per_control") else []))
    if config.get("diagnostic_previews"):
        diagnostics = {"prepare": ["high_front.png", "high_side.png"],
                       "facial_topology": ["lowpoly_front.png", "lowpoly_side.png"],
                       "lowpoly_validate": [f"low_check_{name}.png" for name in ["neutral", "eyeBlink_L", "mouthSmile", "jawOpen"]]}
        for stage in result:
            stage["outputs"] += diagnostics.get(stage["name"], [])
    return result


def stage_fingerprint(stage, config, completed, memo):
    def file_hash(path):
        path = str(Path(path).resolve())
        if path not in memo:
            memo[path] = digest(path)
        return memo[path]
    settings = {k: config.get(k) for k in stage["keys"]}
    path_keys = {"source", "face_config", "instant_meshes", "retopology_job", "retopology_obj", "ffmpeg"}
    files = {k: file_hash(v) for k, v in settings.items() if k in path_keys and v is not None}
    files.update({name: file_hash(SCRIPTS / name) for name in stage["scripts"]})
    executable = stage["command"][0]
    files["executable"] = file_hash(executable)
    value = dict(schema=2, settings=settings, files=files, command=stage["command"],
                 dependencies={k: completed[k]["outputs"] for k in stage["dependencies"]})
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def workflow(config, resume=True):
    root = Path(config["output"])
    root.mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(exist_ok=True)
    checkpoint = root / "workflow.json"
    previous = json.loads(checkpoint.read_text()) if checkpoint.exists() else {}
    attempt_id = str(uuid.uuid4())
    task_id = previous.get("task_id", str(uuid.uuid4()))
    started = utc_now()
    clock = time.monotonic()
    config_path = root / "resolved_config.json"
    write_json(config_path, config)
    cached = previous.get("completed", {}) if resume and previous.get("schema") == 2 else {}
    manifest = {
        "task_id": task_id,
        "attempt_id": attempt_id,
        "previous_attempt_id": previous.get("attempt_id"),
        "schema": 2,
        "started_at": started,
        "status": "running",
        "completed": {},
    }
    write_json(checkpoint, manifest)
    if previous.get("status") == "running":
        with (root / "timings.jsonl").open("a") as stream:
            stream.write(
                json.dumps(
                    {
                        "task_id": task_id,
                        "attempt_id": previous.get("attempt_id"),
                        "stage": "attempt_recovery",
                        "status": "interrupted",
                        "started_at": previous.get("started_at"),
                        "ended_at": None,
                        "elapsed_seconds": None,
                        "reason": "Previous process ended without a final record; exact interruption time is unavailable",
                        "recovered_by_attempt_id": attempt_id,
                    }
                )
                + "\n"
            )
    records = []
    failure = None
    memo = {}
    for stage in stages(config, config_path):
        name, command, outputs = stage["name"], stage["command"], stage["outputs"]
        stage_start = utc_now()
        stage_clock = time.monotonic()
        record = {
            "task_id": task_id,
            "attempt_id": attempt_id,
            "stage": name,
            "started_at": stage_start,
        }
        try:
            if failure:
                record.update(status="skipped", reason="upstream failure; not executed")
            else:
                if name == "remesh" and config.get("retopology_backend") == "runtime":
                    config["retopology_obj"] = str(prepare_handoff(config))
                    write_json(config_path, config)
                fp = stage_fingerprint(stage, config, manifest["completed"], memo)
                old = cached.get(name, {})
                valid = old.get("fingerprint") == fp and artifacts_match(
                    old.get("outputs", {}), base=root, expected=outputs, allow_empty=True)
                if valid:
                    record.update(
                        status="skipped",
                        reason="verified content cache",
                        reused_attempt_id=old.get("attempt_id"),
                    )
                    manifest["completed"][name] = old
                else:
                    print("START", name, flush=True)
                    run_stage(
                        command, root / "logs" / (attempt_id + "_" + name + ".log")
                    )
                    if name == "bake":
                        baked = json.loads((root / "bake_report.json").read_text())
                        outputs = outputs + [v["file"] for v in baked["textures"].values()]
                    hashes = {p: digest(root / p) for p in outputs}
                    manifest["completed"][name] = {"fingerprint": fp, "outputs": hashes, "attempt_id": attempt_id}
                    record["status"] = "completed"
        except BaseException as exc:
            failure = exc
            record.update(
                status=(
                    "waiting" if isinstance(exc, WaitingForRetopology) else "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
                ),
                error=str(exc),
            )
        record.update(
            ended_at=utc_now(),
            elapsed_seconds=time.monotonic() - stage_clock,
            timing_scope="local stage invocation including child compute and wait; cached skips measure validation only",
        )
        records.append(record)
        with (root / "timings.jsonl").open("a") as stream:
            stream.write(json.dumps(record) + "\n")
        write_json(checkpoint, manifest)
        print(
            record["status"].upper(),
            name,
            round(record["elapsed_seconds"], 2),
            flush=True,
        )
    manifest.update(
        status="waiting_retopology" if isinstance(failure, WaitingForRetopology) else "failed" if failure else "completed",
        ended_at=utc_now(),
        elapsed_seconds=time.monotonic() - clock,
    )
    write_json(checkpoint, manifest)
    summary = {
        "task_id": task_id,
        "attempt_id": attempt_id,
        "started_at": started,
        "ended_at": manifest["ended_at"],
        "elapsed_seconds": manifest["elapsed_seconds"],
        "status": manifest["status"],
        "stages": records,
        "scope": "this attempt wall-clock interval; sequential stages are included, not added to the task total",
        "history": "timings.jsonl; one record per stage and attempt; no token usage collected",
    }
    write_json(root / "timing_summary.json", summary)
    if failure:
        raise failure
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config")
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    config = preflight(json.loads(Path(args.config).read_text()))

    def interrupted(signum, frame):
        raise KeyboardInterrupt("Workflow interrupted by signal " + str(signum))

    signal.signal(signal.SIGTERM, interrupted)
    if args.check:
        print("CONFIG_READY")
        return
    try:
        workflow(config, resume=not args.fresh)
    except WaitingForRetopology as exc:
        print(json.dumps({'status': 'waiting_retopology', 'message': str(exc),
                          'plan': str(Path(config['output']) / 'retopology-request.json')}))
        raise SystemExit(3)


if __name__ == "__main__":
    main()
