"""Resumable head/hair workflow; image generation is an explicit host handoff."""
import argparse
import json
import math
from pathlib import Path
import sys
import uuid
from checkpoints import digest
from path_safety import validate_write_roots
from process_run import BudgetTimeout, run_budgeted, run_checked, write_heartbeat
from timing import StageRecorder, write_json
from tool_result import tool_result

SCRIPTS = Path(__file__).resolve().parent
PACKAGE = SCRIPTS.parent
DEPENDENCIES = {
    "prepare": ["render_reference.py", "execute.py", "asset_scene.py", "scene_io.py", "render_engine.py"],
    "html": ["build_html.py", "graphcut.py", "label_texture.py", "partition.py", "apply_labels.py", "glb_clips.py"],
    "split": ["split_worker.py", "graphcut.py", "label_texture.py", "partition.py", "apply_labels.py", "glb_clips.py"],
}


def fingerprint(stage, inputs, parameters):
    sources = DEPENDENCIES[stage] + ["workflow.py", "process_run.py", "timing.py", "checkpoints.py", "path_safety.py", "tool_result.py"]
    if stage == "prepare":
        inputs = dict(inputs, prompt=PACKAGE/"references/label-prompt.txt")
    if stage == "html":
        sources += ["../assets/viewer/" + name for name in (
            "page.html", "app.js", "cut.js", "fbx.js", "worker.js", "three.min.js", "OrbitControls.js", "LICENSE-three.txt")]
    return {"schema": 1, "inputs": {k: digest(v) for k,v in inputs.items()},
            "parameters": parameters, "sources": {name: digest(SCRIPTS/name) for name in sources}}


def cached(stage, expected):
    marker = stage / "complete.json"
    if not marker.exists():
        if stage.exists():
            raise ValueError("Incomplete local stage retained; inspect it and choose a new run directory")
        return False
    record = json.loads(marker.read_text())
    if record["fingerprint"] != expected:
        raise ValueError("Inputs, settings or code changed; use a new local run directory with existing label mesh")
    if not record.get("artifacts"):
        raise ValueError("Empty cache manifest")
    for relative, checksum in record["artifacts"].items():
        path = stage / relative
        if not path.is_file() or digest(path) != checksum:
            raise ValueError("Cached artifact missing or changed")
    return True


def publish(stage, key):
    artifacts = {str(p.relative_to(stage)): digest(p) for p in sorted(stage.rglob("*"))
                 if p.is_file() and p.name not in ("complete.json", "process.log", "heartbeat.json")}
    write_json(stage / "complete.json", {"fingerprint": key, "artifacts": artifacts})


def bounded(command, stage, seconds):
    write_json(stage / "budget.json", {"max_wall_seconds": seconds, "automatic_retry": False})
    # Present before the child starts, not only after Popen.
    write_heartbeat(stage / "heartbeat.json", status="running", phase="prepared",
                    elapsed_s=0, budget_s=seconds, heartbeat_s=5)
    try:
        run_budgeted(command, stage/"process.log", max_wall_seconds=seconds,
                     heartbeat_path=stage/"heartbeat.json")
    except BudgetTimeout as exc:
        # StageRecorder classifies SystemExit as interrupted, not failed.
        raise SystemExit(3) from exc


