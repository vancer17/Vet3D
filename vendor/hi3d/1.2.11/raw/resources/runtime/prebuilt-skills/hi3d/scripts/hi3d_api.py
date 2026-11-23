"""Plan, submit, track and download account-backed Hi3D tasks. Use --help on each subcommand."""

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _candidate in (_HERE, _HERE.parent):
    if (_candidate / "web_option_gates.py").is_file():
        _added = str(_candidate)
        if _added not in sys.path:
            sys.path.insert(0, _added)
        break

from hi3d_artifacts import download_job, export_image
from hi3d_client import CREATE, Client
from hi3d_jobs import (
    adopt_job, job_outcome, query_job, read_retry_quota, retry_parent, retry_root_id, submit_job, wait_job,
)
from hi3d_parameters import build_plan, image_prompt_budget, load_defaults
from hi3d_progress import emit_progress, job_summary
from hi3d_storage import public_record, save, load, exception_summary, IMAGE_FAILURE_ACTION
from hi3d_generation_workflow import generate_retry_task, generate_task
from hi3d_image_workflow import generate_image, image_plan
from web_option_gates import gate_parameter_overrides


def add_plan_arguments(command):
    command.add_argument("--image", action="append", default=[])
    for option in ("views", "image-url", "mesh", "mesh-url"):
        command.add_argument("--" + option)
    command.add_argument("--image-slots", help="Explicit 3D slots, e.g. 0,2; exclusive with --views")
    command.add_argument("--request", help="Native hi3d-codex JSON request file")
    command.add_argument("--set", action="append", default=[])
    command.add_argument("--session", help="Task-directory pcg.session.v1 with Hi3D parameter selections")


def plan_arguments(args):
    return dict(images=args.image, views=args.views, image_url=args.image_url,
                mesh=args.mesh, mesh_url=args.mesh_url, overrides=args.set,
                request=args.request, image_slots=args.image_slots)


def progress_reporter(args):
    return None if args.progress == "none" else lambda snapshot: emit_progress(snapshot, sys.stderr, args.progress)


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    sub.add_parser("defaults")
    check = sub.add_parser("check-image-prompt", help="Count prompt characters offline before image generation")
    check.add_argument("--prompt-file", required=True, help="UTF-8 file containing the exact final prompt")
    export = sub.add_parser("export-image")
    export.add_argument("--source", required=True)
    export.add_argument("--out", required=True)
    image = sub.add_parser("generate-image", help="Validate, submit once, wait and download in one invocation")
    image.add_argument("--kind", choices=("text-to-image", "image-edit"), default="text-to-image")
    add_plan_arguments(image)
    image.add_argument("--prompt", required=True)
    image.add_argument("--model", default=load_defaults()["parameters"]["text-to-image"]["modelName"])
    image.add_argument("--aspect-ratio", default="1:1", choices=("1:1", "16:9", "9:16", "4:3", "3:4"))
    image.add_argument("--count", type=int, default=1, choices=range(1, 5))
    image.add_argument("--job", required=True)
    image.add_argument("--out", required=True)
    image.add_argument("--seconds", type=float, default=1800)
    image.add_argument("--interval", type=float, default=30)
    image.add_argument("--progress", choices=("text", "json", "none"), default="none")
    image.add_argument("--dry-run", action="store_true")
    balance = sub.add_parser("balance")
    balance.add_argument("--out")
    quota = sub.add_parser("retry-quota", help="Read remaining free retries for an existing 3D task")
    quota.add_argument("--task-id")
    quota.add_argument("--job")
    retry = sub.add_parser("retry", help="Submit one free retry of an existing 3D task into a new job")
    retry.add_argument("--parent-job")
    retry.add_argument("--parent-task-id")
    retry.add_argument("--kind", choices=("model", "relief", "split", "multicolor"))
    retry.add_argument("--job", required=True)
    retry.add_argument("--out", required=True)
    retry.add_argument("--seconds", type=float, default=1800)
    retry.add_argument("--interval", type=float, default=30)
    retry.add_argument("--progress", choices=("text", "json", "none"), default="none")
    retry.add_argument("--dry-run", action="store_true")
    for command in ("submit", "generate-3d"):
        submit = sub.add_parser(command)
        if command == "submit":
            submit.add_argument("kind", choices=CREATE)
        else:
            submit.add_argument("--kind", choices=("model", "relief", "split", "multicolor"), default="model")
            submit.add_argument("--out", required=True)
            submit.add_argument("--seconds", type=float, default=1800)
            submit.add_argument("--interval", type=float, default=30)
            submit.add_argument("--progress", choices=("text", "json", "none"), default="none")
        add_plan_arguments(submit)
        submit.add_argument("--job", required=True)
        submit.add_argument("--dry-run", action="store_true")
    adopt = sub.add_parser("adopt")
    adopt.add_argument("kind", choices=CREATE)
    adopt.add_argument("task_id")
    adopt.add_argument("--job", required=True)
    for command in ("query", "wait", "download"):
        item = sub.add_parser(command)
        item.add_argument("--job", required=True)
        if command in {"query", "wait"}:
            item.add_argument("--output", choices=("summary", "full"), default="summary",
                              help="Compact progress by default; full includes the entire job")
        if command == "wait":
            item.add_argument("--seconds", type=float, default=1800, help="Wait budget: 0..3600 seconds (default 1800)")
            item.add_argument("--interval", type=float, default=30, help="Polling interval: 5..300 seconds (default 30)")
            item.add_argument("--progress", choices=("text", "json", "none"), default="none",
                              help="Live progress on stderr; stdout remains final JSON")
        if command == "download":
            item.add_argument("--out", required=True)
    return root


