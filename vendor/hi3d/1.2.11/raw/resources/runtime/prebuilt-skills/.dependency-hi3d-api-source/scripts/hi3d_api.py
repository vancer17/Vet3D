"""Plan, submit, track and download Hi3D tasks. Use --help on each subcommand."""

import argparse
import json
import sys

from hi3d_artifacts import download_job
from hi3d_client import CREATE, Client
from hi3d_jobs import adopt_job, job_outcome, query_job, submit_job, wait_job
from hi3d_parameters import build_plan, load_defaults
from hi3d_storage import public_record, save
from web_option_gates import gate_parameter_overrides


def _add_selection_arguments(command):
    command.add_argument('--session', help='Task-directory pcg.session.v1 with Hi3D parameter selections')


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    sub.add_parser("defaults")
    balance = sub.add_parser("balance")
    balance.add_argument("--out")
    submit = sub.add_parser("submit")
    submit.add_argument("kind", choices=CREATE)
    submit.add_argument("--image", action="append", default=[])
    for option in ("views", "image-url", "mesh", "mesh-url"):
        submit.add_argument("--" + option)
    submit.add_argument("--set", action="append", default=[])
    submit.add_argument("--job", required=True)
    submit.add_argument("--dry-run", action="store_true")
    _add_selection_arguments(submit)
    adopt = sub.add_parser("adopt")
    adopt.add_argument("kind", choices=CREATE)
    adopt.add_argument("task_id")
    adopt.add_argument("--job", required=True)
    for command in ("query", "wait", "download"):
        item = sub.add_parser(command)
        item.add_argument("--job", required=True)
        if command == "wait":
            item.add_argument("--seconds", type=float, default=50)
            item.add_argument("--interval", type=float, default=20)
        if command == "download":
            item.add_argument("--out", required=True)
    return root


def execute(args, client_factory=Client):
    if args.command == "defaults":
        return load_defaults(), 0
    if args.command == "adopt":
        return {"adopted": True, "job": adopt_job(args.kind, args.task_id, args.job)}, 0
    if args.command == "submit":
        gate, rewritten = gate_parameter_overrides(
            args.kind,
            overrides=args.set,
            session=getattr(args, 'session', None),
            has_mesh=bool(args.mesh or args.mesh_url),
        )
        if not args.dry_run and gate['result'] != 'ready':
            return gate, 2
        planned = build_plan(
            args.kind,
            images=args.image,
            views=args.views,
            image_url=args.image_url,
            mesh=args.mesh,
            mesh_url=args.mesh_url,
            overrides=rewritten,
        )
        if args.dry_run:
            return {"dry_run": True, **planned, 'consent': gate}, 0
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
        return job, job_outcome(job)[1]
    if args.command == "wait":
        return wait_job(client, args.job, args.seconds, args.interval)
    return download_job(client, args.job, args.out), 0


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result, code = execute(args)
    except Exception as error:  # noqa: BLE001 - suppress response/transport details at the reporting boundary
        result, code = (
            {
                "error_type": type(error).__name__,
                "message": "Operation stopped. Check local inputs and the job state; never retry an uncertain submission.",
            },
            2,
        )
    print(
        json.dumps(public_record(result), ensure_ascii=False, indent=2, allow_nan=False)
    )
    return code


if __name__ == "__main__":
    sys.exit(main())
