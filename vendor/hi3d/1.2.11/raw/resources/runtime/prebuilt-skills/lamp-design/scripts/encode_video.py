"""Encode a contiguous 0000.png sequence and decode-check the resulting MP4."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess


from media_tools import find_ffmpeg
from encode_sequence import sequence_names
from encode_sequence import encoder_command as _encoder_command, encode_sequence


def encoder_command(ffmpeg, folder, fps, output):
    if type(fps) is not int or fps <= 0:
        raise ValueError('Require positive integer fps')
    return _encoder_command(ffmpeg, folder, fps, output, crf=18, pad_even=True)


def encode(ffmpeg, folder, fps, output, run=subprocess.run):
    """I/O adapter: validate names, encode, decode, then save a sidecar report.

    Failed encoding may leave a partial MP4; use a fresh output for a retry.
    """
    folder, output = Path(folder).resolve(), Path(output).resolve()
    names = sequence_names(p.name for p in folder.glob('*.png'))
    command = encoder_command(ffmpeg, folder, fps, output)
    if output.exists() or output.with_suffix('.json').exists():
        raise FileExistsError('Use a fresh output video and sidecar path')
    output.parent.mkdir(parents=True, exist_ok=True)
    checked = encode_sequence(ffmpeg, folder, fps, output, crf=18, pad_even=True, run=run)
    if output.stat().st_size <= 1024:
        raise ValueError('Encoded video is unexpectedly small')
    info = {'video':output.name,'frames':len(names),'fps':fps,'seconds':len(names)/fps,
            'decode_check':'pass','bytes':output.stat().st_size, 'technical_check':checked}
    output.with_suffix('.json').write_text(json.dumps(info, indent=2)+'\n')
    return info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ffmpeg', default=find_ffmpeg())
    parser.add_argument('--frames-dir', required=True)
    parser.add_argument('--fps', type=int, default=24)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        info = encode(args.ffmpeg, args.frames_dir, args.fps, args.output)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    print(json.dumps(info))


if __name__ == '__main__':
    main()