def local(args, recorder):
    if args.command == "split" and (not getattr(args, "confirmed_cut", False) or args.threshold is None):
        raise ValueError("Deliver workflow.py html first. Agent-side cut requires an explicit user request, --confirmed-cut and --threshold.")
    stage = args.run_dir / {"prepare": "01_front_render", "html": "03_interactive", "split": "04_split"}[args.command]
    inputs = {"mesh": args.mesh}
    params = {"max_seconds": args.max_seconds}
    if args.command in ("html", "split"):
        inputs["label_mesh"] = args.label_mesh
        params.update(threshold=args.threshold, tolerance=args.tolerance)
    else:
        inputs["blender"] = args.blender
        params["front"] = "+Z in Y-up GLB, imported as Blender -Y"
    validate_write_roots({"stage": stage}, package_root=PACKAGE, protected_inputs=inputs.values())
    key = fingerprint(args.command, inputs, params)
    if cached(stage, key):
        recorder.skip(args.command, "Validated input/source/parameter and output hashes")
        write_json(args.run_dir / "tool_result.json", tool_result(status="skipped",
            summary="Validated existing local outputs; no new artifact trace",
            next_checkpoint={"prepare": "label", "html": "handoff", "split": "review"}[args.command]))
        return
    stage.mkdir(parents=True)
    with recorder.stage(args.command):
        if args.command == "prepare":
            command = [str(args.blender), "--background", "--factory-startup", "--disable-autoexec",
                "--python-exit-code", "1", "--python", str(SCRIPTS/"execute.py"), "--",
                "--script", str(SCRIPTS/"render_reference.py"), "--",
                str(args.mesh), str(stage/"front.png"), str(stage/"camera.json")]
            bounded(command, stage, args.max_seconds)
            from PIL import Image
            with Image.open(stage/"front.png") as im:
                rgba = im.convert("RGBA")
            white = Image.new("RGBA", rgba.size, (255,255,255,255))
            white.alpha_composite(rgba)
            white.convert("RGB").save(stage/"front.png")
            (stage/"prompt.txt").write_text((PACKAGE/"references/label-prompt.txt").read_text())
        elif args.command == "html":
            command = [sys.executable, str(SCRIPTS/"build_html.py"), "--source", str(args.mesh),
                "--label-mesh", str(args.label_mesh), "--output", str(stage/"result"),
                "--tolerance", str(args.tolerance)]
            if args.threshold is not None:
                command += ["--threshold", str(args.threshold)]
            bounded(command, stage, args.max_seconds)
        else:
            command = [sys.executable, str(SCRIPTS/"split_worker.py"), "--source", str(args.mesh),
                "--label-mesh", str(args.label_mesh), "--output", str(stage/"result"),
                "--tolerance", str(args.tolerance), "--confirmed-cut"]
            if args.threshold is not None:
                command += ["--threshold", str(args.threshold)]
            bounded(command, stage, args.max_seconds)
        publish(stage, key)
    if args.command == "prepare":
        slots = [("image", stage/"front.png"), ("camera", stage/"camera.json"), ("prompt", stage/"prompt.txt")]
        task, following = "reference", "label"
    elif args.command == "html":
        slots = [("html", stage/"result/head-hair-split.html"), ("manifest", stage/"result/manifest.json")]
        task, following = "html", "handoff"
    else:
        slots = [(name, stage/"result/parts"/file) for name,file in (
            ("head","head_textured.glb"),("hair","hair_textured.glb"),
            ("combined","head_hair_textured.glb"),("report","report.json"),
            ("labels","source_face_labels.npy"))]
        slots.append(("cut",stage/"result/graphcut.json"))
        task, following = "split", "review"
    summary = "HTML ready: provide the link, open it, then wait for user interaction; no mincut was executed." if args.command == "html" else "Local stage complete; visual acceptance remains separate"
    result = tool_result(status="ok", summary=summary,
        artifacts=[{"task":task,"output":name,"path":str(path),"sha256":digest(path)} for name,path in slots],
        next_checkpoint=following)
    write_json(args.run_dir/"tool_result.json", result)
    print(json.dumps(result))


