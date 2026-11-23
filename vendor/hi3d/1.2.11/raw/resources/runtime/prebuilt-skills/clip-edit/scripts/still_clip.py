"""Turn a still image into a constant-frame clip for media-edit."""
from __future__ import annotations

import subprocess
from pathlib import Path
from media_tools import find_ffmpeg


def still_clip(image, destination, duration, fps, width, height, ffmpeg=None):
    binary = find_ffmpeg(ffmpeg)
    if not binary:
        raise RuntimeError('ffmpeg is required to hold a still image')
    if duration <= 0:
        raise ValueError('duration must be positive')
    out = Path(destination)
    if out.exists():
        raise ValueError('still clip output must be a new file')
    command = [
        binary, '-hide_banner', '-y', '-loop', '1', '-i', str(image),
        '-t', str(duration), '-r', str(fps),
        '-vf', 'scale={}:{}:force_original_aspect_ratio=decrease,pad={}:{}:(ow-iw)/2:(oh-ih)/2'.format(
            width, height, width, height),
        '-pix_fmt', 'yuv420p', str(out),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0 or not out.is_file():
        raise RuntimeError('still image clip failed')
    return out


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='Encode a still image as a video clip')
    parser.add_argument('--image', required=True)
    parser.add_argument('--duration', type=float, required=True)
    parser.add_argument('--fps', default='30')
    parser.add_argument('--width', type=int, required=True)
    parser.add_argument('--height', type=int, required=True)
    parser.add_argument('--ffmpeg', default='')
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    still_clip(args.image, args.output, args.duration, args.fps, args.width, args.height, args.ffmpeg or None)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
