"""Blender scene inspection, local trajectory compilation and camera baking."""

import argparse
import datetime
import json
import math
import pathlib
import sys
import time

import bpy
from mathutils import Matrix, Quaternion, Vector


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value, label, positive=False):
    require(isinstance(value, (int, float)) and not isinstance(value, bool), label + ": expected a number")
    require(math.isfinite(value), label + ": must be finite")
    require(not positive or value > 0, label + ": must be positive")
    return float(value)


def vector(value, label):
    require(isinstance(value, list) and len(value) == 3, label + ": expected [x,y,z]")
    return Vector([number(component, label) for component in value])


def quaternion(value, label):
    require(isinstance(value, list) and len(value) == 4, label + ": expected [w,x,y,z]")
    result = Quaternion([number(component, label) for component in value])
    require(abs(result.magnitude - 1.0) < 0.0001, label + ": quaternion must have unit length")
    result.normalize()
    return result


def input_path(root, value):
    candidate = pathlib.Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve(strict=True)
    require(resolved.is_relative_to(root) and resolved.is_file(), "Input must be a regular file inside workspace")
    require(resolved.stat().st_nlink == 1, "Copy hard-linked input to an independent workspace file first")
    return resolved


def output_path(root, value, suffix):
    candidate = pathlib.Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    require(resolved.is_relative_to(root / "exports"), "Output must be inside workspace/exports")
    require(resolved.name.startswith("hi3d-") and resolved.suffix.lower() == suffix, "Output requires hi3d- prefix and " + suffix)
    require(not candidate.is_symlink() and not resolved.exists(), "Output already exists or is a symbolic link; use a new take")
    return resolved


def read_json(path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def load_scene(path):
    suffix = path.suffix.lower()
    if suffix == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False, use_scripts=False)
    elif suffix in {".glb", ".gltf"}:
        if suffix == ".gltf":
            for collection in ("buffers", "images"):
                for entry in read_json(path).get(collection, []):
                    uri = entry.get("uri", "")
                    if uri and not uri.startswith("data:"):
                        require(":" not in uri and not uri.startswith(("/", "\\")), "GLTF resource must use a local relative URI")
                        resource = (path.parent / uri).resolve(strict=True)
                        require(resource.is_relative_to(path.parent), "GLTF resource escapes input directory")
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(path))
        bpy.context.scene.unit_settings.system = "METRIC"
        bpy.context.scene.unit_settings.scale_length = 1.0
    else:
        raise ValueError("Scene input must be .blend, .glb or .gltf")
    return bpy.context.scene


def scene_scale(scene, source, override=None):
    if override is not None:
        return number(override, "scale override", positive=True), "verified", "explicit_calibration_required"
    if source.suffix.lower() in {".glb", ".gltf"}:
        return 1.0, "verified", "gltf_meter_convention"
    scale = number(scene.unit_settings.scale_length, "scene scale", positive=True)
    status = "unverified" if scene.unit_settings.system == "NONE" else "verified"
    return scale, status, "blender_unit_settings"


def inspect_scene(root, arguments):
    source = input_path(root, arguments.input)
    output = output_path(root, arguments.output, ".json")
    scene = load_scene(source)
    scale, status, evidence = scene_scale(scene, source, arguments.scale_m_per_unit)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    objects = []
    cameras = []
    for item in sorted(scene.objects, key=lambda item: item.name):
        evaluated = item.evaluated_get(depsgraph)
        entry = {
            "id": item.name,
            "type": item.type,
            "parent": item.parent.name if item.parent else None,
            "hidden_render": bool(item.hide_render),
            "has_animation": bool(item.animation_data or getattr(item.data, "animation_data", None)),
            "has_constraints": bool(item.constraints),
        }
        if item.type in {"MESH", "CURVE", "SURFACE", "META", "FONT"}:
            corners = [evaluated.matrix_world @ Vector(corner) for corner in evaluated.bound_box]
            entry["bounds_m"] = {
                "min": [min(corner[axis] for corner in corners) * scale for axis in range(3)],
                "max": [max(corner[axis] for corner in corners) * scale for axis in range(3)],
            }
        objects.append(entry)
        if item.type == "CAMERA":
            cameras.append({
                "id": item.name,
                "camera_type": item.data.type,
                "position_m": list(evaluated.matrix_world.translation * scale),
                "quaternion_wxyz": list(evaluated.matrix_world.to_quaternion()),
                "focal_mm": item.data.lens,
                "sensor_width_mm": item.data.sensor_width,
            })
    write_json(output, {
        "schema_version": 1,
        "coordinate_system": "blender_zup",
        "unit": "meter",
        "scale_m_per_blender_unit": scale,
        "scale_status": status,
        "scale_evidence": evidence,
        "source": source.relative_to(root).as_posix(),
        "frame_start": scene.frame_start,
        "frame_end": scene.frame_end,
        "evaluated_frame": scene.frame_current,
        "fps": scene.render.fps / scene.render.fps_base,
        "objects": objects,
        "cameras": cameras,
        "limitations": ["instances_not_expanded", "single_evaluated_time", "bounds_are_not_free_space", "not_a_native_CinemaTraj_scene_graph"],
    })


