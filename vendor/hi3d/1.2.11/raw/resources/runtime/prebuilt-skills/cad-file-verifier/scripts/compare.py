"""Semantic comparison. Equal counts are not identity, and unread fields are not empty matches."""
from __future__ import annotations

from snapshot import (
    BLOCKED,
    CANNOT_EXPRESS,
    CHECK_FIELD,
    FAIL,
    HEALTH,
    NA,
    PASS,
    PRESERVATION,
    UNKNOWN,
    missing,
    overall_status,
    select_checks,
    unread,
)


def build_checks(task, document_type, candidate, source, workspace_info, roundtrip, probe):
    chosen, omitted, profile = select_checks(
        document_type, task["required_preservation"], task["excluded_checks"]
    )
    has_baseline = source is not None and task["mode"] in {"compare", "roundtrip", "inspect"} and task["source"]
    # inspect may still carry a source when the caller provided one
    has_baseline = source is not None and task["source"] is not None
    checks = []
    expected_confirmed = []
    unexpected = []
    for check_id in chosen:
        required = _required(check_id, task, chosen, workspace_info)
        status, reason, confirmed, extra = _evaluate(
            check_id, required, task, candidate, source, has_baseline, workspace_info, roundtrip, probe
        )
        if not required and status == NA:
            pass
        checks.append({
            "id": check_id,
            "required": required,
            "status": status,
            "reason": reason,
            "evidence_refs": ["candidate-snapshot.json"] + (["source-snapshot.json"] if has_baseline else []),
        })
        expected_confirmed.extend(confirmed)
        unexpected.extend(extra)
    return {
        "checks": checks,
        "profile": profile,
        "omitted_checks": omitted,
        "expected_confirmed": expected_confirmed,
        "unexpected": unexpected,
        "overall_status": overall_status(checks),
        "document_type": document_type,
    }


def _required(check_id, task, chosen, workspace_info):
    if check_id in {"file_readable", "source_protected"}:
        return True
    if check_id == "native_open":
        return bool(task["require_native"] and task["target"]["software"])
    if check_id == "roundtrip":
        return task["mode"] == "roundtrip"
    if check_id in {"continue_edit", "direct_edit"}:
        return "edit_probe" in task["allowed_operations"]
    if check_id == "dependencies_closed":
        return bool(task["dependencies"] or workspace_info.get("external_refs"))
    return check_id in chosen and check_id in (PRESERVATION | HEALTH)


def _evaluate(check_id, required, task, candidate, source, has_baseline, workspace_info, roundtrip, probe):
    if check_id == "file_readable":
        return _file_readable(candidate)
    if check_id == "source_protected":
        if workspace_info.get("source_unchanged"):
            return PASS, "原始输入的内容在检查后未变化", [], []
        return FAIL, "原始输入的内容在检查期间发生变化", [], []
    if check_id == "native_open":
        return _native(task, candidate, probe)
    if check_id == "dependencies_closed":
        return _closure(task, workspace_info)
    if check_id == "roundtrip":
        return _roundtrip(task, roundtrip, probe)
    if check_id in {"continue_edit", "direct_edit"}:
        return _edit(check_id, task)
    fmt = (candidate.get("format") or {}).get("id")
    if required and check_id in CANNOT_EXPRESS.get(fmt, set()):
        return FAIL, "该格式不能表达此项，因此不满足保留要求", [], [{"path": check_id, "reason": "格式不能表达"}]
    if not has_baseline:
        return UNKNOWN, "没有可信基线，不能判断该项是否保留", [], []
    field_name = CHECK_FIELD[check_id]
    status, reason, confirmed, extra = _compare_field(
        field_name, source, candidate, task["expected_changes"], task["tolerances"].get("absolute")
    )
    return status, reason, confirmed, extra


