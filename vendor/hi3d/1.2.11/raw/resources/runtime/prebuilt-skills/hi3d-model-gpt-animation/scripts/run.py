"""Dispatch stage commands with an explicitly provided rig-retarget dependency."""

import argparse
import importlib
import sys
from pathlib import Path

COMMANDS = (
    "contact_check",
    "contact_sheet",
    "embed_cloth",
    "render_samples",
    "stage_ops",
    "self_test",
    "test_cloth_contacts",
)


def arguments(argv=None):
    """Accept explicit arguments or Blender's arguments after its -- separator."""
    if argv is not None:
        return list(argv)
    values = sys.argv[1:]
    return values[values.index("--") + 1 :] if "--" in values else values


def dispatch(command, argv, rig_skill=None):
    """Import one capability lazily and execute its CLI adapter."""
    if command not in COMMANDS:
        raise ValueError("Unknown skill command")
    if rig_skill is None:
        raise ValueError(
            "Provide --rig-skill with the separately supplied rig-retarget package"
        )
    dependency = Path(rig_skill).expanduser().resolve()
    if not (dependency / "scripts/rigging/blend_common.py").is_file():
        raise ValueError("Invalid rig-retarget package path")
    sys.path.insert(0, str(dependency / "scripts"))
    directory = str(Path(__file__).resolve().parent)
    if directory not in sys.path:
        sys.path.insert(0, directory)
    module = importlib.import_module("character." + command)
    return module.main(argv)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rig-skill",
        help="Explicit rig-retarget package providing shared Blender primitives",
    )
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    options = parser.parse_args(arguments(argv))
    return dispatch(options.command, options.arguments, options.rig_skill)


if __name__ == "__main__":
    sys.exit(main())
