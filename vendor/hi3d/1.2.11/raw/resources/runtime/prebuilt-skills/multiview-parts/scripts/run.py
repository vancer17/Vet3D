"""Public Python/Blender entrypoint; delegate to the single pipeline implementation."""
import importlib.util
from pathlib import Path
import sys


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if argv is None and "--" in arguments:
        arguments = arguments[arguments.index("--") + 1:]
    path = Path(__file__).resolve().parent / "parts_pipeline.py"
    spec = importlib.util.spec_from_file_location("multiview_parts_pipeline", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
