#!/usr/bin/env python3
"""Compile a reviewed part-module job in Blender; --check runs without bpy."""
import argparse
import ast
import importlib.util
import json
import math
from pathlib import Path
import re
import struct
import sys
import uuid

HERE = Path(__file__).resolve().parent


def load_job(path):
    """Read/validate JSON and module syntax without importing modules or bpy."""
    path = Path(path).resolve()
    job = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(job, dict):
        raise ValueError("Job must be an object")
    allowed = {"name", "modules", "parts", "palette", "axis", "gap", "output_dir", "exports"}
    if set(job) - allowed:
        raise ValueError("Unknown job keys: " + ", ".join(sorted(set(job) - allowed)))
    ident = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
    if not isinstance(job.get("name"), str) or not ident.fullmatch(job["name"]):
        raise ValueError("name must be a 1-64 character file-safe identifier")
    if not isinstance(job.get("parts"), list) or not job["parts"]:
        raise ValueError("parts must be a non-empty ordered list")
    ids = []
    for part in job["parts"]:
        if not isinstance(part, dict) or set(part) != {"id", "label"}:
            raise ValueError("Each part must have exactly id and label")
        if not isinstance(part["id"], str) or not ident.fullmatch(part["id"]):
            raise ValueError("Invalid part id")
        if not isinstance(part["label"], str) or not part["label"].strip():
            raise ValueError("Part label is required")
        ids.append(part["id"])
    if len(ids) != len(set(ids)):
        raise ValueError("Part ids must be unique")
    palette = job.get("palette")
    if not isinstance(palette, dict) or not palette:
        raise ValueError("palette must map material keys to six-digit sRGB hex colors")
    for key, value in palette.items():
        if not key or not isinstance(value, str) or not re.fullmatch(r"#?[0-9a-fA-F]{6}", value):
            raise ValueError("Invalid palette entry")
    modules = job.get("modules")
    if not isinstance(modules, list) or not modules:
        raise ValueError("modules must be a non-empty list of Python file paths")
    resolved = []
    for item in modules:
        if not isinstance(item, str) or not item:
            raise ValueError("Invalid module path")
        module = (path.parent / item).resolve()
        if module.suffix != ".py" or not module.is_file():
            raise ValueError("Missing Python module: " + str(module))
        ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        resolved.append(str(module))
    if len(resolved) != len(set(resolved)):
        raise ValueError("Duplicate modules")
    job["modules"] = resolved
    job["axis"] = job.get("axis", "X")
    if job["axis"] not in ("X", "Y"):
        raise ValueError("axis must be X or Y; Z is the ground-normal axis")
    gap = job.get("gap", 0.5)
    if isinstance(gap, bool) or not isinstance(gap, (int, float)) or not math.isfinite(gap) or gap < 0:
        raise ValueError("gap must be finite and non-negative")
    job["gap"] = gap
    output = job.get("output_dir", "outputs")
    if not isinstance(output, str) or not output:
        raise ValueError("output_dir must be a path string")
    job["output_dir"] = str((path.parent / output).resolve())
    install_dir = HERE.parent.resolve()
    resolved_output = Path(job["output_dir"])
    if resolved_output == install_dir or install_dir in resolved_output.parents:
        raise ValueError("output_dir must be outside the skill package; copy the example to a task directory first")
    exports = job.get("exports", {})
    if not isinstance(exports, dict) or set(exports) - {"whole", "parts"}:
        raise ValueError("exports only accepts whole and parts")
    if any(type(value) is not bool for value in exports.values()):
        raise ValueError("Export flags must be Boolean")
    job["exports"] = {"whole": exports.get("whole", False), "parts": exports.get("parts", False)}
    return job


def layout_offsets(bounds, axis="X", gap=0.5):
    """Pure function: align evaluated bounds to ground and center a row at origin."""
    if axis not in ("X", "Y") or not math.isfinite(gap) or gap < 0:
        raise ValueError("Invalid layout")
    along = 0 if axis == "X" else 1
    across = 1 - along
    cursor, offsets = 0.0, []
    for low, high in bounds:
        if len(low) != 3 or len(high) != 3:
            raise ValueError("Bounds require three coordinates")
        if any(not math.isfinite(v) for v in (*low, *high)) or any(a > b for a, b in zip(low, high)):
            raise ValueError("Invalid bounds")
        offset = [0.0, 0.0, -low[2]]
        offset[along] = cursor - low[along]
        offset[across] = -(low[across] + high[across]) / 2
        offsets.append(offset)
        cursor += high[along] - low[along] + gap
    width = cursor - gap if offsets else 0.0
    for offset in offsets:
        offset[along] -= width / 2
    return offsets


