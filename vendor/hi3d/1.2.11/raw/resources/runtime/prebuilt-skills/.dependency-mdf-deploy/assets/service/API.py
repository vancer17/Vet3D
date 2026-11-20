"""Stable local path API. No MDF3 types and no per-request model loading."""
from pathlib import Path
import tempfile


def infer(session, source, target, options):
    """Validate, infer into a sibling temporary file, read back, then publish."""
    source, target = Path(source).resolve(), Path(target).resolve()
    if not source.is_file() or source.stat().st_size == 0:
        raise ValueError("Input file is missing or empty")
    if source == target or source.suffix.lower() not in session.input_suffixes:
        raise ValueError("Invalid input path or suffix")
    if target.suffix.lower() != session.output_suffix:
        raise ValueError("Unexpected output suffix")
    options = session.validate_options(options)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".mdf-output-", dir=target.parent) as directory:
        staged = Path(directory) / ("result" + session.output_suffix)
        session.infer(source, staged, options)
        if not staged.is_file() or staged.stat().st_size == 0:
            raise RuntimeError("Algorithm produced no output")
        metadata = session.validate_output(source, staged, options)
        staged.replace(target)
    return metadata
