"""Argument/path boundaries; importing this module never starts work."""
from pathlib import Path
import sys

def cli_arguments(argv=None):
    if argv is not None:
        return list(argv)
    return sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]

def validate_paths(options):
    """Normalize explicit paths and reject missing inputs or in-package outputs.

    Mutates only the provided Namespace. No file or scene changes occur here.
    `frames` is a directory only in application_demo, otherwise a frame selector.
    """
    for name in ('source', 'scene', 'library', 'heightfield', 'heightfields', 'config', 'artwork', 'input', 'model'):
        value = getattr(options, name, None)
        if value is not None:
            path = Path(value).expanduser().resolve()
            if not path.exists():
                raise FileNotFoundError(f'{name}: {path}')
            setattr(options, name, path)
    package = Path(__file__).resolve().parents[1]
    for name in ('output',):
        value = getattr(options, name, None)
        if value is not None:
            path = Path(value).expanduser().resolve()
            if path == package or package in path.parents:
                raise ValueError('Runtime outputs must stay outside the Skill package')
            setattr(options, name, path)


def load_config(path, *, required=()):
    """Read a JSON object and reject absent required fields before modeling."""
    import json
    config=json.loads(Path(path).read_text())
    if not isinstance(config,dict):raise ValueError('Configuration must be a JSON object')
    missing=[k for k in required if k not in config]
    if missing:raise ValueError('Missing required config: '+', '.join(missing))
    return config


def resolve_file_request(inputs, write_roots, *, package_root):
    """Resolve existing input files and protect them/the caller package from writes.

    Returns (resolved inputs, resolved write roots); creates nothing. Existing
    output roots and overlaps between them remain allowed for local continuation.
    """
    from path_safety import validate_write_roots
    resolved = {name: Path(path).resolve() for name,path in inputs.items()}
    for name,path in resolved.items():
        if not path.is_file():raise FileNotFoundError(f'{name}: {path}')
    roots = validate_write_roots(write_roots, package_root=package_root,
                                 protected_inputs=resolved.values())
    return resolved, roots
