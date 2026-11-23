"""Bounded native-scene frame rendering with source-hash checkpoints and fresh processes."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import argparse, json, subprocess, hashlib, time
from pathlib import Path
from PIL import Image
from stage_cli import cli_arguments, StageFinished, _finish_stage

def build_parser():
    p = argparse.ArgumentParser()
    p.add_argument('--case', type=Path, required=True)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--blender', required=True)
    p.add_argument('--spec', type=Path, required=True, help='JSON list of {tag, frames} for case/<tag>.blend')
    p.add_argument('--chunk-size', type=int, default=16)
    p.add_argument('--adopt-existing', action='store_true')
    return p

def read_spec(path):
    """Read explicit scene tags/frame counts, rejecting ambiguous or invalid plans."""
    spec = json.loads(Path(path).read_text())
    if not isinstance(spec, list) or not spec:
        raise ValueError('Nonempty render spec required')
    seen = set()
    for item in spec:
        tag, count = item['tag'], item['frames']
        if not isinstance(tag, str) or not tag or not all(c.isalnum() or c in '-_' for c in tag):
            raise ValueError('Invalid render tag')
        if tag in seen or not isinstance(count, int) or isinstance(count, bool) or count < 1:
            raise ValueError('Unique tags and positive integer frame counts required')
        seen.add(tag)
    return spec


def render_sources(scripts, blender=None):
    """Fingerprint executable rendering sources, independently of business geometry."""
    result = {name: hashlib.sha256((Path(scripts)/name).read_bytes()).hexdigest()
            for name in ('render_video_chunks.py', 'render_frame_chunk.py', 'render_scene.py', 'render_engine.py', 'stage_cli.py')}
    if blender is not None:
        result['blender_executable'] = hashlib.sha256(Path(blender).read_bytes()).hexdigest()
    return result


def matching_checkpoint(record, source_hash, frame_count, sources):
    """Reuse frames only for the same source and the complete rendering profile."""
    return (isinstance(record, dict) and record.get('source_sha256') == source_hash
            and record.get('render_sources') == sources
            and record.get('frame_count') == frame_count
            and record.get('resolution') == [864, 768] and record.get('fps') == 24
            and record.get('engine') == 'BLENDER_EEVEE')


def execute(a):
    """Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate."""
    s = Path(__file__).resolve().parent
    a.case = a.case.resolve()
    a.work = a.work.resolve()
    a.work.mkdir(parents=True, exist_ok=True)
    spec = read_spec(a.spec)
    sources = render_sources(s, a.blender)
    if a.chunk_size < 1:
        raise ValueError('Positive chunk size required')
    for item in spec:
        tag, count = item['tag'], item['frames']
        scene = a.case / (tag + '.blend')
        sha = hashlib.sha256(scene.read_bytes()).hexdigest()
        folder = a.work / (tag + '-frames')
        stamp = a.work / (tag + '-render-checkpoint.json')
        known = json.loads(stamp.read_text()) if stamp.exists() else None
        if known and not matching_checkpoint(known, sha, count, sources):
            if folder.exists():
                folder.rename(a.work / (tag + '-frames-old-' + str(time.time_ns())))
            known = None
        if folder.exists() and any(folder.glob('*.png')) and (not known) and (not a.adopt_existing):
            raise RuntimeError('Existing frames have no matching source checkpoint; use newwork or explicitly review/adopt them')
        folder.mkdir(parents=True, exist_ok=True)
        record = {'render_sources': sources, 'source': scene.name, 'source_sha256': sha, 'engine': 'BLENDER_EEVEE', 'resolution': [864, 768], 'fps': 24, 'frame_count': count, 'adopted_existing_after_explicit_review': bool(not known and a.adopt_existing), 'chunks': known.get('chunks', []) if known else []}
        stamp.write_text(json.dumps(record, indent=2))

        def valid(i):
            q = folder / f'{i:04d}.png'
            if not q.exists():
                return False
            try:
                with Image.open(q) as im:
                    assert im.size == (864, 768)
                    im.verify()
                return True
            except Exception:
                return False
        for start in range(1, count + 1, a.chunk_size):
            end = min(count, start + a.chunk_size - 1)
            missing = [i for i in range(start, end + 1) if not valid(i)]
            if not missing:
                continue
            begin = missing[0]
            finish = missing[-1]
            print('RENDER', tag, begin, finish, flush=True)
            for attempt in range(2):
                try:
                    subprocess.run([a.blender, '-b', '-t', '2', '--python-exit-code', '1', '--python', str(s / 'render_frame_chunk.py'), '--', str(scene), str(folder), str(begin), str(finish)], check=True, timeout=240)
                    break
                except subprocess.TimeoutExpired:
                    if attempt:
                        raise
                    print('Bounded retry', tag, begin, finish, flush=True)
            assert all((valid(i) for i in range(begin, finish + 1)))
            record['chunks'].append({'start': begin, 'end': finish, 'completed': True})
            stamp.write_text(json.dumps(record, indent=2))
        assert all((valid(i) for i in range(1, count + 1)))
        record['complete'] = True
        record['frames'] = [{'frame': i, 'sha256': hashlib.sha256((folder / f'{i:04d}.png').read_bytes()).hexdigest()} for i in range(1, count + 1)]
        stamp.write_text(json.dumps(record, indent=2))
        print('COMPLETE', tag, count, flush=True)

def main(argv=None):
    try:
        return execute(build_parser().parse_args(cli_arguments(argv)))
    except StageFinished as done:
        return done
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