def header(data):
    require(data.get("schema_version") == 1, "Unsupported schema_version")
    require(data.get("coordinate_system") == "blender_zup" and data.get("unit") == "meter", "Expected Blender Z-up coordinates in meters")
    require(data.get("scale_status") == "verified", "Physical scene scale must be verified before compile/bake")
    result = {key: data[key] for key in ("schema_version", "coordinate_system", "unit", "scale_status")}
    result["scale_m_per_blender_unit"] = number(data["scale_m_per_blender_unit"], "scale", positive=True)
    result["fps"] = number(data.get("fps", 24), "fps", positive=True)
    require(1 <= result["fps"] <= 240, "fps must be in the bridge range 1..240")
    resolution = data.get("resolution", [1280, 720])
    require(isinstance(resolution, list) and len(resolution) == 2, "resolution must contain two integers")
    require(all(type(dimension) is int and 0 < dimension <= 16384 for dimension in resolution), "Invalid resolution")
    result["resolution"] = resolution
    result["sensor_width_mm"] = number(data.get("sensor_width_mm", 36), "sensor width", positive=True)
    result["clip_start_m"] = number(data.get("clip_start_m", 0.05), "near clip", positive=True)
    result["clip_end_m"] = number(data.get("clip_end_m", 1000), "far clip", positive=True)
    require(result["clip_end_m"] > result["clip_start_m"], "Far clip must exceed near clip")
    result["camera_name"] = data.get("camera_name", "Hi3D_Camera_Take01")
    require(isinstance(result["camera_name"], str) and bool(result["camera_name"].strip()), "Invalid camera name")
    result["backend"] = data.get("backend", "local_parametric")
    require(result["backend"] in {"local_parametric", "gendop_candidate", "cinematraj_native"}, "Unknown backend")
    result["scene_frame_start"] = data.get("scene_frame_start", 1)
    require(type(result["scene_frame_start"]) is int, "scene_frame_start must be an integer")
    limits = data.get("limits", {})
    require(isinstance(limits, dict), "limits must be an object")
    supported_limits = {"max_speed_m_s", "max_acceleration_m_s2", "max_angular_speed_deg_s", "max_angular_acceleration_deg_s2", "max_focal_rate_mm_s"}
    require(set(limits).issubset(supported_limits), "Unknown motion limit")
    result["limits"] = {key: number(value, key, positive=True) for key, value in limits.items()}
    for optional in ("source", "scale_evidence", "notes", "generation_method"):
        if optional in data:
            result[optional] = data[optional]
    return result


def look_rotation(position, target):
    direction = target - position
    require(direction.length > 0.000001, "Camera coincides with look-at target")
    direction.normalize()
    require(abs(direction.z) < 0.9999, "Vertical look-at needs an explicitly authored continuous quaternion trajectory")
    right = direction.cross(Vector((0, 0, 1))).normalized()
    up = right.cross(direction).normalized()
    return Matrix((right, up, -direction)).transposed().to_quaternion().normalized()


def aligned_start(position, rotation, target):
    expected = look_rotation(position, target)
    angle = math.degrees(2 * math.acos(min(1.0, abs(rotation.dot(expected)))))
    require(angle < 0.5, "Look-at would jump at a segment boundary; add an explicit orientation transition")


def make_sample(frame, fps, position, rotation, focal, previous=None):
    rotation = rotation.normalized()
    if previous is not None and previous.dot(rotation) < 0:
        rotation.negate()
    return {
        "frame": frame,
        "t": (frame - 1) / fps,
        "position_m": list(position),
        "quaternion_wxyz": list(rotation),
        "focal_mm": focal,
    }


