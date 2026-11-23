#!/usr/bin/env python3
"""Byte-exact asset transport; no image/mesh editing, network, or credentials."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def verify(manifest_path):
    manifest_path = Path(manifest_path)
    root = manifest_path.resolve().parent
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    total = 0
    combined = hashlib.sha256()
    seen = set()
    if not data["parts"]:
        raise ValueError("Manifest has no parts")
    for part in data["parts"]:
        name = part["file"]
        if not isinstance(name, str) or Path(name).name != name or name in seen:
            raise ValueError("Part names must be unique plain filenames")
        seen.add(name)
        path = root / name
        if path.resolve().parent != root:
            raise ValueError("Part escapes the manifest directory")
        blob = path.read_bytes()
        if len(blob) != part["bytes"] or hashlib.sha256(blob).hexdigest() != part["sha256"]:
            raise ValueError(f"Part integrity mismatch: {name}")
        combined.update(blob)
        total += len(blob)
    if total != data["source_bytes"] or combined.hexdigest() != data["source_sha256"]:
        raise ValueError("Reassembled asset integrity mismatch")
    return {"verified": True, "bytes": total, "parts": len(seen), "sha256": combined.hexdigest()}


def split(source, output, chunk_mib=20, url_prefix=None):
    source, output = Path(source), Path(output)
    if not math.isfinite(chunk_mib) or chunk_mib <= 0:
        raise ValueError("chunk-mib must be positive and finite")
    chunk_bytes = int(chunk_mib * 1024 * 1024)
    if chunk_bytes < 1:
        raise ValueError("chunk-mib is smaller than one byte")
    if not source.is_file() or source.stat().st_size == 0:
        raise ValueError("Source must be a nonempty file")
    # An existing directory is deliberately refused, including partial earlier output.
    output.mkdir(parents=True, exist_ok=False)
    parts, total, digest = [], 0, hashlib.sha256()
    with source.open("rb") as stream:
        index = 0
        while True:
            blob = stream.read(chunk_bytes)
            if not blob:
                break
            name = f"part{index:04d}.bin"
            (output / name).write_bytes(blob)
            entry = {"file": name, "bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()}
            if url_prefix is not None:
                entry["url"] = url_prefix.rstrip("/") + "/" + name
            parts.append(entry)
            digest.update(blob)
            total += len(blob)
            index += 1
    manifest = {"schema_version": 1, "source_name": source.name,
                "source_bytes": total, "source_sha256": digest.hexdigest(),
                "parts": parts, "preservation": "Byte-exact transport; no transformations."}
    path = output / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"manifest": str(path.resolve()), **verify(path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?")
    parser.add_argument("output", nargs="?")
    parser.add_argument("--chunk-mib", type=float, default=20)
    parser.add_argument("--url-prefix")
    parser.add_argument("--verify", metavar="MANIFEST")
    args = parser.parse_args()
    if args.verify and (args.source or args.output or args.url_prefix):
        parser.error("--verify cannot be combined with source/output/url-prefix")
    if not args.verify and not (args.source and args.output):
        parser.error("source and output are required unless using --verify")
    try:
        result = verify(args.verify) if args.verify else split(args.source, args.output, args.chunk_mib, args.url_prefix)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Asset operation failed: {error}\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