def _file_readable(candidate):
    if candidate.get("read_error"):
        return FAIL, candidate["read_error"], [], []
    confidence = (candidate.get("format") or {}).get("confidence")
    if confidence == "high":
        return PASS, "已按文件内容识别格式，不单凭扩展名", [], []
    return UNKNOWN, "格式识别不确定，不能把扩展名当成格式证据", [], []


def _native(task, candidate, probe):
    if not task["require_native"]:
        return NA, "本次不要求目标软件原生打开", [], []
    if not probe.get("executable", {}).get("open_native"):
        return BLOCKED, probe.get("blocked_reason") or "目标软件不可用，原生打开未执行；这不是文件不兼容的证据", [], []
    opened = candidate.get("open") or {}
    status = opened.get("status") or BLOCKED
    reason = opened.get("reason") or "原生打开没有返回证据"
    if status == PASS and opened.get("recovered"):
        return FAIL, "打开过程发生了恢复或修复，不能作为无变化打开", [], []
    return status, reason, [], []


def _closure(task, workspace_info):
    problems = list(workspace_info.get("outside_dependencies") or []) + list(workspace_info.get("external_refs") or [])
    if not task["dependencies"] and not problems:
        return NA, "本次没有声明外部依赖，也没有读到外部引用路径", [], []
    if problems:
        names = ", ".join(item["id"] for item in problems)
        return FAIL, "交付依赖未闭合，仍指向工作区外或缺失：" + names, [], [{"path": "dependencies", "reason": names}]
    return PASS, "声明的依赖都在工作区内", [], []


def _roundtrip(task, roundtrip, probe):
    if task["mode"] != "roundtrip":
        return NA, "本次不是保存往返", [], []
    if "roundtrip" not in task["allowed_operations"]:
        return BLOCKED, "未授权在副本中保存并重新打开", [], []
    if not probe.get("executable", {}).get("save_copy"):
        return BLOCKED, "目标软件不可用，保存往返未执行；这不是文件不兼容的证据", [], []
    if not roundtrip:
        return BLOCKED, "保存往返没有返回结果", [], []
    return roundtrip["status"], roundtrip["reason"], [], roundtrip.get("unexpected") or []


def _edit(check_id, task):
    if "edit_probe" not in task["allowed_operations"]:
        return NA, "本次未约定编辑探针", [], []
    return UNKNOWN, "当前适配器未实现编辑探针，不能用任意修改代表整个工程可编辑", [], []


def _compare_field(field_name, source, candidate, expected, tolerance):
    left = source.get(field_name) or unread("unsupported", "基线没有该字段")
    right = candidate.get(field_name) or unread("unsupported", "候选没有该字段")
    if left.get("status") != "read" or right.get("status") != "read":
        if {left.get("status"), right.get("status")} == {"read", "missing"}:
            return FAIL, field_name + " 一侧读到了值，另一侧确认不存在", [], [{"path": field_name, "reason": "存在性不一致"}]
        return UNKNOWN, _unread_reason(field_name, left, right), [], []
    if left.get("items") is not None or right.get("items") is not None:
        return _compare_items(field_name, left.get("items") or {}, right.get("items") or {}, expected, tolerance)
    return _finish(field_name, left.get("value"), right.get("value"), expected, tolerance)


def _unread_reason(field_name, left, right):
    if left.get("status") == "missing" and right.get("status") == "missing":
        return field_name + " 两侧都未能读取，不能视为一致"
    if left.get("status") == "unsupported" and right.get("status") == "unsupported":
        return field_name + " 当前接口不能读取，不能视为一致"
    return field_name + " 证据不足：" + (right.get("reason") or left.get("reason") or "未读取")


