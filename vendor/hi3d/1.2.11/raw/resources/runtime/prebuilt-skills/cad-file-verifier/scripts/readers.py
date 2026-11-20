"""Content identification and static snapshots. Extension is not format evidence."""
from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from snapshot import blank_snapshot, cell, missing, read_items, read_value

MAX_TEXT_BYTES = 32 * 1024 * 1024
STEP_TYPE = re.compile(r"#\d+\s*=\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(")
STEP_SCHEMA = re.compile(r"FILE_SCHEMA\s*\(\s*\(\s*'([^']*)'")


def identify(path):
    path = Path(path)
    raw = path.read_bytes()[:4096]
    if raw.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
        except zipfile.BadZipFile:
            return _identity("unknown", None, "none", "zip header is unreadable")
        if _unsafe_names(names):
            return _identity("fcstd", None, "high", "zip member path is unsafe", unsafe=True)
        if "Document.xml" in names:
            return _identity("fcstd", None, "high", "zip Document.xml")
        return _identity("unknown", None, "low", "zip has no Document.xml")
    text_head = raw.lstrip(b"\xef\xbb\xbf \t\r\n")
    if text_head.startswith(b"ISO-10303-21"):
        return _identity("step", _step_version(path), "high", "ISO-10303-21 header")
    if raw.startswith(b"AutoCAD Binary DXF"):
        return _identity("dxf", None, "high", "binary DXF sentinel", binary=True)
    if _looks_like_ascii_dxf(raw):
        return _identity("dxf", None, "high", "DXF group codes")
    return _identity("unknown", None, "low", "content does not match STEP, DXF, or FCStd")


def _identity(fmt, version, confidence, evidence, unsafe=False, binary=False):
    return {
        "id": fmt,
        "version": version,
        "confidence": confidence,
        "evidence": evidence,
        "unsafe": unsafe,
        "binary": binary,
    }


def _unsafe_names(names):
    for name in names:
        parts = Path(name).parts
        if name.startswith("/") or name.startswith("\\") or ".." in parts:
            return True
    return False


def _looks_like_ascii_dxf(raw):
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeError:
        return False
    lines = [line.strip() for line in text.splitlines()[:8]]
    return len(lines) >= 2 and lines[0] == "0" and lines[1] in {"SECTION", "COMMENT"}


def _step_version(path):
    head = Path(path).read_text(encoding="utf-8", errors="replace")[:8000]
    match = STEP_SCHEMA.search(head)
    return match.group(1) if match else None


def read_static(path):
    identity = identify(path)
    snap = blank_snapshot()
    snap["format"] = {key: identity[key] for key in ("id", "version", "confidence", "evidence")}
    if identity["confidence"] != "high":
        snap["warnings"].append("格式不能仅凭扩展名确定")
        return snap
    if identity.get("unsafe"):
        snap["read_error"] = "压缩包成员路径不安全，已拒绝读取"
        snap["warnings"].append(snap["read_error"])
        return snap
    if identity.get("binary"):
        snap["read_error"] = ""
        snap["warnings"].append("二进制 DXF 已识别，但静态读取器不能解析其图层和对象")
        return snap
    reader = {"step": _read_step, "dxf": _read_dxf, "fcstd": _read_fcstd}[identity["id"]]
    try:
        reader(Path(path), snap)
    except (OSError, ValueError, ET.ParseError, zipfile.BadZipFile) as exc:
        snap["read_error"] = "静态读取失败：" + type(exc).__name__
        snap["warnings"].append(snap["read_error"])
    return snap


def _read_step(path, snap):
    if path.stat().st_size > MAX_TEXT_BYTES:
        raise ValueError("file exceeds static read limit")
    text = path.read_text(encoding="utf-8", errors="replace")
    counts = {}
    for match in STEP_TYPE.finditer(text):
        name = match.group(1)
        counts[name] = counts.get(name, 0) + 1
    snap["entity_types"] = read_items({name: {"count": cell(count)} for name, count in sorted(counts.items())})
    if ".MILLI." in text and ".METRE." in text:
        snap["units"] = read_value("mm", "SI_UNIT milli metre")
    elif ".CENTI." in text and ".METRE." in text:
        snap["units"] = read_value("cm", "SI_UNIT centi metre")
    elif ".METRE." in text:
        snap["units"] = read_value("m", "SI_UNIT metre")
    else:
        snap["units"] = missing("STEP 头未给出可识别的长度单位")
    snap["objects"] = missing("STEP 实体序号不是稳定对象身份，静态读取不把类型数量当成对象")
    snap["geometry"] = unread_geometry()
    snap["placement"] = missing("静态 STEP 读取不提取装配位置")
    snap["dependencies"] = read_items({})


