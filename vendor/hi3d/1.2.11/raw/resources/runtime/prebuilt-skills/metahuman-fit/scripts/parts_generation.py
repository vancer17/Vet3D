"""Validate split head/hair references and emit Runtime hi3d_api handoffs."""

import argparse
import json
from pathlib import Path


SETTINGS = {
    "model": "hi3dv3.0",
    "resolution": "2048quality",
    "request_type": 1,
    "face": 5000000,
    "format": 2,
    "shading": 0.5,
}


def part_config(config, part):
    data = config["parts"][part]
    views = data.get("gray_views", {})
    if not views.get("front"):
        raise ValueError("Gray front is required")
    if set(views) - {"front", "right", "back", "left"}:
        raise ValueError("Unknown gray view direction")
    if part == "hair" and data.get("occluded_hair_completed") is not True:
        raise ValueError("Review completed hair behind the removed head and neck before generation")
    for path in views.values():
        if not Path(path).is_file():
            raise ValueError("Missing gray reference")
    names = [name for name in ("front", "back", "left", "right") if name in views]
    root = Path(config["output"]).resolve() / part
    return {
        "action": "generate_3d",
        "kind": "model",
        "images": [str(Path(views[name]).resolve()) for name in names],
        "views": names,
        "settings": dict(SETTINGS),
        "jobPath": str(root / "hi3d_job.json"),
        "outputDir": str(root / "generation"),
    }


def run(config):
    parts = config["parts"]
    if "bald" not in parts or set(parts) - {"bald", "hair"}:
        raise ValueError("parts must contain bald and optionally hair")
    return {
        part: {
            "runtimeTool": "hi3d_api",
            "dryRunFirst": True,
            "arguments": part_config(config, part),
        }
        for part in parts
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    print(json.dumps(run(json.loads(args.config.read_text(encoding="utf-8"))), indent=2))
