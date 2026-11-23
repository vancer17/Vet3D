import argparse
import json
import math
import sys
from pathlib import Path

LEVELS = (8, 6, 4, 3, 2, 1)


def number(value, name, minimum=0.0):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric, not boolean")
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be numeric") from None
    if not math.isfinite(result) or result < minimum:
        raise ValueError(f"{name} must be finite and >= {minimum}")
    return result


def region_kind(region):
    kind = region.get("kind", "gray")
    if not isinstance(kind, str) or kind not in ("gray", "yellow", "red"):
        raise ValueError("kind must be gray, yellow or red")
    return kind


def region_floor(region, budget):
    kind = region_kind(region)
    faces = count(region.get("faces"), "faces", 1)
    learned_floor = count(region.get("learned_floor", 1), "learned_floor", 1)
    perimeter_segments = count(region.get("boundary_segments", 4), "boundary_segments", 4)
    if kind == "red":
        return faces, "protected"
    area = number(region.get("area"), "area", 0)
    curvature = number(region.get("max_curvature", 0), "max_curvature")
    span = math.sqrt(8 * budget / curvature) if curvature > 0 else math.inf
    if kind == "yellow" and region.get("max_span") is not None:
        span = min(span, number(region["max_span"], "max_span", 1e-12))
    curvature_faces = 1 if math.isinf(span) else math.ceil(area / (span * span))
    boundary_faces = max(1, math.ceil(perimeter_segments / 16))
    floor = min(faces, max(1, curvature_faces, boundary_faces, learned_floor))
    reason = "curvature" if curvature_faces >= boundary_faces else "boundary"
    return floor, reason


def predict(data):
    budget = number(data["epsilon"], "epsilon", 1e-15)
    regions = []
    for region in data["regions"]:
        floor, reason = region_floor(region, budget)
        faces = count(region["faces"], "faces", 1)
        aggressive = floor
        recommended = min(faces, max(floor, math.ceil(floor * 1.5)))
        conservative = min(faces, max(recommended, math.ceil(faces * 0.75)))
        regions.append({"id": region["id"], "kind": region.get("kind", "gray"), "faces": faces,
                        "aggressive": aggressive, "recommended": recommended,
                        "conservative": conservative, "limit": reason})
    totals = {key: sum(region[key] for region in regions) for key in ("faces", "aggressive", "recommended", "conservative")}
    return {"stage": "predict", "regions": regions, "totals": totals}


def verdict(data):
    budget = number(data["epsilon"], "epsilon", 1e-15)
    limits = {"min_angle": 20.0, "max_aspect": 8.0, "max_normal_degrees": 20.0, "max_uv_stretch": 1.25}
    limits.update(data.get("limits", {}))
    limits = {name: number(value, name) for name, value in limits.items()}
    required = ("forward_error", "backward_error", "min_angle", "max_aspect", "max_normal_degrees",
                "max_uv_stretch", "closed_loops", "nonquad", "nonmanifold")
    results = []
    for item in data["regions"]:
        if "kind" in item:
            region_kind(item)
        probe = item.get("probe", False)
        if not isinstance(probe, bool):
            raise ValueError("probe must be true or false")
        faces = count(item.get("faces"), "faces", 1) if probe or "faces" in item else None
        level = count(item["level"], "level", 1)
        if level not in LEVELS:
            raise ValueError(f"level must be one of {LEVELS}")
        metrics = item["metrics"]
        missing = [name for name in required if name not in metrics or metrics[name] is None]
        if missing:
            raise ValueError(f"region {item.get('id')} missing metrics: {', '.join(missing)}")
        if not isinstance(metrics["closed_loops"], bool):
            raise ValueError("closed_loops must be true or false")
        for name in required:
            if name != "closed_loops":
                number(metrics[name], name)
        failures = []
        if number(metrics["forward_error"], "forward_error") > budget or number(metrics["backward_error"], "backward_error") > budget:
            failures.append("error")
        if number(metrics["min_angle"], "min_angle") < limits["min_angle"]:
            failures.append("angle")
        if number(metrics["max_aspect"], "max_aspect") > limits["max_aspect"]:
            failures.append("stretch")
        if number(metrics["max_normal_degrees"], "max_normal_degrees") > limits["max_normal_degrees"]:
            failures.append("normal")
        if number(metrics["max_uv_stretch"], "max_uv_stretch") > limits["max_uv_stretch"]:
            failures.append("uv")
        if not metrics["closed_loops"] or number(metrics["nonquad"], "nonquad") or number(metrics["nonmanifold"], "nonmanifold"):
            failures.append("topology")
        lower = [candidate for candidate in LEVELS if candidate < level]
        if not failures:
            action = "accept"
            next_level = level
            floor_update = faces
        elif lower:
            action = "rollback_refine"
            next_level = lower[0]
            floor_update = None
        else:
            action = "keep_previous"
            next_level = None
            floor_update = None
        results.append({"id": item["id"], "probe": probe, "level": level,
                        "action": action, "next_level": next_level, "failures": failures,
                        "learned_floor": floor_update if probe and action == "accept" else None})
    return {"stage": "verdict", "regions": results}

def ratio(value, name):
    result = number(value, name)
    if result > 1:
        raise ValueError(f"{name} must be <= 1")
    return result


