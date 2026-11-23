"""Portable separate DIY branch; original run.py remains the purchased-hardware entry."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import argparse, sys, subprocess, json, hashlib, shutil
from pathlib import Path
from PIL import Image
from stage_cli import cli_arguments, StageFinished, _finish_stage
from path_safety import validate_write_roots

def sha(p):
    """Independently callable sha operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def run(cmd, log, *, calls, work):
    """Independently callable run operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    with (work / log).open('w') as stream:
        r = subprocess.run([str(x) for x in cmd], stdout=stream, stderr=subprocess.STDOUT)
    calls.append({'command': [str(x) for x in cmd], 'returncode': r.returncode, 'log': str(work / log)})
    assert r.returncode == 0, f'{log}: exit{r.returncode}'

def blender(script, args, log, *, a, calls, scripts, work):
    """Independently callable blender operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    run([a.blender, '-b', '-t', '2', '--python-exit-code', '1', '--python', scripts / script, '--', *args], log, calls=calls, work=work)

def build_parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-case', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--blender', type=Path, required=True)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--stage', choices=['all', 'verify', 'media'], default='all')
    p.add_argument('--skip-stills', action='store_true')
    video = p.add_mutually_exclusive_group()
    video.add_argument('--render-video', dest='no_video', action='store_false', help='Render/encode video only when explicitly requested')
    video.add_argument('--no-video', dest='no_video', action='store_true', help='Keep video disabled (the default)')
    p.set_defaults(no_video=True)
    return p

def execute(a):
    """Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate."""
    scripts = Path(__file__).resolve().parent
    out = a.output.resolve()
    work = a.work.resolve()
    src = a.source_case.resolve()
    validate_write_roots({'output': out, 'work': work}, package_root=scripts.parent, protected_inputs=[src])
    out.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    config = a.config.resolve()
    calls = []
    required = ['construction.json', 'scene.blend', 'print/character-with-blind-foot-sockets.stl', 'print/skateboard-with-integrated-pegs-and-trucks.stl']
    for name in required:
        assert (src / name).is_file(), f'Missing replay input: {name}'
    if a.stage == 'all':
        run([sys.executable, scripts / 'build_diy_solids.py', '--source-case', src, '--output', out, '--config', config], 'solids.log', calls=calls, work=work)
        blender('build_diy_scene.py', ['--source-scene', src / 'scene.blend', '--output', out, '--work', work] + (['--skip-stills'] if a.skip_stills else []), 'scene.log', a=a, calls=calls, scripts=scripts, work=work)
    if a.stage in ['all', 'verify']:
        run([sys.executable, scripts / 'check_diy_interface.py', '--output', out], 'interface-check.log', calls=calls, work=work)
        run([sys.executable, scripts / 'validate_stl.py', out / 'print', out / 'coupons', '--json', out / 'stl-validation.json'], 'stl.log', calls=calls, work=work)
        blender('inspect_diy_exports.py', ['--output', out, '--work', work], 'fresh-import.log', a=a, calls=calls, scripts=scripts, work=work)
        run([sys.executable, scripts / 'check_diy_motion.py', '--output', out, '--work', work], 'motion-check.log', calls=calls, work=work)
    if a.stage in ['all', 'media'] and (not a.no_video):
        scene = out / 'assembly.blend'
        digest = sha(scene)
        frames = work / 'video' / digest
        frames.mkdir(parents=True, exist_ok=True)
        cfg = json.loads((out / 'config.json').read_text())
        count = cfg['video_frames']
        fps = cfg['fps']
        for start in range(1, count + 1, 24):
            end = min(count, start + 23)
            ok = True
            for f in range(start, end + 1):
                try:
                    with Image.open(frames / f'{f:04d}.png') as im:
                        im.verify()
                except Exception:
                    ok = False
                    break
            if not ok:
                blender('render_diy_frames.py', ['--scene', scene, '--frames', frames, '--start', start, '--end', end], f'render-{start:04d}.log', a=a, calls=calls, scripts=scripts, work=work)
            assert sha(scene) == digest, 'Native scene changed during render; preserve old frame directory and restart from current hash.'
        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            ffmpeg = shutil.which('ffmpeg')
        assert ffmpeg, 'ffmpeg or imageio-ffmpeg required'
        run([ffmpeg, '-y', '-framerate', fps, '-i', frames / '%04d.png', '-frames:v', count, '-c:v', 'libx264', '-crf', '19', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out / 'assembly.mp4'], 'encode.log', calls=calls, work=work)
        run([ffmpeg, '-v', 'error', '-i', out / 'assembly.mp4', '-f', 'null', '-'], 'decode.log', calls=calls, work=work)
        sheet = Image.new('RGB', (4 * 432, 3 * 384), (230, 230, 230))
        selected = [1, 14, 24, 36, 48, 60, 78, 90, 101, 112, 128, 144]
        for k, f in enumerate(selected):
            with Image.open(frames / f'{f:04d}.png') as im:
                sheet.paste(im.convert('RGB').resize((432, 384)), (k % 4 * 432, k // 4 * 384))
        sheet.save(out / 'video-contact-sheet.jpg', quality=93)
        (out / 'video-validation.json').write_text(json.dumps({'scene_sha256': digest, 'mp4_sha256': sha(out / 'assembly.mp4'), 'frames': count, 'fps': fps, 'duration_seconds': count / fps, 'decode_exit': 0, 'frames_directory': str(frames), 'contact_frames': selected, 'visual_review': 'Open actual contact sheet and first/middle/last frames before final acceptance.'}, indent=2))
    for old in out.glob('*.blend1'):
        target = work / 'old-native-backups'
        target.mkdir(exist_ok=True)
        shutil.move(old, target / old.name)
    (out / 'replay-inputs.json').write_text(json.dumps({'source_case_layout': {name: {'sha256': sha(src / name), 'bytes': (src / name).stat().st_size} for name in required}, 'historical_absolute_path_required': False, 'retrieval': 'Provide a compatible standard cart package using the four-file layout in references/runtime.md. Inputs must meet its dimensional and named-object contract. Input originals are not changed.'}, indent=2))
    (work / f'run-{a.stage}.json').write_text(json.dumps({'stage': a.stage, 'skip_stills': a.skip_stills, 'no_video': a.no_video, 'calls': calls, 'inputs': str(src), 'output': str(out), 'actual_files': [str(x.relative_to(out)) for x in out.rglob('*') if x.is_file()]}, indent=2))
    print('DIY RUN COMPLETE', a.stage, out)

def main(argv=None):
    try:
        return execute(build_parser().parse_args(cli_arguments(argv)))
    except StageFinished as done:
        return done
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