def import_file(path):
    """Execute a reviewed local module. This is code execution, not a sandbox."""
    name = "_multiview_" + uuid.uuid4().hex
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


def verified_file(path, kind):
    """Check on-disk signatures; this does not certify visual quality."""
    path = Path(path)
    data = path.read_bytes()
    if kind == "blend":
        if len(data) <= 12 or not data.startswith(b"BLENDER"):
            raise ValueError("Invalid uncompressed blend file")
    elif kind == "glb":
        if len(data) < 20 or data[:4] != b"glTF":
            raise ValueError("Invalid GLB header")
        version, length, chunk_length, chunk_type = struct.unpack_from("<IIII", data, 4)
        if version != 2 or length != len(data) or chunk_type != 0x4E4F534A or chunk_length > len(data) - 20:
            raise ValueError("Invalid GLB structure")
        document = json.loads(data[20:20 + chunk_length])
        if not document.get("meshes"):
            raise ValueError("GLB contains no meshes")
    else:
        raise ValueError("Unknown file kind")
    return {"path": str(path), "bytes": len(data), "status": "verified_signature"}


def part_bounds(collection, depsgraph):
    """Evaluated world-space bounds, including mesh and bevelled curve objects."""
    from mathutils import Vector
    points = []
    for obj in collection.all_objects:
        if obj.type in {"MESH", "CURVE"}:
            evaluated = obj.evaluated_get(depsgraph)
            if obj.type == "MESH" and not evaluated.data.vertices:
                raise ValueError("Empty evaluated mesh: " + obj.name)
            if obj.type == "CURVE" and not evaluated.data.splines:
                raise ValueError("Empty evaluated curve: " + obj.name)
            points.extend(evaluated.matrix_world @ Vector(corner) for corner in evaluated.bound_box)
    if not points:
        raise ValueError("Part contains no supported geometry: " + collection.name)
    return ([min(p[i] for p in points) for i in range(3)],
            [max(p[i] for p in points) for i in range(3)])


def export_glb(bpy, path, entries, local=False):
    """Export evaluated mesh copies. Preserve source geometry and root transforms."""
    from mathutils import Matrix
    source = bpy.context.window.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    temp = bpy.data.scenes.new("Multiview export")
    created_objects, created_meshes = [], []
    try:
        for collection, root in entries:
            duplicate_root = bpy.data.objects.new(root.name, None)
            temp.collection.objects.link(duplicate_root)
            created_objects.append(duplicate_root)
            duplicate_root.matrix_world = Matrix.Identity(4) if local else root.matrix_world.copy()
            inverse = root.matrix_world.inverted()
            for obj in collection.all_objects:
                if obj.type not in {"MESH", "CURVE"}:
                    continue
                evaluated = obj.evaluated_get(depsgraph)
                mesh = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=depsgraph)
                created_meshes.append(mesh)
                duplicate = bpy.data.objects.new(obj.name, mesh)
                temp.collection.objects.link(duplicate)
                created_objects.append(duplicate)
                duplicate.parent = duplicate_root
                duplicate.matrix_local = inverse @ obj.matrix_world
        bpy.context.window.scene = temp
        for obj in created_objects:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = created_objects[0]
        result = bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=True)
        if "FINISHED" not in result:
            raise RuntimeError("GLB exporter did not finish")
        return verified_file(path, "glb")
    finally:
        bpy.context.window.scene = source
        for obj in created_objects:
            bpy.data.objects.remove(obj, do_unlink=True)
        for mesh in created_meshes:
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        bpy.data.scenes.remove(temp)


def build_modules(ctx, paths, records):
    """Execute reviewed modules and retain success/failure of each attempted module."""
    for path in paths:
        record = {"path": path, "status": "running"}
        records.append(record)
        try:
            module = import_file(path)
            module.build(ctx)
            record["status"] = "built"
        except BaseException as exc:
            record.update(status="failed" if isinstance(exc, Exception) else "interrupted",
                          error=str(exc), error_type=type(exc).__name__)
            raise
    return records