def api_command(args):
    """Compose only; actual transport/authentication remains the independent tool."""
    script = args.api_dir / "scripts/hi3d_api.py"
    if not script.is_file():
        raise FileNotFoundError("Explicit, materialized public Hi3D API package required")
    protected = [getattr(args, name) for name in ("mesh", "label_image") if hasattr(args, name)]
    roots = {"job": args.job}
    if hasattr(args, "output"):
        roots["output"] = args.output
        protected.append(args.job)
        # Validate download independently so the existing job remains read-only.
        validate_write_roots({"output": args.output}, package_root=PACKAGE, protected_inputs=protected)
        roots = {"job": args.job}
        protected.remove(args.job)
    validate_write_roots(roots, package_root=PACKAGE, protected_inputs=protected)
    command = [sys.executable, str(script)]
    if args.command in ("plan", "submit"):
        command += ["submit", "model", "--mesh", str(args.mesh), "--image", str(args.label_image),
                    "--job", str(args.job)]
        for item in ("request_type=2", "model=hi3dv3.0", "resolution="+args.resolution,
                     "pbr=0", "shading=1.0", "format=glb"):
            command += ["--set", item]
        if args.command == "plan":
            command += ["--dry-run"]
        elif args.session:
            command += ["--session", str(args.session)]
    else:
        command += [args.command, "--job", str(args.job)]
        if not args.job.is_file():
            raise FileNotFoundError("Resume the original job; do not create a replacement submission")
        if args.command == "wait":
            command += ["--seconds", "50", "--interval", "20"]
        if args.command == "download":
            command += ["--out", str(args.output)]
    return command


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("prepare", "html", "split", "plan", "submit", "query", "wait", "download"):
        q = sub.add_parser(name)
        q.add_argument("--run-dir", required=True, type=Path)
        if name in ("prepare","html","split","plan","submit"):
            q.add_argument("--mesh", required=True, type=Path)
        if name in ("prepare","html","split"):
            q.add_argument("--max-seconds", type=float, default=300)
            q.add_argument("--confirm-budget", action="store_true")
        if name == "prepare":
            q.add_argument("--blender", required=True, type=Path)
        elif name in ("html", "split"):
            q.add_argument("--label-mesh", required=True, type=Path)
            q.add_argument("--threshold", type=float, required=name == "split")
            q.add_argument("--tolerance", type=float, default=1e-6)
            if name == "split":
                q.add_argument("--confirmed-cut", action="store_true", required=True,
                               help="Only after the user explicitly asks the agent to execute the cut")
        else:
            q.add_argument("--api-dir", required=True, type=Path)
            q.add_argument("--job", required=True, type=Path)
            if name in ("plan","submit"):
                q.add_argument("--label-image", required=True, type=Path)
                q.add_argument("--resolution", choices=["2048quality","2048master"], default="2048quality")
                q.add_argument("--session", type=Path,
                               help="Optional task pcg.session.v1 with already selected Hi3D parameters")
            elif name == "download":
                q.add_argument("--output", required=True, type=Path)
    return p


def main():
    args = parser().parse_args()
    for key, value in vars(args).items():
        if isinstance(value, Path):
            setattr(args, key, value.resolve())
    # Task root can contain earlier artifacts; never write in the installed package.
    validate_write_roots({"run": args.run_dir}, package_root=PACKAGE)
    protected = [getattr(args, key) for key in ("mesh","label_mesh","label_image","job") if hasattr(args,key)]
    validate_write_roots({name: args.run_dir/name for name in ("timings.jsonl","timing_summary.json","tool_result.json")},
                         package_root=PACKAGE, protected_inputs=protected)
    if args.command in ("prepare","html","split"):
        if not math.isfinite(args.max_seconds) or args.max_seconds <= 0:
            raise ValueError("Finite positive budget required")
        if args.max_seconds > 300 and not args.confirm_budget:
            raise SystemExit("Medium/high budget requires user choice and --confirm-budget")
    command = None if args.command in ("prepare","html","split") else api_command(args)
    previous_path = args.run_dir / "timing_summary.json"
    previous = json.loads(previous_path.read_text()).get("attempt_id") if previous_path.exists() else None
    recorder = StageRecorder(args.run_dir, args.run_dir.name, uuid.uuid4().hex,
                             previous_attempt_id=previous)
    status = "completed"
    try:
        if command is None:
            local(args, recorder)
        else:
            with recorder.stage(args.command):
                run_checked(command)
    except BaseException as exc:
        status = "interrupted" if isinstance(exc, (SystemExit,KeyboardInterrupt)) else "failed"
        raise
    finally:
        recorder.finish(status)


if __name__ == "__main__":
    main()
