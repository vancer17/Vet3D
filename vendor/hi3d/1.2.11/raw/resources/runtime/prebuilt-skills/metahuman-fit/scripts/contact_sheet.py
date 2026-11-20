"""Small labeled overview of actual same-camera renders; no synthetic imagery."""

from pathlib import Path
import json
from PIL import Image, ImageDraw, ImageFont
from image_sheet import compose_sheet


def make_sheet(
    root, title="MetaHuman registration review", tile=360, source_geometry=False
):
    root = Path(root)
    modes = [
        ("highpoly", "Source highpoly"),
        ("lowpoly", "Source geometry" if source_geometry else "Source lowpoly"),
        ("geometry", "Registered geometry"),
        ("detail", "Textured result"),
    ]
    angles = ["front", "side", "threequarter"]
    header = 70
    label = 30
    image = Image.new("RGB", (4 * tile, header + 3 * (tile + label)), (18, 24, 30))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=18)
    draw.text((16, 12), title, font=font, fill="white")
    grid, _ = compose_sheet(
        [dict(path=root / "renders" / f"{mode}_{angle}.png", label=angle)
         for angle in angles for mode, _ in modes],
        columns=4, image_size=(tile, tile), label_height=label,
        background=(18, 24, 30), foreground=(201, 211, 226), font=font,
        label_offset=(12, 4), resize="stretch", label_position="bottom",
    )
    image.paste(grid, (0, header))
    for col, (_, name) in enumerate(modes):
        draw.text((col * tile + 12, 42), name, font=font, fill=(201, 211, 226))
    image.save(root / "overview.jpg", quality=92)


def make_expression_sheet(root, title="MetaHuman registration review", tile=360):
    root = Path(root)
    poses = json.loads((root / "expression_report.json").read_text())["poses"]
    cols = min(3, len(poses))
    font = ImageFont.load_default(size=18)
    grid, _ = compose_sheet(
        [dict(path=root / "expressions" / f"pose_{i:02d}.png", label=pose["name"])
         for i, pose in enumerate(poses)],
        columns=cols, image_size=(tile, tile), label_height=30,
        background=(18, 24, 30), foreground=(201, 211, 226), font=font,
        label_offset=(12, 4), resize="stretch", label_position="bottom",
    )
    image = Image.new("RGB", (grid.width, 70 + grid.height), (18, 24, 30))
    image.paste(grid, (0, 70))
    draw = ImageDraw.Draw(image)
    draw.text((16, 12), title, font=font, fill="white")
    draw.text(
        (16, 40),
        "OpenRigLogic + CPU skinning | sampled poses",
        font=font,
        fill=(201, 211, 226),
    )
    image.save(root / "expressions.jpg", quality=92)
