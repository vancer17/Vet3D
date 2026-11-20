"""Measure integrated loudness and true peak of an existing WAV via ffmpeg ebur128."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from media_tools import find_ffmpeg


def measure(path, ffmpeg=None):
    binary = find_ffmpeg(ffmpeg)
    if not binary:
        raise RuntimeError('ffmpeg is required to measure loudness')
    command = [
        binary, '-hide_banner', '-i', str(path),
        '-filter_complex', 'ebur128=peak=true', '-f', 'null', '-',
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    text = (completed.stderr or '') + (completed.stdout or '')
    if completed.returncode != 0:
        raise RuntimeError('loudness measurement failed')
    integrated = None
    peak = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith('I:') and 'LUFS' in stripped:
            integrated = float(stripped.split()[1])
        if stripped.startswith('Peak:') and 'dBFS' in stripped:
            peak = float(stripped.split()[1])
    if integrated is None:
        raise RuntimeError('ffmpeg did not report integrated loudness')
    return {'integrated_lufs': integrated, 'true_peak_dbfs': peak, 'source': str(path)}


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='Measure WAV loudness')
    parser.add_argument('--input', required=True)
    parser.add_argument('--ffmpeg', default='')
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    out = Path(args.output)
    if out.exists():
        raise SystemExit('output must be a new file')
    report = measure(args.input, args.ffmpeg or None)
    out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