def compile_plan(root, arguments):
    plan = read_json(input_path(root, arguments.plan))
    output = output_path(root, arguments.output, ".json")
    result = header(plan)
    require(result["backend"] == "local_parametric", "compile implements local_parametric only, not a learned model")
    initial = plan["initial"]
    position = vector(initial["position_m"], "initial position")
    require(("quaternion_wxyz" in initial) != ("target_m" in initial), "initial requires exactly one target_m or quaternion_wxyz")
    rotation = quaternion(initial["quaternion_wxyz"], "initial quaternion") if "quaternion_wxyz" in initial else look_rotation(position, vector(initial["target_m"], "initial target"))
    focal = number(initial.get("focal_mm", 35), "initial focal", positive=True)
    fps = result["fps"]
    samples = [make_sample(1, fps, position, rotation, focal)]
    segments = plan.get("segments")
    require(isinstance(segments, list) and bool(segments), "At least one segment is required")
    summaries = []
    identifiers = set()
    fields = {
        "move": {"end_position_m", "control1_m", "control2_m", "target_m", "end_quaternion_wxyz"},
        "dolly": {"target_m", "end_ratio"},
        "orbit": {"center_m", "angle_deg", "end_height_m"},
        "pan": {"angle_deg"}, "tilt": {"angle_deg"}, "roll": {"angle_deg"},
        "zoom": set(), "hold": set(),
    }
    common = {"id", "op", "duration_s", "end_focal_mm", "intent", "target_object"}
    for segment in segments:
        operation = segment.get("op")
        require(operation in fields, "Unsupported local operation: " + str(operation))
        require(set(segment).issubset(fields[operation] | common), "Unknown fields in " + operation)
        identifier = segment.get("id")
        require(isinstance(identifier, str) and identifier and identifier not in identifiers, "Each segment needs a unique id")
        identifiers.add(identifier)
        intervals = max(1, round(number(segment["duration_s"], "segment duration", positive=True) * fps))
        require(len(samples) + intervals <= 200000, "Trajectory exceeds bridge sample limit")
        start_position, start_rotation, start_focal = position.copy(), rotation.copy(), focal
        end_focal = number(segment.get("end_focal_mm", focal), "end focal", positive=True)
        if operation == "zoom":
            require("end_focal_mm" in segment, "zoom requires end_focal_mm")
        target = None
        center = None
        controls = None
        end_rotation = None
        end_position = start_position.copy()
        if operation in {"move", "dolly"} and "target_m" in segment:
            target = vector(segment["target_m"], "target")
            aligned_start(start_position, start_rotation, target)
        if operation == "move":
            end_position = vector(segment["end_position_m"], "end position")
            require(("control1_m" in segment) == ("control2_m" in segment), "Bézier controls must be supplied together")
            if "control1_m" in segment:
                controls = (vector(segment["control1_m"], "control1"), vector(segment["control2_m"], "control2"))
            if "end_quaternion_wxyz" in segment:
                require(target is None, "move cannot combine target_m and end_quaternion_wxyz")
                end_rotation = quaternion(segment["end_quaternion_wxyz"], "end quaternion")
                if start_rotation.dot(end_rotation) < 0:
                    end_rotation.negate()
        elif operation == "dolly":
            require(target is not None, "dolly requires target_m")
            ratio = number(segment["end_ratio"], "dolly ratio", positive=True)
            end_position = target + (start_position - target) * ratio
        elif operation == "orbit":
            center = vector(segment["center_m"], "orbit center")
            require((start_position - center).xy.length > 0.000001, "Orbit requires a nonzero horizontal radius")
            aligned_start(start_position, start_rotation, center)
            end_height = number(segment.get("end_height_m", start_position.z - center.z), "end height")
        if operation in {"pan", "tilt", "roll", "orbit"}:
            angle = math.radians(number(segment["angle_deg"], "angle"))
        first_frame = len(samples)
        for step in range(1, intervals + 1):
            fraction = step / intervals
            progress = fraction ** 3 * (10 + fraction * (-15 + 6 * fraction))
            position = start_position.lerp(end_position, progress)
            rotation = start_rotation.copy()
            if operation == "move" and controls is not None:
                remaining = 1 - progress
                position = remaining ** 3 * start_position + 3 * remaining ** 2 * progress * controls[0] + 3 * remaining * progress ** 2 * controls[1] + progress ** 3 * end_position
            if operation == "orbit":
                offset = Quaternion((0, 0, 1), angle * progress) @ (start_position - center)
                position = center + offset
                position.z = start_position.z + (center.z + end_height - start_position.z) * progress
                rotation = look_rotation(position, center)
            elif target is not None:
                rotation = look_rotation(position, target)
            elif end_rotation is not None:
                rotation = start_rotation.slerp(end_rotation, progress)
            elif operation == "pan":
                rotation = Quaternion((0, 0, 1), angle * progress) @ start_rotation
            elif operation in {"tilt", "roll"}:
                axis = (1, 0, 0) if operation == "tilt" else (0, 0, -1)
                rotation = start_rotation @ Quaternion(axis, angle * progress)
            focal = start_focal + (end_focal - start_focal) * progress
            samples.append(make_sample(len(samples) + 1, fps, position, rotation, focal, Quaternion(samples[-1]["quaternion_wxyz"])))
        summaries.append({"id": identifier, "op": operation, "frame_start": first_frame, "frame_end": len(samples), "effective_duration_s": intervals / fps})
    result["generation_method"] = "local_quintic_atomic_compiler"
    result["segments"] = summaries
    result["samples"] = samples
    write_json(output, result)


