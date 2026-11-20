#!/usr/bin/env python3
"""File/CLI adapter for the internal head-reference review gate (stdlib only)."""
import argparse
import hashlib
import html
import json
from pathlib import Path

import reference_review_core as core


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def file_record(role, path):
    path = Path(path).resolve(strict=True)
    core.require(path.is_file() and path.stat().st_size > 0, "Empty/non-file input: " + role)
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
    return {"role": role, "path": str(path), "sha256": sha.hexdigest()}


def prepare(manifest_path, base_path, policy_path, evaluator):
    manifest_path = Path(manifest_path).resolve(strict=True)
    manifest = read_json(manifest_path)
    core.require(manifest.get("schema") == 1 and manifest.get("mode") in core.VIEWS,
                 "Invalid input manifest")
    view_ids = core.views_for(manifest["mode"], manifest.get("pose_mode"))
    views = set(view_ids)
    for field in ("images", "prompts", "generation_inputs"):
        core.require(isinstance(manifest.get(field), dict) and set(manifest[field]) == views,
                     "Exact view mapping required: " + field)
    for field in ("neck_crop", "appearance", "required_shape_constraints"):
        core.require(isinstance(manifest.get(field), str), "Missing context: " + field)
    files = []

    def add(role, value):
        core.require(core.nonempty(value), "Input path required: " + role)
        path = Path(value)
        files.append(file_record(role, path if path.is_absolute() else manifest_path.parent / path))

    add("source", manifest["source"])
    for view in view_ids:
        add("image/" + view, manifest["images"][view])
        add("prompt/" + view, manifest["prompts"][view])
        inputs = manifest["generation_inputs"][view]
        core.require(isinstance(inputs, list) and inputs, "Actual generation inputs required")
        for i, value in enumerate(inputs):
            add(f"generation/{view}/{i}", value)
    examples = manifest.get("examples", [])
    core.require(isinstance(examples, list), "Examples must be a list")
    policies = [read_json(base_path)] + ([read_json(policy_path)] if policy_path else [])
    criteria = core.criteria_for(manifest["mode"], manifest["appearance"], policies, manifest.get("pose_mode"))
    for i, example in enumerate(examples):
        core.require(example.get("criterion") in {c["id"] for c in criteria} and
                     example.get("verdict") in {"positive", "negative"} and
                     core.nonempty(example.get("note")), "Example needs a scoped criterion, verdict and note")
        add(f"example/{i}", example["path"])
    implementation = {name: file_record(name, Path(__file__).with_name(name))["sha256"]
                      for name in ("reference_review.py", "reference_review_core.py")}
    snapshot = {"manifest": manifest, "files": files}
    return core.make_request(snapshot, policies, evaluator, implementation)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Reports/reviews are immutable artifacts; explicitly choose a new path for each run.
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def report_html(request, response, decision):
    escape = lambda value: html.escape(str(value), quote=True)
    by_key = {c["key"]: c for c in response["checks"]}
    rows = []
    for criterion in request["criteria"]:
        c = by_key[criterion["key"]]
        rows.append("<tr>" + "".join("<td>" + escape(value) + "</td>" for value in (
            c["key"], criterion["title"], c["status"], c["rating"], c["observation"],
            json.dumps(c["evidence"], ensure_ascii=False))) + "</tr>")
    return """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>参考图评审</title>
<style>body{font:16px system-ui;max-width:1200px;margin:32px auto;padding:0 20px;color:#222}
table{border-collapse:collapse;width:100%}td,th{padding:12px;border:1px solid #ddd;text-align:left}
td{overflow-wrap:anywhere}code{overflow-wrap:anywhere}.scroll{overflow:auto}p{line-height:1.7}</style>
<h1>参考图评审 · """ + escape(decision["state"]) + "</h1><p>" + escape(
        f"观察评分（未校准）：{decision['ordinal_points']}/{decision['ordinal_max']}；"
        f"已评分 {decision['rated_checks']}/{decision['total_checks']} 项。评分不能抵消硬性失败。"
        "这是静态检查记录，不是自动检测结果或提交服务按钮。") + "</p><p>视角模式：" + escape(
            request["view_frame"]["pose_mode"] + " / " + request["view_frame"]["kind"]) + "</p><p>版本：<code>" + escape(
            decision["request_id"]) + "</code></p><div class='scroll'><table><thead><tr>" + "".join(
            "<th>" + title + "</th>" for title in ("视图 / 项", "要求", "状态", "0–3", "观察依据", "证据")) + \
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div><h2>修订建议</h2><pre>" + escape(
            json.dumps(decision["repair_proposals"], ensure_ascii=False, indent=2)) + \
        "</pre><p>放行还需实际人工确认；本报告不能覆盖输入变化，交接前必须重新运行 check。</p></html>"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "check"))
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--base-policy", required=True)
    parser.add_argument("--policy", help="Optional caller-specific policy; never replaces base checks")
    parser.add_argument("--evaluator", required=True)
    parser.add_argument("--evaluator-version", required=True)
    parser.add_argument("--output", required=True, help="New output JSON, never overwritten")
    parser.add_argument("--response", help="prepare: new template path; check: completed input JSON")
    parser.add_argument("--retry-counts", help="Host-maintained JSON mapping view/criterion to targeted revisions")
    parser.add_argument("--confirmation", help="Human-confirmed decision JSON; not produced by evaluator")
    parser.add_argument("--html", help="Optional new static review HTML alongside existing workflow page")
    args = parser.parse_args()
    try:
        request = prepare(args.manifest, args.base_policy, args.policy,
                          {"name": args.evaluator, "version": args.evaluator_version})
        if args.command == "prepare":
            core.require(not args.confirmation and not args.retry_counts and not args.html,
                         "prepare does not accept check-only arguments")
            write_json(args.output, request)
            if args.response:
                write_json(args.response, core.response_template(request))
            print(json.dumps({"request_id": request["request_id"], "checks": len(request["criteria"])}))
            return 0
        core.require(args.response is not None, "check requires --response")
        response = read_json(args.response)
        decision = core.assess(request, response,
                               read_json(args.retry_counts) if args.retry_counts else None,
                               read_json(args.confirmation) if args.confirmation else None)
        write_json(args.output, decision)
        if args.html:
            path = Path(args.html)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("x", encoding="utf-8") as stream:
                stream.write(report_html(request, response, decision))
        print(json.dumps({"state": decision["state"], "approved": decision["approved"]}))
        return 0 if decision["approved"] else 2
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(1, "Review blocked: " + str(error) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
