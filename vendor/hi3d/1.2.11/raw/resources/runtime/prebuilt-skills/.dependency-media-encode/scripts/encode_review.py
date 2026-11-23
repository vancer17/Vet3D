"""encode review local stage adapter."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

from pathlib import Path
import argparse, json, hashlib
from encode_sequence import encode_sequence
import imageio_ffmpeg
from PIL import Image
from image_sheet import write_sheet
from stage_cli import cli_arguments, StageFinished, _finish_stage

def build_parser():
    p = argparse.ArgumentParser()
    p.add_argument('case', type=Path)
    p.add_argument('frames', type=Path)
    p.add_argument('work', type=Path)
    return p

def execute(a):
    """Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate."""
    a.work.mkdir(parents=True, exist_ok=True)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    for folder in a.frames.glob('*-frames'):
        tag = folder.name[:-7]
        count = len(list(folder.glob('*.png')))
        target = a.case / (tag + '.mp4')
        checked = encode_sequence(ff, folder, 24, target, start=None, crf=19, overwrite=True)
        stream = imageio_ffmpeg.read_frames(str(target), pix_fmt='rgb24')
        meta = next(stream)
        snaps = []
        for i, buf in enumerate(stream):
            if i % 12 == 0 or i == count - 1:
                snaps.append((i + 1, Image.frombytes('RGB', meta['size'], buf)))
        decoded = i + 1
        assert count == decoded
        contact = write_sheet([dict(image=im,label=f'{num}/{decoded}') for num,im in snaps],
                              a.work / (tag+'-decoded-contact.png'), columns=4,
                              image_size=(400,276), label_height=24,
                              background=(232,230,220), foreground='#222222',
                              resize='contain', resample=Image.Resampling.BICUBIC, overwrite=True)
        r = {'file': target.name, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'decoded_frames': decoded, 'fps': meta['fps'], 'seconds': decoded / meta['fps'], 'contact_sheet': tag + '-decoded-contact.png', 'technical_check': checked, 'contact_cells': contact['cells']}
        target.with_suffix('.video.json').write_text(json.dumps(r, indent=2))
        print(r, flush=True)

def main(argv=None):
    try:
        return execute(build_parser().parse_args(cli_arguments(argv)))
    except StageFinished as done:
        return done
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
