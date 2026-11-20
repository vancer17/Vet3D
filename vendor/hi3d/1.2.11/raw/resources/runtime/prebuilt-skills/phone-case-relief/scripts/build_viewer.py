#!/usr/bin/env python3
"""Embed one self-contained GLB in a bilingual HTML viewer (CDN runtime)."""

import argparse
import sys
import hashlib
import html
import json
from pathlib import Path
import re
import struct
from typing import Any, Dict, Optional, Sequence


sys.path.insert(0,str(Path(__file__).resolve().parent))
from page_assets import encode_asset, render_template, read_asset

JSON_CHUNK_TYPE = 0x4E4F534A
ORBIT_PART = re.compile(r"[A-Za-z0-9.+%_-]+")
TEMPLATE_TOKENS = (
    "__MODEL_DATA__",
    "__MODEL_NAME_HTML__",
    "__MODEL_NAME_JS__",
    "__EXTERIOR_ORBIT__",
    "__INTERIOR_ORBIT__",
)


class ViewerError(ValueError):
    """Raised when a viewer input or template violates the package contract."""


def validate_orbit(value: str) -> str:
    """Return a safe three-part model-viewer camera orbit."""
    parts = value.split()
    if len(parts) != 3 or any(ORBIT_PART.fullmatch(part) is None for part in parts):
        raise ViewerError("Orbit must contain three safe angle/distance values")
    return " ".join(parts)


def parse_glb_document(data: bytes) -> Dict[str, Any]:
    """Validate the GLB 2 header/JSON chunk and return its JSON document."""
    if len(data) < 20:
        raise ViewerError("Truncated GLB")
    magic, version, declared_size = struct.unpack_from("<4sII", data)
    if magic != b"glTF" or version != 2 or declared_size != len(data):
        raise ViewerError("Invalid GLB 2 container header")
    chunk_size, chunk_type = struct.unpack_from("<II", data, 12)
    chunk_end = 20 + chunk_size
    if chunk_type != JSON_CHUNK_TYPE or chunk_end > len(data):
        raise ViewerError("Missing or truncated glTF JSON chunk")
    try:
        document = json.loads(data[20:chunk_end])
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ViewerError("Invalid glTF JSON chunk") from exc
    if not isinstance(document, dict):
        raise ViewerError("glTF JSON root must be an object")
    return document


def validate_embeddable_document(document: Dict[str, Any]) -> None:
    """Reject mesh-free files and GLBs that still depend on external resources."""
    meshes = document.get("meshes")
    if not isinstance(meshes, list) or not meshes:
        raise ViewerError("GLB contains no meshes")
    buffers = document.get("buffers", [])
    images = document.get("images", [])
    if not isinstance(buffers, list) or not isinstance(images, list):
        raise ViewerError("glTF buffers and images must be arrays")
    resources = buffers + images
    for entry in resources:
        if not isinstance(entry, dict):
            raise ViewerError("Invalid buffer or image entry")
        uri = entry.get("uri", "")
        if uri and not str(uri).startswith("data:"):
            raise ViewerError("GLB has external resources; pack them before embedding")


def load_glb(path: Path) -> bytes:
    """Read and validate one local, self-contained GLB file."""
    if path.suffix.lower() != ".glb":
        raise ViewerError("Expected a .glb input")
    try:
        data, _ = read_asset(path.parent,path.name)
    except (OSError, ValueError) as exc:
        raise ViewerError(f"Unable to read GLB: {exc}") from exc
    document = parse_glb_document(data)
    validate_embeddable_document(document)
    return data


def render_page(
    template: str,
    model_data: bytes,
    model_name: str,
    exterior_orbit: str,
    interior_orbit: str,
) -> str:
    """Replace every required template token and return the completed page."""
    replacements = {
        "__MODEL_DATA__": encode_asset(model_data),
        "__MODEL_NAME_HTML__": html.escape(model_name, quote=True),
        "__MODEL_NAME_JS__": json.dumps(model_name, ensure_ascii=True).replace("<", r"\u003c"),
        "__EXTERIOR_ORBIT__": html.escape(exterior_orbit, quote=True),
        "__INTERIOR_ORBIT__": html.escape(interior_orbit, quote=True),
    }
    try:
        return render_template(template,replacements)
    except ValueError as exc:
        raise ViewerError(str(exc)) from exc


def write_new_text(path: Path, content: str) -> None:
    """Write UTF-8 text without overwriting an existing output."""
    if path.suffix.lower() != ".html":
        raise ViewerError("Expected an .html output")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as stream:
            stream.write(content)
    except FileExistsError as exc:
        raise ViewerError("Output exists; choose a new filename") from exc
    except OSError as exc:
        raise ViewerError(f"Unable to write HTML: {exc}") from exc


def build_viewer(
    model: Path,
    output: Path,
    language: str,
    exterior_orbit: str,
    interior_orbit: str,
    template_dir: Path,
) -> Dict[str, Any]:
    """Build a viewer and return a machine-readable delivery summary."""
    if language not in {"zh", "en"}:
        raise ViewerError("Language must be zh or en")
    exterior = validate_orbit(exterior_orbit)
    interior = validate_orbit(interior_orbit)
    source = model.resolve()
    target = output.resolve()
    data = load_glb(source)
    template_path = template_dir / f"viewer_{language}.html"
    try:
        template = template_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ViewerError(f"Unable to read viewer template: {exc}") from exc
    page = render_page(template, data, source.name, exterior, interior)
    write_new_text(target, page)
    return {
        "html": str(target),
        "model": source.name,
        "language": language,
        "model_sha256": hashlib.sha256(data).hexdigest(),
        "html_bytes": target.stat().st_size,
        "viewer_requires_network": True,
        "browser_interaction_tested": False,
    }


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse the small CLI surface; both model-specific camera orbits are required."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--lang", choices=("zh", "en"), default="zh")
    parser.add_argument("--exterior-orbit", required=True)
    parser.add_argument("--interior-orbit", required=True)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI adapter for the reusable validation and rendering functions."""
    args = parse_args(argv)
    try:
        result = build_viewer(
            model=args.model,
            output=args.output,
            language=args.lang,
            exterior_orbit=args.exterior_orbit,
            interior_orbit=args.interior_orbit,
            template_dir=Path(__file__).resolve().parent.parent / "assets",
        )
    except ViewerError as exc:
        raise SystemExit(f"error: {exc}") from exc
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
