"""Check profiles, field cells, and overall status for CAD verification."""
from __future__ import annotations

PASS = "pass"
FAIL = "fail"
UNKNOWN = "unknown"
BLOCKED = "blocked"
NA = "not_applicable"
OVERALL = {PASS, FAIL, UNKNOWN, BLOCKED, "partial"}

PROFILE_REVISION = "1"
PROFILES = {
    "drawing": {
        "id": "drawing-preservation",
        "required": ["layers", "objects", "blocks", "dimensions", "text_styles", "xrefs", "layouts"],
    },
    "part": {
        "id": "part-preservation",
        "required": ["units", "solids", "sketches", "constraints", "parameters", "features", "configurations", "custom_properties"],
    },
    "assembly": {
        "id": "assembly-preservation",
        "required": ["components", "instances", "placements", "mates", "configurations", "suppression", "external_refs"],
    },
    "drawing_sheet": {
        "id": "sheet-preservation",
        "required": ["model_link", "views", "dimensions", "annotations", "title_block", "fonts", "layouts"],
    },
    "exchange_solid": {
        "id": "exchange-solid",
        "required": ["entity_types", "units", "placement", "geometry"],
    },
}

# Fields a format is known not to carry. Unsupported here means the requirement
# cannot be satisfied, which is different from a reader that has not implemented the field.
CANNOT_EXPRESS = {
    "step": {"layers", "blocks", "layouts", "text_styles", "sketches", "constraints", "parameters", "features", "mates", "xrefs", "views", "annotations", "title_block"},
    "dxf": {"sketches", "constraints", "parameters", "features", "mates", "solids", "components"},
    "fcstd": set(),
}

CHECK_FIELD = {
    "layers": "layers",
    "objects": "objects",
    "blocks": "blocks",
    "dimensions": "dimensions",
    "text_styles": "text_styles",
    "layouts": "layouts",
    "xrefs": "dependencies",
    "units": "units",
    "solids": "solids",
    "sketches": "sketches",
    "constraints": "constraints",
    "parameters": "parameters",
    "features": "features",
    "configurations": "configurations",
    "custom_properties": "custom_properties",
    "components": "components",
    "instances": "objects",
    "placements": "placement",
    "mates": "relations",
    "suppression": "suppression",
    "external_refs": "dependencies",
    "model_link": "relations",
    "views": "views",
    "annotations": "annotations",
    "title_block": "title_block",
    "fonts": "fonts",
    "entity_types": "entity_types",
    "placement": "placement",
    "geometry": "geometry",
}

PRESERVATION = set(CHECK_FIELD)
HEALTH = {"file_readable", "native_open", "source_protected", "dependencies_closed", "roundtrip", "continue_edit", "direct_edit"}
INFER_TYPE = {"dxf": "drawing", "step": "exchange_solid", "fcstd": "part"}


def cell(value):
    return {"status": "read", "value": value}


def unread(status, reason):
    return {"status": status, "items": None, "value": None, "reason": reason}


def read_items(items, reason=""):
    return {"status": "read", "items": items, "value": None, "reason": reason}


def read_value(value, reason=""):
    return {"status": "read", "items": None, "value": value, "reason": reason}


def missing(reason):
    return unread("missing", reason)


def blank_snapshot():
    unsupported = {
        "units": "尚未读取单位",
        "layers": "尚未读取图层",
        "objects": "尚未读取对象",
        "entity_types": "尚未读取实体类型",
        "blocks": "尚未读取块",
        "dimensions": "尚未读取尺寸",
        "text_styles": "尚未读取文字样式",
        "layouts": "尚未读取布局",
        "parameters": "当前适配器未实现参数读取",
        "features": "当前适配器未实现特征读取",
        "sketches": "当前适配器未实现草图读取",
        "constraints": "当前适配器未实现约束读取",
        "solids": "当前适配器未实现实体读取",
        "configurations": "当前适配器未实现配置读取",
        "custom_properties": "当前适配器未实现自定义属性读取",
        "components": "当前适配器未实现零部件读取",
        "placement": "当前适配器未实现位置读取",
        "relations": "当前适配器未实现关系读取",
        "suppression": "当前适配器未实现抑制状态读取",
        "views": "当前适配器未实现视图读取",
        "annotations": "当前适配器未实现标注读取",
        "title_block": "当前适配器未实现图框读取",
        "fonts": "当前适配器未实现字体读取",
        "geometry": "静态读取不能作为几何一致的证据",
        "dependencies": "尚未读取外部依赖",
    }
    snap = {
        "format": {"id": "unknown", "version": None, "confidence": "none", "evidence": ""},
        "warnings": [],
        "read_error": "",
        "open": {"native": False, "status": BLOCKED, "recovered": None, "reason": "尚未执行原生打开"},
        "evidence_origin": "static",
    }
    for key, reason in unsupported.items():
        snap[key] = unread("unsupported", reason)
    return snap


def profile_for(document_type):
    data = PROFILES.get(document_type)
    if not data:
        return {"id": "untyped", "revision": PROFILE_REVISION, "required": []}
    return {"id": data["id"], "revision": PROFILE_REVISION, "required": list(data["required"])}


def select_checks(document_type, required_preservation, excluded):
    """Return check ids in stable order. Explicit preservation replaces the profile default."""
    profile = profile_for(document_type)
    if required_preservation:
        chosen = list(required_preservation)
    else:
        chosen = list(profile["required"])
    excluded = set(excluded or [])
    ordered = []
    for check_id in ["file_readable", "source_protected", *chosen, "native_open", "dependencies_closed", "roundtrip", "continue_edit", "direct_edit"]:
        if check_id in excluded or check_id in ordered:
            continue
        ordered.append(check_id)
    omitted = [check_id for check_id in profile["required"] if check_id not in chosen and check_id not in excluded]
    return ordered, omitted, profile


def overall_status(checks):
    required = [item for item in checks if item.get("required") and item.get("status") != NA]
    if not required:
        if any(item.get("status") == BLOCKED for item in checks):
            return BLOCKED
        return "partial"
    statuses = {item["status"] for item in required}
    if FAIL in statuses:
        return FAIL
    if BLOCKED in statuses:
        return BLOCKED
    if UNKNOWN in statuses or NA in statuses:
        return "partial"
    if statuses == {PASS}:
        return PASS
    return "partial"
