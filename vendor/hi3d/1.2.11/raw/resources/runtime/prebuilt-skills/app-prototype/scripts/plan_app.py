"""Validate an app-prototype brief. Does not invent business records."""
from __future__ import annotations

import json
from pathlib import Path

LAYOUTS = {'table', 'cards', 'adaptive'}
FIELD_TYPES = {'string', 'number', 'enum', 'boolean'}


def load_examples(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('schemaVersion') != 1 or 'examples' not in data:
        raise ValueError('examples.json must be schemaVersion 1')
    return data['examples']


def validate_fields(fields):
    if not isinstance(fields, list) or not fields:
        raise ValueError('fields must be a nonempty list')
    ids = []
    for field in fields:
        if not isinstance(field, dict):
            raise ValueError('field must be an object')
        ident = field.get('id')
        label = field.get('label')
        kind = field.get('type')
        if not isinstance(ident, str) or not ident.strip() or ident in ids:
            raise ValueError('field id must be unique')
        if not isinstance(label, str) or not label.strip():
            raise ValueError('field label is required')
        if kind not in FIELD_TYPES:
            raise ValueError('unsupported field type')
        if kind == 'enum':
            options = field.get('options')
            if not isinstance(options, list) or len(options) < 2:
                raise ValueError('enum fields need at least two options')
        ids.append(ident)
    return ids


def validate_brief(brief, examples=None):
    if not isinstance(brief, dict) or brief.get('schemaVersion') != 1:
        raise ValueError('brief schemaVersion must be 1')
    preset = brief.get('examplePreset')
    if preset:
        if not examples or preset not in examples:
            raise ValueError('unknown examplePreset')
        seed = dict(examples[preset])
        for key in ('actor', 'scene', 'entity', 'primaryAction', 'fields', 'statusField', 'records'):
            brief.setdefault(key, seed.get(key))
        brief['dataSource'] = 'example'
    for key in ('actor', 'scene', 'entity', 'primaryAction'):
        if not isinstance(brief.get(key), str) or not brief[key].strip():
            raise ValueError(key + ' is required')
    field_ids = validate_fields(brief.get('fields'))
    status = brief.get('statusField')
    if status is not None and status not in field_ids:
        raise ValueError('statusField must name a field')
    layout = brief.get('layout', 'adaptive')
    if layout not in LAYOUTS:
        raise ValueError('layout must be table, cards or adaptive')
    records = brief.get('records') or []
    if not isinstance(records, list):
        raise ValueError('records must be a list')
    if brief.get('dataSource') != 'example':
        for item in records:
            if isinstance(item, dict) and item.get('example') is True:
                raise ValueError('example records cannot be labeled as real business data')
    else:
        for item in records:
            if not isinstance(item, dict) or item.get('example') is not True:
                raise ValueError('examplePreset records must keep example true')
    unimplemented = brief.get('unimplemented') or ['登录', '支付', '多人同步']
    return {
        'actor': brief['actor'].strip(),
        'scene': brief['scene'].strip(),
        'entity': brief['entity'].strip(),
        'primaryAction': brief['primaryAction'].strip(),
        'fields': brief['fields'],
        'statusField': status,
        'layout': layout,
        'records': records,
        'dataSource': brief.get('dataSource', 'user'),
        'unimplemented': list(unimplemented),
        'appId': brief.get('appId') or 'app-prototype',
    }


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='Plan an app-prototype brief')
    parser.add_argument('--brief', required=True)
    parser.add_argument('--examples', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    out = Path(args.output)
    if out.exists():
        raise SystemExit('output must be a new file')
    brief = json.loads(Path(args.brief).read_text(encoding='utf-8'))
    plan = validate_brief(brief, load_examples(args.examples))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