def count(value, name, minimum=0):
    result = number(value, name, minimum)
    if not result.is_integer():
        raise ValueError(f"{name} must be an integer")
    return int(result)


def view_scores(value, name):
    if not isinstance(value, list) or len(value) < 3:
        raise ValueError(f"{name} requires at least three measured views")
    return [ratio(item, name) for item in value]


ROUTE_FIELDS = ("primitive", "primitive_silhouette_iou", "cavity_status", "cavity_evidence")


def route(data):
    missing = [name for name in ROUTE_FIELDS if data.get(name) is None]
    if missing:
        raise ValueError(f"route missing: {', '.join(missing)}")
    threshold = ratio(data.get("limits", {}).get("min_primitive_iou", 0.95), "min_primitive_iou")
    primitive = str(data["primitive"])
    scores = view_scores(data["primitive_silhouette_iou"], "primitive_silhouette_iou")
    cavity = data["cavity_status"]
    if cavity not in ("present", "absent", "unknown"):
        raise ValueError("invalid cavity_status")
    evidence = data["cavity_evidence"]
    if not isinstance(evidence, dict) or any(not isinstance(evidence.get(key), str) or not evidence[key].strip() for key in ("method", "scope", "record")):
        raise ValueError("cavity_evidence requires method, scope and record")
    if cavity != "unknown" and evidence["method"] not in ("ray_intersections", "cross_sections", "inspected_geometry"):
        raise ValueError("bounding-box depth is not cavity evidence")
    if "red_area_ratio" in data:
        ratio(data["red_area_ratio"], "red_area_ratio")
    decomposition = data.get("decomposition_needed", False)
    if not isinstance(decomposition, bool):
        raise ValueError("decomposition_needed must be boolean")
    reasons = []
    if primitive not in ("cube", "cylinder", "uv_sphere", "plane", "cone", "torus"):
        reasons.append("no_primitive")
    if min(scores) < threshold:
        reasons.append("silhouette_far_from_primitive")
    if cavity == "present":
        reasons.append("internal_cavity")
    if decomposition:
        choice = "inspect_components"
        reasons.append("assembly_needs_component_assessment")
    elif cavity == "unknown":
        choice = "inspect_geometry"
        reasons.append("cavity_unverified")
    else:
        choice = "primitive_align" if not reasons else "v5_baseline"
    return {"stage": "route", "route": choice, "reasons": reasons,
            "limits": {"min_primitive_iou": threshold}, "regions": [],
            "note": "route is a planning decision, not model acceptance"}


def align_step(data):
    for name in ("iteration", "faces", "v5_faces", "gray_yellow_max", "silhouette_iou", "silhouette_max_error", "bad_red", "bad_gray_yellow", "epsilon", "metrics", "local_attempts", "stalled", "fallback_validated"):
        if data.get(name) is None:
            raise ValueError(f"align missing: {name}")
    budget = number(data["epsilon"], "epsilon", 1e-15)
    faces = count(data["faces"], "faces", 1)
    ceiling = count(data["v5_faces"], "v5_faces", 1)
    count(data["iteration"], "iteration")
    bad_red = count(data["bad_red"], "bad_red")
    bad_gray_yellow = count(data["bad_gray_yellow"], "bad_gray_yellow")
    local_attempts = count(data["local_attempts"], "local_attempts")
    for name in ("stalled", "fallback_validated"):
        if not isinstance(data[name], bool):
            raise ValueError(f"{name} must be boolean")
    minimum_iou = ratio(data.get("limits", {}).get("min_silhouette_iou", 0.99), "min_silhouette_iou")
    scores = view_scores(data["silhouette_iou"], "silhouette_iou")
    failures = verdict({"epsilon": budget, "limits": data.get("quality_limits", {}),
                        "regions": [{"id": "candidate", "level": 1, "metrics": data["metrics"]}]})["regions"][0]["failures"]
    if number(data["gray_yellow_max"], "gray_yellow_max") > budget:
        failures.append("gray_yellow_error")
    silhouette_error = number(data["silhouette_max_error"], "silhouette_max_error")
    if min(scores) < minimum_iou or silhouette_error > budget:
        failures.append("silhouette")
    if bad_red or bad_gray_yellow:
        failures.append("unresolved_regions")
    next_faces = count(data.get("next_faces", faces), "next_faces", 1)
    if faces > ceiling or next_faces > ceiling:
        action = "fallback_v5" if data["fallback_validated"] else "keep_best_review"
    elif not failures:
        action = "accept"
    elif any(reason in failures for reason in ("angle", "stretch", "normal", "uv", "topology")):
        action = "repair_quality"
    elif data["stalled"] and local_attempts >= 2:
        action = "uniform_refine"
    elif bad_red:
        action = "add_closed_lines_red"
    elif bad_gray_yellow:
        action = "add_closed_lines_gray_yellow"
    else:
        action = "locate_error"
    return {"stage": "align", "action": action, "failures": failures, "regions": []}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("predict", "verdict", "route", "align"))
    parser.add_argument("input")
    parser.add_argument("output")
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise SystemExit("output exists")
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = {"predict": predict, "verdict": verdict, "route": route, "align": align_step}[args.mode](data)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result.get("totals") or {k: result[k] for k in ("route", "action", "reasons") if k in result} or result["regions"], ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (KeyError, ValueError) as error:
        print(f"invalid input: {error}", file=sys.stderr)
        sys.exit(2)