def validate_part_ownership(scene, collections, expected_ids):
    """Check declared parts and exclusive object/parent ownership; return id mapping."""
    actual = {collection["part_id"]: collection for collection in collections}
    if len(actual) != len(collections) or set(actual) != set(expected_ids):
        raise ValueError("Built collections do not match the requested part ids")
    owned = set()
    for collection in collections:
        members = set(collection.all_objects)
        if owned & members:
            raise ValueError("An Object cannot be shared across parts")
        if any(obj.parent is not None and obj.parent not in members for obj in members):
            raise ValueError("Cross-part or external parenting is not supported")
        owned.update(members)
    if set(scene.objects) != owned:
        raise ValueError("Modules created objects outside their declared part collections")
    return actual


def create_part_roots(bpy, collections, ordered_parts):
    """Create one origin root per part without changing child world transforms."""
    entries = []
    for part in ordered_parts:
        collection = collections[part["id"]]
        collection["label"] = part["label"]
        root = bpy.data.objects.new(part["id"] + " | " + part["label"], None)
        collection.objects.link(root)
        root["part_id"] = part["id"]
        for obj in list(collection.all_objects):
            if obj != root and obj.parent is None:
                matrix = obj.matrix_world.copy()
                obj.parent = root
                obj.matrix_world = matrix
        entries.append((collection, root))
    return entries


def apply_layout(bpy, entries, ordered_parts, axis, gap):
    """Translate roots using evaluated bounds and return the resulting inventory."""
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    bounds = [part_bounds(collection, depsgraph) for collection, root in entries]
    for (collection, root), offset in zip(entries, layout_offsets(bounds, axis, gap)):
        root.location = offset
    bpy.context.view_layer.update()
    return [{"id": part["id"], "root": root.name, "translation": list(root.location),
             "bounds": part_bounds(collection, depsgraph)}
            for part, (collection, root) in zip(ordered_parts, entries)]


def save_scene(bpy, scene, path):
    """Save only the task scene, preserve the current file path, check its signature."""
    bpy.data.libraries.write(str(path), {scene}, path_remap="RELATIVE_ALL",
                            fake_user=True, compress=False)
    return verified_file(path, "blend")


def export_part_files(bpy, directory, ordered_parts, entries):
    """Yield each confirmed artifact; earlier yields survive a later part failure."""
    directory = Path(directory)
    directory.mkdir()
    for part, entry in zip(ordered_parts, entries):
        yield export_glb(bpy, directory / (part["id"] + ".glb"), [entry], local=True)


def restore_context(bpy, scene, view_layer):
    """Restore the user's active scene and layer without depending on logging."""
    bpy.context.window.scene = scene
    bpy.context.window.view_layer = view_layer


def _identifier(value, label):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value):
        raise ValueError(label + " must be a 1-128 character identifier")
    return value