def unread_geometry():
    from snapshot import unread
    return unread("unsupported", "静态读取不能作为几何一致的证据")


def _pairs(text):
    lines = text.splitlines()
    pairs = []
    index = 0
    while index + 1 < len(lines):
        code_text = lines[index].strip()
        try:
            code = int(code_text)
        except ValueError as exc:
            raise ValueError("DXF group code is not an integer") from exc
        pairs.append((code, lines[index + 1].strip()))
        index += 2
    return pairs


def _read_dxf(path, snap):
    if path.stat().st_size > MAX_TEXT_BYTES:
        raise ValueError("file exceeds static read limit")
    pairs = _pairs(path.read_text(encoding="utf-8", errors="replace"))
    section = None
    expect_section = False
    table = None
    layers = {}
    styles = {}
    blocks = {}
    objects = {}
    dimensions = {}
    dependencies = {}
    current = None
    bucket = None
    saw_entities = False
    saw_layer_table = False
    entity_counts = {}
    pending_units = False
    for code, value in pairs:
        if code == 0 and value == "SECTION":
            expect_section = True
            current = None
            continue
        if expect_section and code == 2:
            section = value
            expect_section = False
            table = None
            continue
        if code == 0 and value == "ENDSEC":
            section = None
            current = None
            continue
        if section == "HEADER" and code == 9 and value == "$INSUNITS":
            pending_units = True
            continue
        if pending_units and code == 70:
            snap["units"] = _dxf_units(value)
            pending_units = False
            continue
        if section == "TABLES" and code == 0 and value == "TABLE":
            table = None
            current = None
            continue
        if section == "TABLES" and code == 2 and table is None:
            table = value
            if value == "LAYER":
                saw_layer_table = True
            continue
        if section == "TABLES" and code == 0 and value == "ENDTAB":
            table = None
            current = None
            continue
        if section == "TABLES" and table == "LAYER" and code == 0 and value == "LAYER":
            current = {}
            bucket = layers
            continue
        if section == "TABLES" and table == "STYLE" and code == 0 and value == "STYLE":
            current = {}
            bucket = styles
            continue
        if section == "BLOCKS" and code == 0 and value == "BLOCK":
            current = {}
            bucket = blocks
            continue
        if section == "ENTITIES" and code == 0 and value not in {"ENDSEC"}:
            saw_entities = True
            entity_counts[value] = entity_counts.get(value, 0) + 1
            current = {"type": value}
            bucket = objects
            continue
        if not isinstance(current, dict):
            continue
        if code == 2 and "name" not in current and bucket is not objects:
            current["name"] = value
        elif code == 5 and bucket is objects and "handle" not in current:
            current["handle"] = value
        elif code == 8 and bucket is objects:
            current["layer"] = value
        elif code == 62 and bucket is layers:
            current["color"] = _int_or_missing(value)
        elif code == 6 and bucket is layers:
            current["linetype"] = value
        elif code == 70 and bucket is layers:
            flags = _int_or_missing(value)
            current["flags"] = flags
        elif code == 42 and bucket is objects:
            current["measure"] = _float_or_missing(value)
        elif code == 1 and bucket is objects and current.get("type") == "IMAGE":
            current["path"] = value
        elif code == 3 and bucket is styles:
            current["font"] = value
        if bucket is objects and current.get("handle") and current.get("type"):
            objects[current["handle"]] = current
        elif bucket is not objects and current.get("name"):
            bucket[current["name"]] = current
    if snap["units"]["status"] == "unsupported":
        snap["units"] = missing("DXF 头未给出 $INSUNITS")
    snap["layers"] = _layer_field(layers, saw_layer_table)
    snap["text_styles"] = read_items({name: {"font": cell(item.get("font"))} for name, item in styles.items()}) if styles or _saw(pairs, "STYLE") else missing("未读到 STYLE 表")
    snap["blocks"] = read_items({name: {"name": cell(name)} for name in blocks}) if blocks or _saw(pairs, "BLOCK") else missing("未读到 BLOCK 段")
    if saw_entities:
        snap["objects"] = read_items({
            handle: {
                "type": cell(item.get("type")),
                "layer": cell(item.get("layer")) if "layer" in item else missing("实体没有组码 8"),
            }
            for handle, item in objects.items()
        })
        snap["entity_types"] = read_items({name: {"count": cell(count)} for name, count in sorted(entity_counts.items())})
        for handle, item in objects.items():
            if item.get("type") == "DIMENSION":
                measure = item.get("measure")
                dimensions[handle] = {
                    "value": cell(measure) if isinstance(measure, float) else missing("尺寸没有组码 42"),
                    "layer": cell(item.get("layer")) if "layer" in item else missing("尺寸没有图层"),
                }
            if item.get("type") == "IMAGE" and item.get("path"):
                dependencies["image:" + handle] = {"path": cell(item["path"])}
        snap["dimensions"] = read_items(dimensions)
        snap["dependencies"] = read_items(dependencies)
    else:
        snap["objects"] = missing("未读到 ENTITIES 段")
        snap["dimensions"] = missing("未读到 ENTITIES 段，不能把尺寸当成空集合")
        snap["dependencies"] = missing("未读到 ENTITIES 段")
    snap["layouts"] = missing("静态 DXF 读取未解析布局；缺失不代表没有布局")
    snap["geometry"] = unread_geometry()


