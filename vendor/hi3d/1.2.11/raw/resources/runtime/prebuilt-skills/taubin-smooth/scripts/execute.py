"""Run an explicitly selected installed package script/module in background Blender."""
import argparse
from pathlib import Path
import runpy
import sys


def execute(*, script=None, module=None, scripts=None, arguments=()):
    """Add only the explicitly selected package's scripts directory, then run its entry.

    The target is trusted package code, not a sandbox. It may mutate this background
    scene and write its declared outputs. Arguments and exceptions are preserved.
    """
    if bool(script) == bool(module):
        raise ValueError('Choose one script or module')
    directory = Path(script).resolve().parent if script else Path(scripts).resolve()
    if not directory.is_dir() or (script and not Path(script).is_file()):
        raise FileNotFoundError(str(directory))
    sys.path.insert(0, str(directory))
    sys.argv = [str(script or module), *arguments]
    if script:
        return runpy.run_path(str(Path(script).resolve()), run_name='__main__')
    return runpy.run_module(module, run_name='__main__')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--script', type=Path)
    group.add_argument('--module')
    parser.add_argument('--scripts', type=Path, help='Installed scripts directory for --module')
    args, remaining = parser.parse_known_args(argv)
    if args.module and args.scripts is None:
        parser.error('--module requires --scripts')
    return execute(script=args.script, module=args.module, scripts=args.scripts, arguments=remaining)


if __name__ == '__main__':
    main(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
