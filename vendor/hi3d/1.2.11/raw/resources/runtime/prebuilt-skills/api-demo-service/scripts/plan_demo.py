"""Validate an api-demo-service brief. Does not wrap host-internal algorithms."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

FIELD_TYPES = {'string', 'number', 'boolean', 'file'}
MODES = {'sync', 'background'}


def load_modes(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('schemaVersion') != 1:
        raise ValueError('modes.json must be schemaVersion 1')
    return data


def _safe_name(name):
    p = Path(name)
    if p.is_absolute() or '..' in p.parts:
        raise ValueError('entry must be a relative filename')
    return p.name


def validate_argv(argv):
    if argv is None:
        return None
    if not isinstance(argv, list) or not argv or any(not isinstance(item, str) or not item for item in argv):
        raise ValueError('argv must be a nonempty list of strings')
    joined = ' '.join(argv)
    if any(token in joined for token in ('{', '}', '$(', '`')):
        raise ValueError('argv must not interpolate request fields or shell substitutions')
    return list(argv)


def validate_plan(brief, modes=None):
    if not isinstance(brief, dict) or brief.get('schemaVersion') != 1:
        raise ValueError('brief schemaVersion must be 1')
    title = brief.get('title')
    if not isinstance(title, str) or not title.strip():
        raise ValueError('title is required')
    entry = _safe_name(brief.get('entry') or '')
    function = brief.get('function') or 'run'
    if not isinstance(function, str) or not function.isidentifier():
        raise ValueError('function must be a Python identifier')
    fields = brief.get('fields')
    if not isinstance(fields, list) or not fields:
        raise ValueError('fields must be a nonempty list')
    ids = []
    normalized_fields = []
    for field in fields:
        if not isinstance(field, dict):
            raise ValueError('field must be an object')
        ident = field.get('id')
        if not isinstance(ident, str) or ident in ids:
            raise ValueError('field id must be unique')
        kind = field.get('type')
        if kind not in FIELD_TYPES:
            raise ValueError('field type must be string, number, boolean or file')
        label = field.get('label') or ident
        required = field.get('required') is not False if kind != 'file' else field.get('required') is True
        item = {'id': ident, 'type': kind, 'label': str(label), 'required': required}
        if kind == 'file':
            suffixes = field.get('suffixes') or []
            if not isinstance(suffixes, list) or any(not isinstance(s, str) or not s.startswith('.') for s in suffixes):
                raise ValueError('file suffixes must be like .txt')
            item['suffixes'] = suffixes
        ids.append(ident)
        normalized_fields.append(item)
    sample = brief.get('sample')
    if not isinstance(sample, dict):
        raise ValueError('sample object is required')
    expected_seconds = brief.get('sampleSeconds')
    if expected_seconds is not None and (type(expected_seconds) not in (int, float) or isinstance(expected_seconds, bool) or expected_seconds < 0):
        raise ValueError('sampleSeconds must be a non-negative number')
    defaults = (modes or {}).get('defaultLimits') or {'maxBytes': 1048576, 'timeoutSeconds': 8, 'concurrency': 1}
    limits = dict(defaults)
    limits.update(brief.get('limits') or {})
    for key in ('maxBytes', 'timeoutSeconds', 'concurrency'):
        value = limits.get(key)
        if type(value) not in (int, float) or isinstance(value, bool) or value <= 0:
            raise ValueError(key + ' must be a positive number')
        limits[key] = int(value) if key != 'timeoutSeconds' else float(value)
    if limits['concurrency'] < 1:
        raise ValueError('concurrency must be at least 1')
    mode = brief.get('mode') or (modes or {}).get('defaultMode', 'sync')
    if expected_seconds is not None and expected_seconds > limits['timeoutSeconds'] and mode == 'sync':
        raise ValueError('cannot choose sync when the sample already exceeds timeoutSeconds')
    if expected_seconds is not None and expected_seconds > 5 and 'mode' not in brief:
        mode = 'background'
    if mode not in MODES:
        raise ValueError('mode must be sync or background')
    argv = validate_argv(brief.get('argv'))
    return {
        'title': title.strip(),
        'entry': entry,
        'function': function,
        'fields': normalized_fields,
        'sample': sample,
        'sampleSeconds': expected_seconds,
        'mode': mode,
        'limits': limits,
        'argv': argv,
        'appId': brief.get('appId') or 'api-demo-service',
        'note': '只封装用户提供的一个算法。校验失败与算法失败分开显示。请求不会拼进 shell。',
        'unimplemented': brief.get('unimplemented') or ['公开部署', '密钥面板', '多算法路由', 'MDF 队列'],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description='Plan an api-demo-service')
    parser.add_argument('--brief', required=True)
    parser.add_argument('--modes', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    out = Path(args.output)
    if out.exists():
        raise SystemExit('output must be a new file')
    plan = validate_plan(json.loads(Path(args.brief).read_text(encoding='utf-8')), load_modes(args.modes))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