def basic_checks(data):
    metadata = header(data)
    samples = data.get("samples")
    require(isinstance(samples, list) and 2 <= len(samples) <= 200000, "Expected 2..200000 trajectory samples")
    fps = metadata["fps"]
    previous_position = None
    previous_rotation = None
    previous_focal = None
    previous_velocity = None
    previous_angular_velocity = None
    peaks = {"max_speed_m_s": 0.0, "max_acceleration_m_s2": 0.0, "max_angular_speed_deg_s": 0.0, "max_angular_acceleration_deg_s2": 0.0, "max_focal_rate_mm_s": 0.0}
    normalized = []
    for index, sample in enumerate(samples):
        require(type(sample.get("frame")) is int and sample["frame"] == index + 1, "Samples must use consecutive integer frame numbers starting at 1")
        require(abs(number(sample["t"], "sample time") - index / fps) < 0.000001, "Sample time does not match frame/fps")
        position = vector(sample["position_m"], "sample position")
        rotation = quaternion(sample["quaternion_wxyz"], "sample quaternion")
        focal = number(sample["focal_mm"], "sample focal", positive=True)
        if previous_rotation is not None and previous_rotation.dot(rotation) < 0:
            rotation.negate()
        if previous_position is not None:
            velocity = (position - previous_position) * fps
            difference = previous_rotation.rotation_difference(rotation)
            angular_velocity = (previous_rotation @ Vector(difference.axis)) * min(difference.angle, 2 * math.pi - difference.angle) * fps * (180 / math.pi)
            peaks["max_speed_m_s"] = max(peaks["max_speed_m_s"], velocity.length)
            peaks["max_angular_speed_deg_s"] = max(peaks["max_angular_speed_deg_s"], angular_velocity.length)
            peaks["max_focal_rate_mm_s"] = max(peaks["max_focal_rate_mm_s"], abs(focal - previous_focal) * fps)
            if previous_velocity is not None:
                peaks["max_acceleration_m_s2"] = max(peaks["max_acceleration_m_s2"], (velocity - previous_velocity).length * fps)
                peaks["max_angular_acceleration_deg_s2"] = max(peaks["max_angular_acceleration_deg_s2"], (angular_velocity - previous_angular_velocity).length * fps)
            previous_velocity, previous_angular_velocity = velocity, angular_velocity
        normalized.append(make_sample(index + 1, fps, position, rotation, focal))
        previous_position, previous_rotation, previous_focal = position, rotation, focal
    limits = metadata["limits"]
    violations = [{"metric": key, "actual": peaks[key], "limit": threshold} for key, threshold in limits.items() if peaks[key] > threshold + 0.00001]
    report = {
        "schema_version": 1,
        "basic_status": "failed" if violations else "passed",
        "scope": "numeric_motion_only",
        "scene_acceptance": "not_checked",
        "sample_count": len(normalized),
        "last_sample_time_s": (len(normalized) - 1) / fps,
        "encoded_duration_if_all_samples_s": len(normalized) / fps,
        "fps": fps,
        "peaks": peaks,
        "limits": limits,
        "violations": violations,
        "checks": {key: "not_checked" for key in ("collision", "clearance", "swept_volume", "occlusion", "composition", "dynamic_geometry", "resource_portability", "reopen_preview")},
        "limitations": ["Angular acceleration is a finite-difference diagnostic, not an analytic SO(3) acceleration guarantee", "No motion limits means numeric validity only, not accepted film motion"],
    }
    return metadata, normalized, report


def linear_action(action):
    curves = list(getattr(action, "fcurves", ()))
    if not curves:
        for layer in getattr(action, "layers", ()):
            for strip in layer.strips:
                for bag in getattr(strip, "channelbags", ()):
                    curves.extend(bag.fcurves)
    require(bool(curves), "Unsupported Blender action layout; no keyframe interpolation changed")
    for curve in curves:
        for point in curve.keyframe_points:
            point.interpolation = "LINEAR"