def run_job(job_path, mode="preview", *, task_id=None, previous_attempt_id=None):
    """Orchestrate atomic phases, measure them, preserve the user's active scene."""
    from datetime import datetime, timezone
    import time
    start_at = datetime.now(timezone.utc).isoformat()
    start_clock = time.monotonic()
    if mode not in {"preview", "deliver"}:
        raise ValueError("mode must be preview or deliver")
    job = load_job(job_path)
    task_id = _identifier(task_id or uuid.uuid5(uuid.NAMESPACE_URL, Path(job_path).resolve().as_uri()).hex, "task_id")
    if previous_attempt_id is not None:
        _identifier(previous_attempt_id, "previous_attempt_id")
    preflight_end = datetime.now(timezone.utc).isoformat()
    preflight_elapsed = time.monotonic() - start_clock
    attempt_id = uuid.uuid4().hex
    out = Path(job["output_dir"]) / (job["name"] + "-" + attempt_id[:10])
    out.mkdir(parents=True, exist_ok=False)
    timing_module = import_file(HERE / "timing.py")
    recorder = timing_module.StageRecorder(out, task_id, attempt_id, previous_attempt_id,
                                          started_at=start_at, started_clock=start_clock)
    recorder.add_record({"stage": "preflight", "status": "completed", "started_at": start_at,
                         "ended_at": preflight_end, "elapsed_seconds": preflight_elapsed,
                         "timing_method": "monotonic"})
    report_path = out / "report.json"
    report = {"schema": 2, "skill": "multiview-parts", "task_id": task_id, "attempt_id": attempt_id,
              "previous_attempt_id": previous_attempt_id, "mode": mode, "job": job,
              "status": "running", "execution_status": "running", "modules": [], "artifacts": [],
              "exports": {"status": "pending" if mode == "deliver" and any(job["exports"].values()) else "skipped"},
              "checks": {"structure": "not_performed", "file_signatures": "not_performed",
                         "roundtrip": "not_performed", "visual": "not_performed"},
              "visual_review": "not_performed", "report_path": str(report_path),
              "timings_path": str(out / "timings.jsonl"),
              "timing_summary_path": str(out / "timing_summary.json"),
              "timing_scope": "automatic pipeline only; caller records image analysis, specification and visual review separately"}
    timing_module.write_json(report_path, report)
    bpy = old_scene = old_layer = None
    interrupted = None
    visited = {"preflight"}
    automatic = ("runtime", "build", "structure", "layout", "save", "export_parts", "export_row")
    try:
        visited.add("runtime")
        with recorder.stage("runtime"):
            import bpy
            if bpy.context.window is None:
                raise RuntimeError("A Blender window context is required, including background mode")
            if bpy.context.mode != "OBJECT":
                raise RuntimeError("Switch Blender to Object Mode before running; user edit state is preserved")
            old_scene, old_layer = bpy.context.window.scene, bpy.context.window.view_layer
            report["blender_version"] = bpy.app.version_string

        visited.add("build")
        with recorder.stage("build"):
            scene = bpy.data.scenes.new(job["name"])
            bpy.context.window.scene = scene
            ctx = import_file(HERE / "geometry.py").Context(scene, job["palette"])
            build_modules(ctx, job["modules"], report["modules"])

        visited.add("structure")
        with recorder.stage("structure"):
            collections = validate_part_ownership(scene, ctx.parts, [p["id"] for p in job["parts"]])
            entries = create_part_roots(bpy, collections, job["parts"])

        visited.add("layout")
        with recorder.stage("layout"):
            report["parts"] = apply_layout(bpy, entries, job["parts"], job["axis"], job["gap"])
            report["checks"]["structure"] = "passed"

        visited.add("save")
        with recorder.stage("save"):
            report["artifacts"].append(save_scene(bpy, scene, out / (job["name"] + ".blend")))
            report["checks"]["file_signatures"] = "partial"
            report["status"] = "saved"

        for key, stage_name in (("parts", "export_parts"), ("whole", "export_row")):
            visited.add(stage_name)
            if mode != "deliver" or not job["exports"][key]:
                recorder.skip(stage_name, "preview mode or export not requested")
                continue
            with recorder.stage(stage_name):
                report["exports"]["status"] = "running"
                if key == "parts":
                    report["artifacts"].extend(export_part_files(bpy, out / "parts", job["parts"], entries))
                else:
                    report["artifacts"].append(export_glb(bpy, out / (job["name"] + "-row.glb"), entries))
                report["exports"]["status"] = "exported"

        report["checks"]["file_signatures"] = "passed"
        report["status"] = "preview_ready" if mode == "preview" else "delivered"
        report["execution_status"] = "completed"
    except BaseException as exc:
        state = "failed" if isinstance(exc, Exception) else "interrupted"
        report.update(status=state, execution_status=state, error=str(exc), error_type=type(exc).__name__)
        if not isinstance(exc, Exception):
            interrupted = exc
        if report["exports"]["status"] == "running":
            report["exports"]["status"] = state
        elif report["exports"]["status"] == "pending":
            report["exports"]["status"] = "skipped"
    finally:
        def cleanup_problem(kind, stage, exc):
            nonlocal interrupted
            report.setdefault(kind, []).append({"stage": stage, "error": str(exc),
                                                "error_type": type(exc).__name__})
            if interrupted is None:
                state = "failed" if isinstance(exc, Exception) else "interrupted"
                report.update(status=state, execution_status=state)
                if not isinstance(exc, Exception):
                    interrupted = exc

        for stage_name in automatic:
            if stage_name not in visited:
                try:
                    recorder.skip(stage_name, "upstream failure or interruption; not executed")
                except BaseException as exc:
                    cleanup_problem("timing_error", stage_name, exc)
        restoration_started = restoration_finished = False
        try:
            if old_scene is not None:
                with recorder.stage("restore_context"):
                    restoration_started = True
                    restore_context(bpy, old_scene, old_layer)
                    restoration_finished = True
                    report["context_restore"] = "completed"
            else:
                recorder.skip("restore_context", "no user scene was changed")
                report["context_restore"] = "not_required"
        except BaseException as exc:
            kind = "cleanup_error" if restoration_started and not restoration_finished else "timing_error"
            cleanup_problem(kind, "restore_context", exc)
            if old_scene is not None and not restoration_started:
                # A failed journal start must never block restoration itself.
                try:
                    restore_context(bpy, old_scene, old_layer)
                    report["context_restore"] = "completed"
                except BaseException as restore_error:
                    report["context_restore"] = "failed"
                    cleanup_problem("cleanup_error", "restore_context", restore_error)
            elif restoration_started and not restoration_finished:
                report["context_restore"] = "failed"
        try:
            report["timing"] = recorder.finish(report["execution_status"])
        except BaseException as exc:
            cleanup_problem("timing_error", "attempt_summary", exc)
        try:
            timing_module.write_json(report_path, report)
        except BaseException as exc:
            if interrupted is None:
                raise
            if hasattr(interrupted, "add_note"):
                interrupted.add_note("Could not persist the final task report: " + type(exc).__name__)
    if interrupted is not None:
        raise interrupted
    return report


