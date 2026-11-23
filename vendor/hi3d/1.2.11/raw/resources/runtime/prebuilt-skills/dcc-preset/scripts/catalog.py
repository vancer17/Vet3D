"""Version-gated DCC presets. The catalog is the only preset list."""

from __future__ import annotations

import re

VERSION_RE = re.compile(r"^(\d+)\.(\d+)(?:\.(\d+))?$")

PRESETS = (
    {
        "id": "unreal.water",
        "app": "unreal",
        "topic": "water",
        "min_version": (5, 7, 0),
        "operation": "enable_plugins",
        "plugins": ("Water", "Landmass"),
        "shipping": "experimental",
        "summary": "在 UE 5.7 及以上的 .uproject 中启用内置 Water 与 Landmass。不放置水体，不打开编辑器。",
    },
    {
        "id": "unreal.water-samples",
        "app": "unreal",
        "topic": "water",
        "min_version": (5, 7, 0),
        "operation": "enable_plugins",
        "plugins": ("Water", "Landmass", "WaterExtras"),
        "shipping": "not_for_shipping",
        "summary": "在水体插件之外再启用 WaterExtras 示例。该插件含测试地图，不直接用于发行。",
    },
    {
        "id": "unreal.water-simulation",
        "app": "unreal",
        "topic": "water",
        "min_version": (5, 7, 0),
        "operation": "enable_plugins",
        "plugins": ("Water", "Landmass", "WaterAdvanced", "Buoyancy"),
        "shipping": "experimental",
        "summary": "再启用实验性的 WaterAdvanced 与 Buoyancy。只打开插件，不创建浅水或浮力对象。",
    },
    {
        "id": "houdini.ocean-spectrum",
        "app": "houdini",
        "topic": "water",
        "min_version": (20, 5, 0),
        "operation": "create_sop",
        "operator": "oceanspectrum",
        "shipping": "builtin",
        "summary": "在 Houdini 20.5 及以上用 hython 新建 HIP，并放入内置 Ocean Spectrum SOP。不生成海洋缓存。",
    },
    {
        "id": "blender.fluid-domain",
        "app": "blender",
        "topic": "water",
        "min_version": (4, 2, 0),
        "operation": "add_fluid_domain",
        "shipping": "builtin",
        "summary": "在 Blender 4.2 及以上新建 BLEND，加入内置流体域和液体流入。没有单独的水体插件可开关，也不烘焙模拟。",
    },
)


def parse_version(text):
    if not isinstance(text, str):
        return None
    match = VERSION_RE.fullmatch(text.strip())
    if not match:
        return None
    major, minor, patch = match.groups()
    return (int(major), int(minor), int(patch or 0))


def version_ok(found, minimum):
    return found is not None and tuple(found) >= tuple(minimum)


def get_preset(preset_id):
    for item in PRESETS:
        if item["id"] == preset_id:
            return item
    return None


def lookup(*, app=None, topic=None, version=None, preset_id=None):
    found = parse_version(version) if version else None
    if version and found is None:
        raise ValueError("version must look like 5.7 or 5.7.1")
    rows = []
    for item in PRESETS:
        if preset_id and item["id"] != preset_id:
            continue
        if app and item["app"] != app:
            continue
        if topic and item["topic"] != topic:
            continue
        row = public_row(item)
        if version:
            row["applicable"] = version_ok(found, item["min_version"])
        else:
            row["applicable"] = None
        rows.append(row)
    return rows


def public_row(item):
    minimum = item["min_version"]
    row = {
        "id": item["id"],
        "app": item["app"],
        "topic": item["topic"],
        "min_version": "%d.%d.%d" % minimum,
        "operation": item["operation"],
        "shipping": item["shipping"],
        "summary": item["summary"],
    }
    if "plugins" in item:
        row["plugins"] = list(item["plugins"])
    if "operator" in item:
        row["operator"] = item["operator"]
    return row
