"""Explicit contiguous PNG/JPEG encoding; media-check owns decode verification."""
from pathlib import Path
import re
import subprocess
from check_media import positive_rate, decode_video, check_video


def sequence_names(names, *, start=0, pattern="%04d.png"):
    """Validate a numeric printf PNG/JPEG pattern and exact contiguous basenames."""
    match = re.fullmatch(r"%0([1-9][0-9]?)d\.(?:png|jpg|jpeg)", pattern)
    if not match or (start is not None and (type(start) is not int or start < 0)):
        raise ValueError("Require %0Nd.png/.jpg/.jpeg pattern and nonnegative integer start")
    names = sorted(names)
    if not names:
        raise ValueError("Require nonempty image sequence")
    if start is None:
        try:
            start = min(int(Path(name).stem) for name in names)
        except ValueError as exc:
            raise ValueError("Image sequence names must be numeric") from exc
    if sorted(pattern % i for i in range(start, start + len(names))) != names:
        raise ValueError("Require contiguous image names with no extra images")
    return names


def encoder_command(ffmpeg, folder, fps, output, *, start=0, pattern="%04d.png",
                    crf=19, pad_even=False, overwrite=False, frames=None):
    """Build argv only; no shell execution or implicit overwrite."""
    if not ffmpeg:
        raise ValueError("ffmpeg executable required")
    positive_rate(fps)
    if (type(start) is not int or start < 0 or not isinstance(pattern, str)
            or not re.fullmatch(r"%0([1-9][0-9]?)d\.(?:png|jpg|jpeg)", pattern)):
        raise ValueError("Require %0Nd.png/.jpg/.jpeg pattern and nonnegative integer start")
    if type(crf) is not int or not 0 <= crf <= 51:
        raise ValueError("CRF must be an integer in [0, 51]")
    if frames is not None and (type(frames) is not int or frames <= 0):
        raise ValueError("frames must be a positive integer")
    args = [str(ffmpeg), '-nostdin', '-v', 'error', '-y' if overwrite else '-n',
            '-framerate', str(fps), '-start_number', str(start),
            '-i', str(Path(folder) / pattern)]
    if frames is not None:
        args += ['-frames:v', str(frames)]
    args += ['-c:v', 'libx264', '-crf', str(crf), '-pix_fmt', 'yuv420p']
    if pad_even:
        args += ['-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2']
    return args + ['-movflags', '+faststart', str(output)]


def encode_sequence(ffmpeg, folder, fps, output, *, start=0, pattern="%04d.png",
                    crf=19, pad_even=False, overwrite=False, ffprobe=None,
                    timeout=600, run=subprocess.run):
    """Encode then verify measured frame count/duration; optional full ffprobe audit.

    On failure a partial output can remain. Never write a success sidecar here;
    the caller chooses its report name after this function returns successfully.
    """
    from PIL import Image
    folder, output = Path(folder).resolve(), Path(output).resolve()
    names = sequence_names((p.name for p in folder.iterdir() if p.is_file() and p.suffix.lower() in {'.png','.jpg','.jpeg'}), start=start, pattern=pattern)
    if start is None:
        start = min(int(Path(name).stem) for name in names)
    rate = positive_rate(fps)
    sizes = set()
    for name in names:
        with Image.open(folder / name) as image:
            if image.format != ('PNG' if pattern.endswith('.png') else 'JPEG'):
                raise ValueError('Frame content does not match the declared image format')
            image.verify()
            sizes.add(image.size)
        with Image.open(folder / name) as image:
            image.load()
    if len(sizes) != 1:
        raise ValueError("All sequence images must have the same dimensions")
    width, height = sizes.pop()
    if not pad_even and (width % 2 or height % 2):
        raise ValueError("yuv420p requires even dimensions or explicit pad_even")
    if output in [(folder / name).resolve() for name in names]:
        raise ValueError("Video must not overwrite an input frame")
    if output.exists() and not overwrite:
        raise FileExistsError("Use a fresh video output or explicit overwrite")
    command = encoder_command(ffmpeg, folder, fps, output, start=start, pattern=pattern,
                              crf=crf, pad_even=pad_even, overwrite=overwrite, frames=len(names))
    output.parent.mkdir(parents=True, exist_ok=True)
    run(command, check=True, timeout=timeout)
    expected = dict(width=width + width % 2 if pad_even else width,
                    height=height + height % 2 if pad_even else height,
                    frames=len(names), fps=str(rate), duration_seconds=float(len(names)/rate))
    if ffprobe:
        actual, errors = check_video(output, expected, ffmpeg, ffprobe, timeout)
        if errors:
            raise ValueError('; '.join(errors))
        scope = 'dimensions, rates, frames, duration and full decode'
    else:
        actual = decode_video(output, ffmpeg, timeout=timeout, run=run)
        if actual['frames'] != len(names) or abs(actual['duration_seconds'] - expected['duration_seconds']) > .001:
            raise ValueError('Decoded frame count or duration mismatch')
        scope = 'frame count, duration and full decode; dimensions/nominal fps not independently probed'
    return dict(expected=expected, actual=actual, check_scope=scope,
                start=start, pattern=pattern, crf=crf, pad_even=pad_even, overwrite=overwrite)


def main(argv=None):
    import argparse
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ffmpeg', required=True)
    parser.add_argument('--frames', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--fps', required=True)
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--pattern', default='%04d.png')
    parser.add_argument('--crf', type=int, default=19)
    parser.add_argument('--pad-even', action='store_true')
    parser.add_argument('--overwrite', action='store_true')
    parser.add_argument('--ffprobe')
    parser.add_argument('--timeout', type=float, default=600)
    args = vars(parser.parse_args(argv))
    args['folder'] = args.pop('frames')
    result = encode_sequence(**args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == '__main__':
    main()