def _saw(pairs, token):
    return any(code == 0 and value == token for code, value in pairs)


def _int_or_missing(value):
    try:
        return int(value)
    except ValueError:
        return None


def _float_or_missing(value):
    try:
        return float(value)
    except ValueError:
        return None


def _dxf_units(value):
    mapping = {"0": "unitless", "1": "in", "4": "mm", "5": "cm", "6": "m"}
    if value not in mapping:
        return missing("未识别的 $INSUNITS 值")
    return read_value(mapping[value], "$INSUNITS")


def _layer_field(layers, saw_table):
    if not saw_table:
        return missing("未读到 LAYER 表，不能把图层当成空集合")
    items = {}
    for name, item in layers.items():
        flags = item.get("flags")
        frozen = isinstance(flags, int) and bool(flags & 1)
        locked = isinstance(flags, int) and bool(flags & 4)
        items[name] = {
            "color": cell(item["color"]) if isinstance(item.get("color"), int) else missing("图层没有颜色组码"),
            "linetype": cell(item["linetype"]) if item.get("linetype") else missing("图层没有线型"),
            "visible": cell(not frozen) if isinstance(flags, int) else missing("图层没有 70 标志"),
            "locked": cell(locked) if isinstance(flags, int) else missing("图层没有 70 标志"),
            "plot": cell(not (isinstance(flags, int) and bool(flags & 16))) if isinstance(flags, int) else missing("图层没有打印标志"),
        }
    return read_items(items, "DXF LAYER 表")


def _read_fcstd(path, snap):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if _unsafe_names(names):
            raise ValueError("unsafe zip member")
        xml_bytes = archive.read("Document.xml")
    root = ET.fromstring(xml_bytes)
    objects = {}
    for element in root.iter():
        if not str(element.tag).endswith("Object"):
            continue
        name = element.attrib.get("name")
        kind = element.attrib.get("type")
        if name and kind:
            objects[name] = kind
    snap["objects"] = read_items({name: {"type": cell(kind), "layer": missing("FCStd 对象没有 DXF 图层")} for name, kind in objects.items()})
    features = {name: {"type": cell(kind)} for name, kind in objects.items() if kind.startswith(("PartDesign::", "Sketcher::"))}
    solids = {name: {"type": cell(kind)} for name, kind in objects.items() if kind.startswith(("Part::", "PartDesign::"))}
    sketches = {name: {"type": cell(kind)} for name, kind in objects.items() if kind.startswith("Sketcher::")}
    snap["features"] = read_items(features, "Document.xml 中的 PartDesign/Sketcher 对象")
    snap["solids"] = read_items(solids, "Document.xml 中的 Part 对象")
    snap["sketches"] = read_items(sketches, "Document.xml 中的草图对象")
    snap["parameters"] = missing("静态 Document.xml 读取不解析约束表达式或电子表格")
    snap["constraints"] = missing("静态 Document.xml 读取不解析约束")
    snap["geometry"] = unread_geometry()
    snap["placement"] = missing("静态 FCStd 读取不提取形状位置")
    snap["units"] = missing("静态 FCStd 读取不证明文档单位")
    snap["dependencies"] = read_items({})
    snap["configurations"] = missing("静态 FCStd 读取不解析配置")
    snap["custom_properties"] = missing("静态 FCStd 读取不解析自定义属性")
