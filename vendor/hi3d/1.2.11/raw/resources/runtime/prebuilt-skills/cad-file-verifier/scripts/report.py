"""Chinese report. Local conclusions stay inside the checks that actually ran."""
from __future__ import annotations

FORBIDDEN = ("完全兼容", "无损", "全部保留", "全面兼容")
TITLES = {"pass": "通过", "partial": "部分验证", "fail": "失败", "blocked": "受阻"}


def render_report(result):
    text = "\n".join([
        "# CAD 工程校对",
        "",
        _lead(result),
        "",
        "## 目标环境",
        _environment(result),
        "",
        "## 上游建模",
        _upstream(result),
        "",
        "## 检查范围",
        _scope(result),
        "",
        "## 预期变化",
        _lines(result.get("expected_confirmed"), "没有需要单独核对的授权修改。"),
        "",
        "## 意外差异",
        _unexpected(result),
        "",
        "## 未验证",
        _by_status(result, "unknown", "没有因证据不足而留下的项目。"),
        "",
        "## 受阻",
        _by_status(result, "blocked", "没有因环境或授权而未能执行的项目。"),
        "",
        "## 人工补救",
        _remedies(result),
        "",
        "## 证据",
        _evidence(result),
        "",
    ])
    for phrase in FORBIDDEN:
        if phrase in text:
            raise ValueError("report used an unsupported absolute claim")
    return text


def _lead(result):
    title = TITLES.get(result["overall_status"], result["overall_status"])
    scope = result["coverage_scope"]
    if result.get("mock"):
        return "本次使用模拟适配器走通了检查流程，整体程序结果为" + title + "。模拟结果不记入实测通过，也不能作为目标软件兼容的证据。"
    if result["overall_status"] == "pass":
        return "整体结果为通过。通过只覆盖本次要求并且实际取到证据的项目。" + scope + " 原始输入未被修改。"
    if result["overall_status"] == "partial":
        return "整体结果为部分验证。已经核对的项目不能外推为其余未验证项目也保留。" + scope
    if result["overall_status"] == "fail":
        return "整体结果为失败。至少一项必须保留的要求没有满足。原始输入未被修改。"
    return "整体结果为受阻。能独立完成的静态检查已经写入本报告；目标软件没有完成本次原生验收。这不构成文件不兼容的证据。"


def _upstream(result):
    upstream = result.get("upstream_build") or {}
    tool = upstream.get("tool") or "not-specified"
    if tool == "not-specified":
        return "本次没有声明 ClassCAD 或其他上游建模会话。源端内部检查即使存在，也不能代替目标软件验收。"
    lines = [
        "上游工具 " + tool + "，版本 " + (upstream.get("version") or "未标明") + "。",
        "这些材料只说明源端建模会话，不能代替目标软件里的图层、特征树、外部引用、重开和编辑探针。",
    ]
    if tool == "classcad":
        lines.append("本次没有连接 ClassCAD 会话，也没有把源端体积、渲染或特征检查记成目标原生通过。")
    refs = upstream.get("session_evidence_refs") or []
    if refs:
        lines.append("调用方提供、但本次未复跑的会话证据：" + "、".join(refs) + "。")
    return "\n".join(lines)


def _environment(result):
    target = result["target"]
    version = target.get("version") or "未标明版本"
    build = target.get("build") or "未标明构建"
    native = result.get("native_reason") or "原生打开未执行"
    return "目标软件 " + (target.get("software") or "未指定") + "，版本 " + version + "，构建 " + build + "。 " + native


def _scope(result):
    lines = [result["coverage_scope"]]
    if result.get("omitted_checks"):
        lines.append("未纳入本次要求、因此不能算作通过的项目：" + "、".join(result["omitted_checks"]) + "。")
    if result.get("excluded_checks"):
        lines.append("调用方明确排除的项目：" + "、".join(result["excluded_checks"]) + "。排除不等于通过。")
    return "\n".join(lines)


def _lines(items, empty):
    if not items:
        return empty
    return "\n".join("- " + _item(item) for item in items)


def _unexpected(result):
    return _lines(result.get("unexpected"), "没有超出授权范围的差异。")


def _by_status(result, status, empty):
    found = [item for item in result["checks"] if item["status"] == status]
    if not found:
        return empty
    return "\n".join("- " + item["id"] + "：" + item["reason"] for item in found)


def _remedies(result):
    lines = []
    for item in result.get("unexpected") or []:
        lines.append("- 需要人工核对该差异：" + _item(item))
    if result["overall_status"] == "blocked":
        lines.append("- 需要在能够启动目标软件的环境中重新执行原生打开或编辑验证。")
    if result.get("needs_confirmation"):
        lines.append("- 未执行操作：" + result["needs_confirmation"]["effect"])
    if not lines:
        return "没有从本次已检查项目中得出的人工补救事项。这不表示未检查的编辑都不需要处理。"
    return "\n".join(lines)


def _evidence(result):
    refs = result.get("evidence_index") or []
    if not refs:
        return "没有可索引的证据文件。"
    registry = "兼容记录已追加。" if result.get("registry_updated") else "兼容记录未更新。"
    return registry + "\n" + "\n".join("- " + item for item in refs)


def _item(item):
    if isinstance(item, str):
        return item
    path = item.get("path") or "未命名项目"
    reason = item.get("reason") or ""
    value = item.get("value")
    if value is not None:
        return path + " = " + str(value)
    return path + ("：" + reason if reason else "")
