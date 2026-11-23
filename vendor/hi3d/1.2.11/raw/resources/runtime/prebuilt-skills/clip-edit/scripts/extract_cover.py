"""Extract a cover PNG from an already exported MP4 using explicit ffmpeg."""
from __future__ import annotations

import subprocess
from pathlib import Path
from media_tools import find_ffmpeg


def extract(video, destination, seconds=0, ffmpeg=None):
    binary = find_ffmpeg(ffmpeg)
    if not binary:
        raise RuntimeError('ffmpeg is required to extract a cover')
    out = Path(destination)
    if out.exists():
        raise ValueError('cover output must be a new file')
    command = [
        binary, '-hide_banner', '-y', '-ss', str(seconds),
        '-i', str(video), '-frames:v', '1', str(out),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0 or not out.is_file() or out.stat().st_size == 0:
        raise RuntimeError('cover extract failed')
    return out


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='Extract cover PNG from MP4')
    parser.add_argument('--video', required=True)
    parser.add_argument('--seconds', type=float, default=0)
    parser.add_argument('--ffmpeg', default='')
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    extract(args.video, args.output, args.seconds, args.ffmpeg or None)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
