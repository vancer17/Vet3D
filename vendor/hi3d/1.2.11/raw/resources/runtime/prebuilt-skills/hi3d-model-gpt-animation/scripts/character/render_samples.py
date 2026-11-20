"""Render explicitly requested time samples, with a resumable manifest. Does not save the blend."""

import argparse
from rigging.io_utils import file_digest
import json
import math
import time
from pathlib import Path
from render_engine import set_samples
import bpy
from rigging.blend_common import open_input, write_json


def sample_frames(start, end, fps, interval):
    if end < start or fps <= 0 or interval <= 0 or not math.isfinite(interval):
        raise ValueError("Invalid frame range, fps, or interval")
    step = fps * interval
    if step < 1:
        raise ValueError("Requested interval is below one scene frame")
    count = math.floor((end - start) / step + 1e-9) + 1
    return sorted(set(round(start + i * step) for i in range(count)))


def render_samples(
    input_path,
    out_dir,
    start=None,
    end=None,
    interval_seconds=1,
    camera=None,
    width=None,
    height=None,
    samples=None,
    resume=False,
):
    """Run render_samples with explicit inputs; see the skill reference for its contract."""
    src = open_input(input_path)
    s = bpy.context.scene
    out = Path(out_dir).expanduser().resolve()
    manifest = out / "render_manifest.json"
    if camera:
        camera = bpy.data.objects.get(camera)
        if not camera or camera.type != "CAMERA":
            raise ValueError("Requested camera does not exist")
        s.camera = camera
    if not s.camera:
        raise ValueError("Scene has no active camera")
    if (width is None) != (height is None):
        raise ValueError("Specify both width and height")
    if width is not None:
        if min(width, height) < 1:
            raise ValueError("Resolution must be positive")
        s.render.resolution_x, s.render.resolution_y = width, height
        s.render.resolution_percentage = 100
    if samples is not None:
        if samples < 1:
            raise ValueError("Samples must be positive")
        if s.render.engine not in {"BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "CYCLES"}:
            raise ValueError("Sample override supports EEVEE or Cycles")
        set_samples(s, samples)
    fps = s.render.fps / s.render.fps_base
    start = s.frame_start if start is None else start
    end = s.frame_end if end is None else end
    frames = sample_frames(start, end, fps, interval_seconds)
    if hasattr(s.render, "use_motion_blur"):
        s.render.use_motion_blur = False
    s.render.image_settings.file_format = "PNG"
    s.render.image_settings.color_mode = "RGB"
    s.render.image_settings.color_depth = "8"
    effective_samples = (
        s.eevee.taa_render_samples
        if s.render.engine in {"BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"} and hasattr(s, "eevee") and hasattr(s.eevee, "taa_render_samples")
        else (s.cycles.samples if s.render.engine == "CYCLES" else None)
    )
    config = {
        "source_sha256": file_digest(src),
        "render_sources": {"render_samples": file_digest(Path(__file__)), "render_engine": file_digest(Path(__file__).resolve().parents[1] / "render_engine.py")},
        "engine": s.render.engine,
        "camera": s.camera.name,
        "fps": fps,
        "frames": frames,
        "samples": effective_samples,
        "resolution": [
            int(s.render.resolution_x * s.render.resolution_percentage / 100),
            int(s.render.resolution_y * s.render.resolution_percentage / 100),
        ],
        "motion_blur": False,
    }
    results = []
    if out.exists() and any(out.iterdir()):
        if not resume or not manifest.exists():
            raise ValueError(
                "Use an empty directory, or --resume with its matching manifest"
            )
        prior = json.loads(manifest.read_text())
        if prior["config"] != config:
            raise ValueError(
                "Resume source or settings differ; use a new output directory"
            )
        results = prior["renders"]
    out.mkdir(parents=True, exist_ok=True)
    completed = {r["frame"]: r for r in results}
    for frame in frames:
        target = out / f"frame_{frame:06d}.png"
        if frame in completed:
            if (
                not target.is_file()
                or file_digest(target) != completed[frame]["sha256"]
            ):
                raise ValueError(
                    "Completed image is missing or modified: " + target.name
                )
            continue
        if target.exists():
            raise ValueError(
                "Untracked partial output exists; inspect it before retrying: "
                + target.name
            )
        s.frame_set(frame)
        s.render.filepath = str(target)
        started = time.monotonic()
        bpy.ops.render.render(write_still=True)
        results.append(
            {
                "frame": frame,
                "seconds_from_start": (frame - start) / fps,
                "file": target.name,
                "sha256": file_digest(target),
                "elapsed_seconds": round(time.monotonic() - started, 2),
            }
        )
        write_json(manifest, {"config": config, "renders": results})
        print("FRAME_COMPLETE", frame, flush=True)
    return {"config": config, "renders": results}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--start", type=int)
    p.add_argument("--end", type=int)
    p.add_argument("--interval-seconds", type=float, default=1)
    p.add_argument("--camera")
    p.add_argument("--width", type=int)
    p.add_argument("--height", type=int)
    p.add_argument("--samples", type=int)
    p.add_argument("--resume", action="store_true")
    a = p.parse_args(argv)
    result = render_samples(
        a.input,
        a.out_dir,
        a.start,
        a.end,
        a.interval_seconds,
        a.camera,
        a.width,
        a.height,
        a.samples,
        a.resume,
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
