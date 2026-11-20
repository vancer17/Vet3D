"""Compose rendered PNGs into a labeled overview and optional ZIP. Requires Pillow."""

import argparse
from image_sheet import write_sheet
import json
import zipfile
from pathlib import Path
from PIL import Image, ImageFont


def compose_sheet(
    manifest, output_path, archive_path=None, columns=3, cell_width=800, font=None
):
    """Run contact_sheet with explicit inputs; see the skill reference for its contract."""
    manifest = Path(manifest).resolve()
    data = json.loads(manifest.read_text())
    items = sorted(data["renders"], key=lambda r: r["frame"])
    if not items or columns < 1 or cell_width < 100:
        raise ValueError("Invalid sheet dimensions or empty renders")
    if Path(output_path).exists() or (archive_path and Path(archive_path).exists()):
        raise ValueError("Use new output paths")
    if archive_path and Path(output_path).resolve() == Path(archive_path).resolve():
        raise ValueError('Sheet and archive need distinct paths')
    files = []
    for r in items:
        image_path = (manifest.parent / r["file"]).resolve()
        if image_path.parent != manifest.parent:
            raise ValueError("Manifest image must be in its own directory")
        with Image.open(image_path) as im:
            im.load()
            if list(im.size) != data["config"]["resolution"]:
                raise ValueError("Image resolution differs from manifest")
        files.append(image_path)
    w = cell_width
    h = round(w * data["config"]["resolution"][1] / data["config"]["resolution"][0])
    font = ImageFont.truetype(font,22) if font else ImageFont.load_default(size=22)
    contact = write_sheet([dict(path=file,sha256=r['sha256'],
                               label=f"{r['seconds_from_start']:.2f} s  |  Frame {r['frame']}")
                           for r,file in zip(items,files)], output_path,
                          columns=min(columns,len(items)), image_size=(w,h), label_height=38,
                          gap=16, background='#0f131c', foreground='#e4eaf6', font=font,
                          label_offset=(6,5), resize='stretch', resample=Image.Resampling.LANCZOS)
    if archive_path:
        Path(archive_path).parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for file in files:
                z.write(file, file.name)
            z.write(manifest, manifest.name)
    return {
        "images": len(items),
        "cells": contact["cells"],
        "output": str(output_path),
        "zip": str(archive_path) if archive_path else None,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--zip")
    p.add_argument("--columns", type=int, default=3)
    p.add_argument("--cell-width", type=int, default=800)
    p.add_argument("--font")
    a = p.parse_args(argv)
    result = compose_sheet(a.manifest, a.output, a.zip, a.columns, a.cell_width, a.font)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