def execute(args, client_factory=Client):
    if args.command == "check-image-prompt":
        with Path(args.prompt_file).open(encoding="utf-8", newline="") as source:
            budget = image_prompt_budget(source.read())
        return budget, 0 if budget["valid"] else 1
    if args.command == "export-image":
        return export_image(args.source, args.out), 0
    if args.command == "generate-image":
        gate, rewritten = gate_parameter_overrides(
            args.kind,
            overrides=args.set,
            session=args.session,
            native=True,
        )
        planned_kwargs = plan_arguments(args)
        planned_kwargs["overrides"] = rewritten
        planned = image_plan(args.prompt, args.model, args.aspect_ratio, args.count,
                             kind=args.kind, **planned_kwargs)
        if args.dry_run:
            body = planned["parameters"]["request"]
            return {"dry_run": True, "kind": planned["kind"], "model": body.get("modelName"),
                    "image_count": body.get("imageCount"), "aspect_ratio": body.get("aspectRatio"),
                    "request": body, "file_count": len(planned["files"]), "consent": gate}, 0
        if gate["result"] != "ready":
            return gate, 2
        return generate_image(client_factory(), planned, args.job, args.out, args.seconds, args.interval,
                              on_progress=progress_reporter(args))
    if args.command == "defaults":
        return load_defaults(), 0
    if args.command == "retry-quota":
        if bool(args.task_id) == bool(args.job):
            raise ValueError("retry-quota requires exactly one of --task-id or --job")
        task_id = args.task_id
        client = client_factory()
        if args.job:
            parent = load(args.job)
            if parent.get("backend") != "hi3d-codex-v1":
                raise ValueError("Retry quota requires an account-runtime job")
            client.check_job(parent)
            task_id = retry_root_id(parent)
        result = read_retry_quota(client, task_id)
        return result, 2 if result.get("error") else 0
    if args.command == "retry":
        if bool(args.parent_job) == bool(args.parent_task_id):
            raise ValueError("retry requires exactly one of --parent-job or --parent-task-id")
        parent = load(args.parent_job) if args.parent_job else None
        kind = args.kind or (parent or {}).get("kind")
        task_id = args.parent_task_id or retry_root_id(parent)
        planned = retry_parent(kind, task_id, parent)
        if args.dry_run:
            return {"dry_run": True, **planned}, 0
        client = client_factory()
        if parent is not None:
            client.check_job(parent)
        return generate_retry_task(client, planned, args.job, args.out, args.seconds, args.interval,
                                   on_progress=progress_reporter(args))
    if args.command == "adopt":
        return {"adopted": True, "job": adopt_job(client_factory(), args.kind, args.task_id, args.job)}, 0
    if args.command in {"submit", "generate-3d"}:
        gate, rewritten = gate_parameter_overrides(
            args.kind,
            overrides=args.set,
            session=args.session,
            native=True,
            # A native --request may carry meshUrl; only assert "no mesh" when none is possible.
            has_mesh=None if args.request else bool(args.mesh or args.mesh_url),
        )
        planned_kwargs = plan_arguments(args)
        planned_kwargs["overrides"] = rewritten
        planned = build_plan(args.kind, **planned_kwargs)
        if args.dry_run:
            payload = {"dry_run": True, "consent": gate, **planned} if args.command != "generate-3d" else {
                "dry_run": True, "kind": planned["kind"],
                "request": planned["parameters"]["request"],
                "image_slots": planned["parameters"].get("imageSlots"),
                "file_count": len(planned["files"]), "consent": gate,
            }
            return payload, 0
        if gate["result"] != "ready":
            return gate, 2
        if args.command == "generate-3d":
            return generate_task(client_factory(), planned, args.job, args.out, args.seconds, args.interval,
                                 on_progress=progress_reporter(args))
        result = submit_job(client_factory(), args.job, planned)
        return result, job_outcome(result["job"])[1]
    client = client_factory()
    if args.command == "balance":
        result = client.balance()
        if args.out:
            save(args.out, result, exclusive=True)
        return result, 0
    if args.command == "query":
        job, _ = query_job(client, args.job)
        return (job if args.output == "full" else job_summary(job, args.job)), job_outcome(job)[1]
    if args.command == "wait":
        reporter = progress_reporter(args)
        result, code = wait_job(client, args.job, args.seconds, args.interval,
                               on_progress=reporter)
        if args.output == "summary":
            result = {**result, "job": job_summary(result["job"], args.job)}
        return result, code
    previous_query = load(args.job).get("last_queried_at")
    try:
        return download_job(client, args.job, args.out), 0
    except Exception as error:
        # Only surface an error from this download's status refresh, not an old
        # query error masking an unrelated artifact or filesystem failure.
        try:
            latest = load(args.job)
        except (OSError, ValueError):
            raise error
        if latest.get("last_query_error") and latest.get("last_queried_at") != previous_query:
            outcome, code = job_outcome(latest)
            return {"result": outcome, "phase": "download", "job": job_summary(latest, args.job)}, code
        raise


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result, code = execute(args)
    except Exception as error:  # noqa: BLE001 - suppress response/transport details at the reporting boundary
        summary = exception_summary(error)
        result, code = (
            {
                "error_type": type(error).__name__,
                "error": summary,
                "message": summary["message"],
                "phase": args.command,
                **({"code": error.code} if type(getattr(error, "code", None)) is int else {}),
                **({"job_file": str(args.job)} if getattr(args, "job", None) else {}),
                **({"next_action": IMAGE_FAILURE_ACTION} if args.command in {"generate-image", "export-image"}
                   or getattr(args, "kind", None) in {"text-to-image", "image-edit"} else {}),
            },
            2,
        )
    print(
        json.dumps(public_record(result), ensure_ascii=False, indent=2, allow_nan=False)
    )
    return code


def _stop_on_terminate(_signal_number, _frame):
    """
    宿主终止对话时会向这个进程发 SIGTERM（1 秒后升级 SIGKILL）。
    默认行为直接结束进程，不跑 finally，下载中的 `.download-*` 临时文件会留在工作区。
    抛 SystemExit 让轮询停下并让清理代码执行完。
    """
    raise SystemExit(130)


if __name__ == "__main__":
    import signal

    for name in ("SIGTERM", "SIGINT", "SIGBREAK"):
        handler = getattr(signal, name, None)
        if handler is not None:
            signal.signal(handler, _stop_on_terminate)
    sys.exit(main())