def describe():
    """Machine-readable description of this skill's existing public call surface."""
    import inspect
    names = ("load_job", "layout_offsets", "verified_file", "build_modules",
             "validate_part_ownership", "create_part_roots", "apply_layout",
             "save_scene", "export_glb", "export_part_files", "restore_context", "run_job")
    return {"schema": 1, "skill": "multiview-parts", "entrypoint": "scripts/run.py",
            "legacy_entrypoint": "scripts/parts_pipeline.py",
            "config_argument": "config.json or --job config.json",
            "modes": ["preview", "deliver"], "check_flag": "--check",
            "report": "report.json", "report_schema": 2,
            "execution_statuses": ["running", "completed", "failed", "interrupted"],
            "timings": ["timings.jsonl", "timing_summary.json"],
            "geometry_route": "GPT-authored build(ctx) modules; images interpreted by the caller",
            "functions": [{"name": name, "signature": str(inspect.signature(globals()[name])),
                           "description": inspect.getdoc(globals()[name])} for name in names]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", nargs="?", help="Job JSON, relative paths resolved from this file")
    parser.add_argument("--job", help="Compatible named form of the job JSON argument")
    parser.add_argument("--mode", choices=("preview", "deliver"), default="preview")
    parser.add_argument("--check", action="store_true", help="Validate config and module syntax only; no bpy, module execution or writes")
    parser.add_argument("--describe", action="store_true", help="Print the callable interface as JSON; no bpy or task required")
    parser.add_argument("--task-id", help="Explicit task identity; default is stable for the absolute job path")
    parser.add_argument("--previous-attempt-id", help="Link an earlier attempt; this does not reuse geometry or caches")
    args = parser.parse_args(argv)
    if args.describe:
        if args.config or args.job or args.check or args.task_id or args.previous_attempt_id:
            parser.error("--describe cannot be combined with a task")
        print(json.dumps(describe(), ensure_ascii=False, indent=2))
        return 0
    if bool(args.config) == bool(args.job):
        parser.error("Provide exactly one config path, positional or --job")
    path = args.config or args.job
    try:
        if args.check:
            result = {"schema": 2, "skill": "multiview-parts", "status": "config_valid",
                      "execution_status": "completed", "job": load_job(path), "blender_run": False}
            if args.task_id:
                _identifier(args.task_id, "task_id")
            if args.previous_attempt_id:
                _identifier(args.previous_attempt_id, "previous_attempt_id")
        else:
            result = run_job(path, args.mode, task_id=args.task_id, previous_attempt_id=args.previous_attempt_id)
    except KeyboardInterrupt:
        result = {"schema": 2, "skill": "multiview-parts", "status": "interrupted",
                  "execution_status": "interrupted", "error": "Interrupted; see task report when created"}
    except Exception as exc:
        result = {"schema": 2, "skill": "multiview-parts", "status": "failed",
                  "execution_status": "failed", "error": str(exc), "error_type": type(exc).__name__}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 130 if result.get("execution_status") == "interrupted" else (1 if result.get("execution_status") == "failed" else 0)


if __name__ == "__main__":
    arguments = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    raise SystemExit(main(arguments))