def _compare_items(field_name, left_items, right_items, expected, tolerance):
    confirmed = []
    unexpected = []
    states = []
    left_ids = set(left_items)
    right_ids = set(right_items)
    if left_ids != right_ids:
        only_left = sorted(left_ids - right_ids)
        only_right = sorted(right_ids - left_ids)
        same_count = len(left_items) == len(right_items)
        reason = "稳定标识无法对应"
        if same_count:
            reason = "数量相同，但稳定标识无法对应，不能按数量通过"
        unexpected.append({"path": field_name, "reason": reason, "missing": only_left, "added": only_right})
        states.append(FAIL)
    for item_id in sorted(left_ids & right_ids):
        left_attrs = left_items[item_id]
        right_attrs = right_items[item_id]
        if not isinstance(left_attrs, dict) or not isinstance(right_attrs, dict):
            states.append(UNKNOWN)
            continue
        for attr in sorted(set(left_attrs) | set(right_attrs)):
            path = field_name + "." + item_id + "." + attr
            state, why, hit = _cells(
                path,
                left_attrs.get(attr) or missing("属性不存在"),
                right_attrs.get(attr) or missing("属性不存在"),
                expected,
                tolerance,
            )
            states.append(state if state != "expected" else PASS)
            if hit:
                confirmed.append({"path": path, "value": right_attrs.get(attr, {}).get("value")})
            elif state == FAIL:
                unexpected.append({"path": path, "reason": why or "属性发生变化"})
    return _fold(field_name, states, confirmed, unexpected)


def _cells(path, left, right, expected, tolerance):
    state = _cell_state(left, right, tolerance)
    if left.get("status") == "read" and right.get("status") == "read":
        for item in expected:
            if item["path"] == path and item["value"] == right.get("value") and item["value"] != left.get("value"):
                return "expected", "", True
    if state == PASS:
        for item in expected:
            if item["path"] == path and item["value"] != right.get("value"):
                return FAIL, "授权修改未在候选中成立", False
        return PASS, "", False
    if state == FAIL:
        if path.endswith(".layer"):
            return FAIL, "图层归属发生变化", False
        return FAIL, "属性与基线不一致", False
    return UNKNOWN, _unread_reason(path, left, right), False


def _cell_state(left, right, tolerance):
    if left.get("status") != "read" or right.get("status") != "read":
        if {left.get("status"), right.get("status")} == {"read", "missing"}:
            return FAIL
        return UNKNOWN
    return _values(left.get("value"), right.get("value"), tolerance)


def _values(left, right, tolerance):
    if isinstance(left, bool) or isinstance(right, bool):
        return PASS if left == right else FAIL
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        if left == right:
            return PASS
        if tolerance is None:
            return UNKNOWN
        return PASS if abs(left - right) <= tolerance else FAIL
    return PASS if left == right else FAIL


def _finish(path, left, right, expected, tolerance):
    state = _values(left, right, tolerance)
    if state == UNKNOWN and not isinstance(left, (int, float)):
        state = PASS if left == right else FAIL
    status, reason, hit = _cells(path, {"status": "read", "value": left}, {"status": "read", "value": right}, expected, tolerance)
    # _cells re-compares; numeric unknown must survive when no expected change applies
    if state == UNKNOWN and not hit:
        return UNKNOWN, "缺少比较阈值，不能把数值差当成一致或失败", [], []
    confirmed = [{"path": path, "value": right}] if hit else []
    extra = [] if status != FAIL else [{"path": path, "reason": reason}]
    folded = PASS if status == "expected" else status
    return folded, reason or ("一致" if folded == PASS else ""), confirmed, extra


def _fold(field_name, states, confirmed, unexpected):
    if FAIL in states:
        reason = unexpected[0]["reason"] if unexpected else field_name + " 与基线不一致"
        return FAIL, reason, confirmed, unexpected
    if UNKNOWN in states:
        return UNKNOWN, field_name + " 有属性未能读取，不能视为一致", confirmed, unexpected
    if states and all(item == PASS for item in states):
        return PASS, field_name + " 在稳定标识上与基线一致", confirmed, unexpected
    if not states:
        return PASS, field_name + " 两侧都为空集合", confirmed, unexpected
    return UNKNOWN, field_name + " 没有足够证据", confirmed, unexpected
