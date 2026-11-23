"""Validate a clip timeline and emit media-edit / subtitle / mix specs."""
from __future__ import annotations

import json
from pathlib import Path

PRESETS = {
    'landscape': {'width': 1920, 'height': 1080, 'fps': '30'},
    'portrait': {'width': 1080, 'height': 1920, 'fps': '30'},
}


def validate_timeline(spec):
    if not isinstance(spec, dict) or spec.get('schemaVersion') != 1:
        raise ValueError('timeline schemaVersion must be 1')
    preset = spec.get('preset', 'portrait')
    if preset not in PRESETS:
        raise ValueError('preset must be landscape or portrait')
    clips = spec.get('clips')
    if not isinstance(clips, list) or not clips:
        raise ValueError('clips must be a nonempty list')
    for index, clip in enumerate(clips):
        if not isinstance(clip, dict):
            raise ValueError('clip must be an object')
        path = clip.get('path')
        start, end = clip.get('start'), clip.get('end')
        if not isinstance(path, str) or not path.strip() or '://' in path:
            raise ValueError('clip path must be local')
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            raise ValueError('clip start and end must be seconds')
        if end <= start:
            raise ValueError('clip end must be greater than start')
        if index == 0 and clip.get('transitionFrames', 0) not in (0, None):
            raise ValueError('first clip transitionFrames must be 0')
    music = spec.get('music')
    if music is not None:
        if not isinstance(music, str) or not music.strip() or '://' in music:
            raise ValueError('music must be a local file when provided')
    cues = spec.get('cues') or []
    if not isinstance(cues, list):
        raise ValueError('cues must be a list')
    return spec, PRESETS[preset]


def media_edit_spec(spec, preset, preview):
    width, height = preset['width'], preset['height']
    if preview:
        width, height = width // 2, height // 2
        if width % 2:
            width -= 1
        if height % 2:
            height -= 1
    clips = []
    for index, clip in enumerate(spec['clips']):
        item = {
            'path': clip['path'],
            'start': clip['start'],
            'end': clip['end'],
            'speed': clip.get('speed', 1),
        }
        if clip.get('crop'):
            item['crop'] = clip['crop']
        item['transitionFrames'] = 0 if index == 0 else int(clip.get('transitionFrames') or 0)
        clips.append(item)
    return {
        'schemaVersion': 1,
        'width': width,
        'height': height,
        'fps': spec.get('fps', preset['fps']),
        'clips': clips,
    }


def subtitle_spec(spec, preset):
    cues = spec.get('cues') or []
    if not cues:
        return None
    return {
        'schemaVersion': 1,
        'width': preset['width'],
        'height': preset['height'],
        'cues': cues,
    }


def mix_spec(video_path, spec, duration):
    tracks = []
    offset = 0.0
    if spec.get('keepSourceAudio'):
        for clip in spec['clips']:
            speed = float(clip.get('speed') or 1)
            held = (clip['end'] - clip['start']) / speed
            tracks.append({
                'path': clip['path'],
                'start': clip['start'],
                'end': clip['end'],
                'offset': offset,
            })
            offset += held
    if spec.get('music'):
        tracks.append({
            'path': spec['music'],
            'end': duration,
            'gainDb': spec.get('musicGainDb', -6),
            'fadeIn': spec.get('musicFadeIn', 0.2),
            'fadeOut': spec.get('musicFadeOut', 0.2),
        })
    if not tracks:
        return None
    result = {
        'schemaVersion': 1,
        'duration': duration,
        'tracks': tracks,
        'video': video_path,
    }
    if spec.get('subtitleFile'):
        result['subtitles'] = spec['subtitleFile']
    return result


def plan(spec, preview=False):
    spec, preset = validate_timeline(spec)
    edit = media_edit_spec(spec, preset, preview)
    return {
        'preset': preset,
        'preview': preview,
        'mediaEdit': edit,
        'subtitles': subtitle_spec(spec, preset),
        'needsAudio': bool(spec.get('music') or spec.get('keepSourceAudio')),
    }


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='Plan clip-edit specs')
    parser.add_argument('--timeline', required=True)
    parser.add_argument('--preview', action='store_true')
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    out = Path(args.output)
    if out.exists():
        raise SystemExit('output must be a new file')
    result = plan(json.loads(Path(args.timeline).read_text(encoding='utf-8')), args.preview)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
