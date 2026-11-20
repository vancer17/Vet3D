"""Look up a DCC preset and, when asked, apply that one operation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from catalog import get_preset, lookup, parse_version, version_ok
from unreal_project import apply_enable


def emit(payload, output):
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if output:
        destination = Path(output)
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "result.json").write_text(text, encoding="utf-8")
    sys.stdout.write(text)


def status_code(payload):
    status = payload.get("status")
    if status in (None, "ok", "ready", "dry_run", "applied", "already_enabled"):
        return 0
    if status == "blocked":
        return 3
    if status == "rejected":
        return 2
    return 1


def command_lookup(args):
    try:
        rows = lookup(
            app=args.app,
            topic=args.topic,
            version=args.version,
            preset_id=args.preset,
        )
    except ValueError as exc:
        return {"status": "rejected", "reason": str(exc), "presets": []}
    return {"status": "ok", "presets": rows}


def command_apply(args, runner):
    preset = get_preset(args.preset)
    if preset is None:
        return {"status": "rejected", "reason": "unknown preset", "preset": args.preset}
    if preset["operation"] == "enable_plugins":
        if not args.project:
            return {"status": "rejected", "reason": "unreal preset needs --project", "preset": args.preset}
        try:
            return apply_enable(args.project, args.preset, args.engine_version, write=args.write)
        except (OSError, ValueError) as exc:
            return {"status": "rejected", "reason": str(exc), "preset": args.preset}
    return apply_host(preset, args, runner)


def apply_host(preset, args, runner):
    found = parse_version(args.version) if args.version else None
    if args.version and found is None:
        return {"status": "rejected", "reason": "version must look like 20.5 or 4.2.1", "preset": preset["id"]}
    if not version_ok(found, preset["min_version"]):
        return {
            "status": "rejected",
            "reason": "pass --version at or above %s" % ".".join(str(part) for part in preset["min_version"]),
            "preset": preset["id"],
        }
    if preset["operation"] == "create_sop":
        binary = args.hython
        script = "houdini_ocean_spectrum.py"
        suffix = ".hip"
    elif preset["operation"] == "add_fluid_domain":
        binary = args.blender
        script = "blender_fluid_domain.py"
        suffix = ".blend"
    else:
        return {"status": "rejected", "reason": "preset has no apply operation", "preset": preset["id"]}
    if not args.output:
        return {"status": "rejected", "reason": "host preset needs --output", "preset": preset["id"]}
    destination = Path(args.output) / ("preset" + suffix)
    payload = {
        "preset": preset["id"],
        "output": str(destination),
        "version_source": "caller",
        "engine_version": "%d.%d.%d" % found,
    }
    if not binary:
        payload.update(status="blocked", reason="host executable was not provided")
        return payload
    if not args.write:
        payload.update(status="dry_run")
        return payload
    script_path = Path(__file__).resolve().parent / script
    if preset["operation"] == "add_fluid_domain":
        command = [
            binary,
            "--background",
            "--factory-startup",
            "--python-exit-code",
            "1",
            "--python",
            str(script_path),
            "--",
            str(destination),
        ]
    else:
        command = [binary, str(script_path), str(destination)]
    Path(args.output).mkdir(parents=True, exist_ok=True)
    completed = runner(command)
    if completed.returncode != 0:
        payload.update(status="rejected", reason="host command failed", returncode=completed.returncode)
        return payload
    if not destination.is_file():
        payload.update(status="rejected", reason="host finished without the preset file")
        return payload
    payload.update(status="applied")
    return payload


def parser():
    tool = argparse.ArgumentParser(description="Look up and apply one DCC preset.")
    tool.add_argument("--output", help="directory for result.json and host files")
    sub = tool.add_subparsers(dest="command", required=True)
    find = sub.add_parser("lookup")
    find.add_argument("--app", choices=("unreal", "houdini", "blender"))
    find.add_argument("--topic")
    find.add_argument("--version")
    find.add_argument("--preset")
    apply = sub.add_parser("apply")
    apply.add_argument("--preset", required=True)
    apply.add_argument("--project")
    apply.add_argument("--engine-version")
    apply.add_argument("--version")
    apply.add_argument("--blender")
    apply.add_argument("--hython")
    apply.add_argument("--write", action="store_true")
    return tool


def main(argv=None, runner=None):
    args = parser().parse_args(argv)
    if runner is None:
        runner = lambda command: subprocess.run(command, check=False)
    if args.command == "lookup":
        payload = command_lookup(args)
    else:
        payload = command_apply(args, runner)
    emit(payload, args.output)
    return status_code(payload)


if __name__ == "__main__":
    sys.exit(main())