def bake_camera(root, arguments):
    started = time.monotonic()
    source = input_path(root, arguments.input)
    trajectory = input_path(root, arguments.trajectory)
    output = output_path(root, arguments.output, ".blend")
    report_path = output_path(root, arguments.report, ".json")
    data = read_json(trajectory)
    metadata, samples, report = basic_checks(data)
    report["backend"] = metadata["backend"]
    report["created_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if report["basic_status"] == "failed":
        report["elapsed_seconds"] = time.monotonic() - started
        write_json(report_path, report)
        raise ValueError("Motion limit failed; basic report written, no scene output created")
    scene = load_scene(source)
    scale = metadata["scale_m_per_blender_unit"]
    stored_scale, stored_status, evidence = scene_scale(scene, source)
    if stored_status == "verified":
        require(abs(stored_scale - scale) <= 0.000001 * max(1, scale), "Trajectory scale disagrees with scene units")
    report["scene_scale_status"] = stored_status
    report["scene_scale_source"] = evidence
    name = metadata["camera_name"]
    require(bpy.data.objects.get(name) is None and bpy.data.cameras.get(name) is None, "Camera name already exists; keep original cameras and use a new take name")
    camera_data = bpy.data.cameras.new(name)
    camera = bpy.data.objects.new(name, camera_data)
    scene.collection.objects.link(camera)
    camera.rotation_mode = "QUATERNION"
    camera_data.type = "PERSP"
    camera_data.sensor_fit = "HORIZONTAL"
    camera_data.sensor_width = metadata["sensor_width_mm"]
    camera_data.clip_start = metadata["clip_start_m"] / scale
    camera_data.clip_end = metadata["clip_end_m"] / scale
    start_frame = metadata["scene_frame_start"]
    for sample in samples:
        frame = start_frame + sample["frame"] - 1
        camera.location = Vector(sample["position_m"]) / scale
        camera.rotation_quaternion = Quaternion(sample["quaternion_wxyz"])
        camera_data.lens = sample["focal_mm"]
        camera.keyframe_insert(data_path="location", frame=frame)
        camera.keyframe_insert(data_path="rotation_quaternion", frame=frame)
        camera_data.keyframe_insert(data_path="lens", frame=frame)
    linear_action(camera.animation_data.action)
    linear_action(camera_data.animation_data.action)
    scene.camera = camera
    scene.render.fps = round(metadata["fps"])
    scene.render.fps_base = scene.render.fps / metadata["fps"]
    scene.render.resolution_x, scene.render.resolution_y = metadata["resolution"]
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = 1
    scene.render.pixel_aspect_y = 1
    scene.frame_start = start_frame
    scene.frame_end = start_frame + len(samples) - 1
    scene.frame_set(start_frame)
    output.parent.mkdir(parents=True, exist_ok=True)
    require(not output.exists(), "Output appeared during processing; refusing to overwrite")
    bpy.ops.wm.save_as_mainfile(filepath=str(output), check_existing=False)
    report["output_scene"] = output.relative_to(root).as_posix()
    report["camera_name"] = name
    report["scene_frame_start"] = scene.frame_start
    report["scene_frame_end"] = scene.frame_end
    report["elapsed_seconds"] = time.monotonic() - started
    write_json(report_path, report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    inspect_parser = subcommands.add_parser("inspect")
    inspect_parser.add_argument("--workspace", required=True)
    inspect_parser.add_argument("--input", required=True)
    inspect_parser.add_argument("--output", required=True)
    inspect_parser.add_argument("--scale-m-per-unit", type=float)
    compile_parser = subcommands.add_parser("compile")
    compile_parser.add_argument("--workspace", required=True)
    compile_parser.add_argument("--plan", required=True)
    compile_parser.add_argument("--output", required=True)
    bake_parser = subcommands.add_parser("bake")
    bake_parser.add_argument("--workspace", required=True)
    bake_parser.add_argument("--input", required=True)
    bake_parser.add_argument("--trajectory", required=True)
    bake_parser.add_argument("--output", required=True)
    bake_parser.add_argument("--report", required=True)
    require("--" in sys.argv, "Pass script arguments after Blender's -- separator")
    arguments = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    root = pathlib.Path(arguments.workspace).resolve(strict=True)
    require(root.is_dir(), "Workspace must be a directory")
    {"inspect": inspect_scene, "compile": compile_plan, "bake": bake_camera}[arguments.command](root, arguments)


if __name__ == "__main__":
    main()
