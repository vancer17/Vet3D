"""Run one rig-retarget capability; optional timing is appended in the task directory."""

import argparse
import importlib
import sys
from pathlib import Path

COMMANDS = (
    "build_character",
    "cache_bvh",
    "make_profile",
    "prepare_mesh",
    "service_rig",
    "validate_blend",
    "weight_graph",
    "rig_adapter",
    "test_blender",
    "test_pipeline",
    "test_service_rig",
    "test_skin_weights",
    "test_weight_graph",
    "test_retarget",
)


def arguments(argv=None):
    values = list(argv) if argv is not None else sys.argv[1:]
    return values[values.index("--") + 1 :] if "--" in values else values


def dispatch(command, argv):
    if command not in COMMANDS:
        raise ValueError("Unknown command")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    return importlib.import_module("rigging." + command).main(argv)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--timing-log")
    p.add_argument("--task-id", default="local")
    p.add_argument("--attempt", default="1")
    p.add_argument("command", choices=COMMANDS)
    p.add_argument("arguments", nargs=argparse.REMAINDER)
    args = p.parse_args(arguments(argv))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    if args.timing_log:
        from rigging.timing import record_stage

        with record_stage(args.timing_log, args.task_id, args.command, args.attempt):
            result = dispatch(args.command, args.arguments)
            if result:
                raise RuntimeError("Capability returned a nonzero result")
            return result
    return dispatch(args.command, args.arguments)


if __name__ == "__main__":
    sys.exit(main())
