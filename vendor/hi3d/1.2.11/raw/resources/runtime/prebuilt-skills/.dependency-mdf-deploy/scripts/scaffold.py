"""Create an independent service starter without modifying an existing project."""
import argparse
from pathlib import Path
import shutil


def scaffold(output):
    """Copy bundled, non-secret templates to a new directory; never overwrite."""
    target = Path(output).absolute()
    source = Path(__file__).resolve().parents[1] / "assets" / "service"
    if target.exists() or target.is_symlink():
        raise FileExistsError("Output must be a new directory")
    if not (source / "service.py").is_file():
        raise FileNotFoundError("Incomplete skill package: service templates missing")
    if any(path.is_symlink() for path in source.rglob("*")):
        raise ValueError("Service templates must not contain symlinks")
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    target = scaffold(args.output)
    print(f"Created {target}; adapt algorithm.py and supply a pinned full MDF3 SDK before deployment")


if __name__ == "__main__":
    main()
