#!/usr/bin/env python3
"""Read-only image/video checks against an explicit local delivery specification."""

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import time
from media_tools import find_ffmpeg, find_ffprobe


def positive_rate(value):
    """Parse a positive finite rate without interpreting bool as a number."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError("fps must be a positive number or rational string")
    try:
        rate = Fraction(str(value))
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("fps must be a positive number or rational string") from exc
    if rate <= 0:
        raise ValueError("fps must be positive")
    return rate


def validate_spec(spec):
    """Validate the manifest without file access; return the declared items."""
    if not isinstance(spec, dict) or set(spec) != {"items"}:
        raise ValueError("spec must contain only an items array")
    items = spec["items"]
    if not isinstance(items, list) or not items:
        raise ValueError("items must be a nonempty array")
    ids = set()
    common = {"id", "kind", "path", "width", "height"}
    for item in items:
        if not isinstance(item, dict) or item.get("kind") not in ("image", "video"):
            raise ValueError("each item must have kind image or video")
        required = common | ({"frames", "fps", "duration_seconds"}
                             if item["kind"] == "video" else set())
        if set(item) != required:
            raise ValueError("item fields do not match the declared media kind")
        if not isinstance(item["id"], str) or not item["id"].strip() or item["id"] in ids:
            raise ValueError("item ids must be nonempty unique strings")
        ids.add(item["id"])
        if (not isinstance(item["path"], str) or not item["path"].strip()
                or "://" in item["path"]):
            raise ValueError("path must name a local file")
        for key in ("width", "height", "frames"):
            if key in item and (type(item[key]) is not int or item[key] <= 0):
                raise ValueError(key + " must be a positive integer")
        if item["kind"] == "video":
            rate = positive_rate(item["fps"])
            duration = item["duration_seconds"]
            if (type(duration) not in (float, int) or not math.isfinite(duration)
                    or duration <= 0):
                raise ValueError("duration_seconds must be a positive finite number")
            if abs(item["frames"] / rate - duration) > 0.001:
                raise ValueError("frames, fps and duration_seconds are inconsistent")
    return items


def check_image(path, expected):
    """Verify structure and load all pixels of one still image; return observations."""
    from PIL import Image

    with Image.open(path) as im:
        im.verify()
    with Image.open(path) as im:
        im.load()
        actual = {"width": im.width, "height": im.height,
                  "format": im.format, "frames": getattr(im, "n_frames", 1)}
    errors = [key + " mismatch" for key in ("width", "height")
              if actual[key] != expected[key]]
    if actual["frames"] != 1:
        errors.append("image item must be a single still, not animated media")
    return actual, errors


def run_tool(argv, timeout):
    """Run one bounded local process; require success and no error-level output."""
    result = subprocess.run(argv, capture_output=True, text=True,
                            timeout=timeout, check=False)
    if result.returncode or result.stderr.strip():
        raise ValueError(Path(argv[0]).name + " failed: " + result.stderr.strip()[:1000])
    return result.stdout


def decode_video(path, ffmpeg, *, timeout=600, run=subprocess.run):
    """Fully decode first video stream; return measured frames and elapsed media time.

    Does not claim codec, dimensions or nominal fps; use check_video with ffprobe
    for those. A partial/error decode never produces a passing record.
    """
    result = run([str(ffmpeg), "-nostdin", "-v", "error", "-xerror",
                  "-protocol_whitelist", "file,pipe", "-i", str(path), "-map", "0:v:0",
                  "-progress", "pipe:1", "-nostats", "-f", "null", "-"],
                 capture_output=True, text=True, timeout=timeout, check=True)
    if result.stderr.strip():
        raise ValueError("Video decode failed: " + result.stderr.strip()[:1000])
    progress = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    if progress.get("progress") != "end":
        raise ValueError("Video decode did not finish")
    frames = int(progress.get("frame", "0"))
    seconds = int(progress.get("out_time_us", "0")) / 1000000
    if frames <= 0 or seconds <= 0:
        raise ValueError("Video decode produced no frames or duration")
    return {"frames": frames, "duration_seconds": seconds, "full_video_decode": "passed"}


def check_video(path, expected, ffmpeg, ffprobe, timeout):
    """Count/probe the first video stream and fully decode it without encoding."""
    raw = run_tool([ffprobe, "-v", "error", "-protocol_whitelist", "file,pipe",
                    "-count_frames", "-select_streams", "v:0", "-show_entries",
                    "stream=codec_name,width,height,r_frame_rate,avg_frame_rate,"
                    "nb_read_frames,duration", "-of", "json", str(path)], timeout)
    streams = json.loads(raw).get("streams", [])
    if len(streams) != 1:
        raise ValueError("no readable first video stream")
    stream = streams[0]
    actual = {"codec": stream.get("codec_name"), "width": int(stream["width"]),
              "height": int(stream["height"]), "frames": int(stream["nb_read_frames"]),
              "fps": stream["r_frame_rate"], "average_fps": stream["avg_frame_rate"],
              "duration_seconds": float(stream["duration"])}
    errors = [key + " mismatch" for key in ("width", "height", "frames")
              if actual[key] != expected[key]]
    rate = positive_rate(expected["fps"])
    for key in ("fps", "average_fps"):
        if abs(positive_rate(actual[key]) - rate) > Fraction(1, 100000):
            errors.append(key + " mismatch")
    if (not math.isfinite(actual["duration_seconds"])
            or abs(actual["duration_seconds"] - expected["duration_seconds"]) > 0.001):
        errors.append("duration_seconds mismatch")
    decoded = decode_video(path, ffmpeg, timeout=timeout)
    if decoded["frames"] != actual["frames"]:
        errors.append("decoded frames mismatch")
    actual["full_video_decode"] = decoded["full_video_decode"]
    return actual, errors


def audit(spec, base, timeout=600, ffmpeg=None, ffprobe=None):
    """Audit files relative to base, preserving per-item failures in the report."""
    items = validate_spec(spec)
    records = []
    for item in items:
        start = time.monotonic()
        record = {"id": item["id"], "expected": dict(item),
                  "started_at": datetime.now(timezone.utc).isoformat()}
        try:
            path = (Path(base) / item["path"]).resolve()
            if not path.is_file():
                raise ValueError("missing media file: " + str(path))
            if item["kind"] == "image":
                actual, errors = check_image(path, item)
            else:
                ffmpeg, ffprobe = find_ffmpeg(ffmpeg), find_ffprobe(ffprobe)
                if not ffmpeg or not ffprobe:
                    raise ValueError("video checks require ffmpeg and ffprobe")
                actual, errors = check_video(path, item, ffmpeg, ffprobe, timeout)
            record.update(actual=actual, errors=errors)
        except (OSError, ValueError, KeyError, ImportError, subprocess.SubprocessError) as exc:
            record["errors"] = [str(exc)]
        record.update(status="failed" if record["errors"] else "passed",
                      ended_at=datetime.now(timezone.utc).isoformat(),
                      seconds=time.monotonic() - start)
        records.append(record)
    return {"status": "passed" if all(r["status"] == "passed" for r in records) else "failed",
            "items": records,
            "scope": "Media dimensions and decoding only; video checks the first video stream. "
                     "Does not certify visual quality, frame provenance, camera motion or audio."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=600,
                        help="Seconds per ffprobe/ffmpeg process (default: 600)")
    parser.add_argument("--ffmpeg")
    parser.add_argument("--ffprobe")
    args = parser.parse_args(argv)
    try:
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        spec_path = args.spec.resolve()
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        items = validate_spec(spec)
        input_paths = [spec_path] + [(spec_path.parent / i["path"]).resolve() for i in items]
        if args.out.resolve() in input_paths:
            raise ValueError("report must not overwrite the specification or media")
        report = audit(spec, spec_path.parent, args.timeout, args.ffmpeg, args.ffprobe)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
    except (OSError, ValueError) as exc:
        print("Media audit failed: " + str(exc), file=sys.stderr)
        return 1
    print(json.dumps({"status": report["status"], "report": str(args.out.resolve())}))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
