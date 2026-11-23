"""Preflight local write roots without creating or changing any files."""
from pathlib import Path


def paths_overlap(first, second):
    """Whether resolved paths coincide or one contains the other; follows existing symlinks."""
    first = Path(first).resolve()
    second = Path(second).resolve()
    return first == second or first in second.parents or second in first.parents


def validate_write_roots(write_roots, *, package_root, protected_inputs=()):
    """Return resolved named write roots, or raise ValueError before any write.

    Roots may already exist and may overlap each other for replay. They must not
    overlap the skill package or explicitly protected source files/directories.
    This validates the declared roots; callers still control their output names.
    """
    package_root = Path(package_root).resolve()
    protected = tuple(Path(path).resolve() for path in protected_inputs)
    resolved = {name: Path(path).resolve() for name, path in write_roots.items()}
    for name, path in resolved.items():
        if paths_overlap(path, package_root):
            raise ValueError(f"{name} overlaps the skill package: {path}")
        for source in protected:
            if paths_overlap(path, source):
                raise ValueError(f"{name} overlaps a protected input: {source}")
    return resolved
