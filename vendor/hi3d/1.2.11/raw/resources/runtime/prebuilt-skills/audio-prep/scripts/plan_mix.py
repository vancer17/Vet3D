"""Build an audio-mix spec from trim/fade/loudness preferences. No mixing here."""
from __future__ import annotations

import json
from pathlib import Path


def validate_brief(brief):
    if not isinstance(brief, dict) or brief.get('schemaVersion') != 1:
        raise ValueError('brief schemaVersion must be 1')
    path = brief.get('path')
    if not isinstance(path, str) or not path.strip() or '://' in path:
        raise ValueError('path must be a local audio file')
    duration = brief.get('duration')
    if not isinstance(duration, (int, float)) or duration <= 0:
        raise ValueError('duration must be a positive number of seconds from a real probe')
    start = float(brief.get('trimStart') or 0)
    end = float(brief.get('trimEnd') if brief.get('trimEnd') is not None else duration)
    if start < 0 or end > duration or end <= start:
        raise ValueError('trim range must stay inside the probed duration')
    mid = brief.get('trimInteriorPauses')
    if mid:
        raise ValueError('interior pause trimming is not offered')
    loudness = brief.get('loudness', -16)
    if not isinstance(loudness, (int, float)) or loudness < -70 or loudness > -5:
        raise ValueError('loudness must be between -70 and -5 LUFS')
    if brief.get('denoise'):
        raise ValueError('denoise is not implemented and must not be requested')
    fade_in = float(brief.get('fadeIn') or 0)
    fade_out = float(brief.get('fadeOut') or 0)
    held = end - start
    if fade_in + fade_out > held:
        raise ValueError('fades cannot exceed the trimmed length')
    return {
        'path': path,
        'duration': duration,
        'start': start,
        'end': end,
        'fadeIn': fade_in,
        'fadeOut': fade_out,
        'gainDb': float(brief.get('gainDb') or 0),
        'loudness': loudness,
        'output': 'wav',
    }


def mix_spec(brief):
    checked = validate_brief(brief)
    held = checked['end'] - checked['start']
    return {
        'schemaVersion': 1,
        'duration': held,
        'loudness': checked['loudness'],
        'tracks': [{
            'path': checked['path'],
            'start': checked['start'],
            'end': checked['end'],
            'gainDb': checked['gainDb'],
            'fadeIn': checked['fadeIn'],
            'fadeOut': checked['fadeOut'],
        }],
    }


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='Plan audio-prep mix spec')
    parser.add_argument('--brief', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    out = Path(args.output)
    if out.exists():
        raise SystemExit('output must be a new file')
    spec = mix_spec(json.loads(Path(args.brief).read_text(encoding='utf-8')))
    out.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
