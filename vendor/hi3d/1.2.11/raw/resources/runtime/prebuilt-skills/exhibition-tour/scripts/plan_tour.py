"""Validate exhibition-tour brief. Does not invent exhibit history or survey a hall."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import layout

MODES = {'free', 'auto', 'both'}
KINDS = {'image', 'model', 'missing'}
SPACES = {'existing', 'virtual'}


def load_modes(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('schemaVersion') != 1:
        raise ValueError('modes.json must be schemaVersion 1')
    return data


def _safe_rel(name):
    p = Path(name)
    if p.is_absolute() or '..' in p.parts:
        raise ValueError('asset paths must be relative filenames')
    return p.name


def validate_plan(brief, modes=None):
    if not isinstance(brief, dict) or brief.get('schemaVersion') != 1:
        raise ValueError('brief schemaVersion must be 1')
    exhibits = brief.get('exhibits')
    if not isinstance(exhibits, list) or not exhibits:
        raise ValueError('exhibits must be a nonempty list')
    ids = []
    normalized = []
    for item in exhibits:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str) or item['id'] in ids:
            raise ValueError('exhibit id must be unique')
        kind = item.get('kind', 'image')
        if kind not in KINDS:
            raise ValueError('exhibit kind must be image, model or missing')
        source = item.get('file')
        title = item.get('title')
        caption = item.get('caption')
        pending = item.get('pending') is True
        if not title or not str(title).strip():
            if source:
                title = Path(source).stem
                pending = True
            elif kind == 'missing':
                title = item['id']
                pending = True
            else:
                raise ValueError('exhibit needs title or filename')
        if not caption or not str(caption).strip():
            caption = Path(source).name if source else title
            pending = True
        if kind == 'missing' or not source:
            kind = 'missing'
            source_name = None
        else:
            source_name = _safe_rel(source)
        dwell = item.get('dwellSeconds', (modes or {}).get('defaultDwellSeconds', 4))
        if type(dwell) not in (int, float) or isinstance(dwell, bool) or dwell <= 0:
            raise ValueError('dwellSeconds must be a positive number')
        normalized.append({
            'id': item['id'],
            'kind': kind,
            'title': str(title).strip(),
            'caption': str(caption).strip(),
            'pending': pending,
            'file': source_name,
            'dwellSeconds': dwell,
        })
        ids.append(item['id'])
    order = brief.get('order') or ids
    if sorted(order) != sorted(ids) or len(order) != len(ids):
        raise ValueError('order must list each exhibit once')
    space = brief.get('space') or {'kind': 'virtual'}
    if space.get('kind') not in SPACES:
        raise ValueError('space.kind must be existing or virtual')
    if space['kind'] == 'existing':
        hall = space.get('file')
        if not hall:
            raise ValueError('existing space requires a real file')
        space = {'kind': 'existing', 'file': _safe_rel(hall), 'surveyed': False}
    else:
        space = {'kind': 'virtual', 'surveyed': False, 'note': '按展品数量自动布置的虚拟展厅，不是建筑测绘或 BIM 成果。'}
    mode = brief.get('mode', (modes or {}).get('defaultMode', 'both'))
    if mode not in MODES:
        raise ValueError('mode must be free, auto or both')
    positions = brief.get('positions')
    if positions:
        if isinstance(positions, list):
            if len(positions) != len(ids):
                raise ValueError('positions must match exhibits')
            positions = {exhibit_id: positions[index] for index, exhibit_id in enumerate(order)}
        elif isinstance(positions, dict):
            if set(positions) != set(ids):
                raise ValueError('positions must match exhibits')
        else:
            raise ValueError('positions must be a list or object')
        for spot in positions.values():
            if not isinstance(spot, dict) or 'x' not in spot or 'y' not in spot:
                raise ValueError('each position needs x and y')
    else:
        spots = layout.auto_layout(len(ids))
        positions = {exhibit_id: spots[index] for index, exhibit_id in enumerate(order)}
    title = brief.get('title')
    if not isinstance(title, str) or not title.strip():
        raise ValueError('title is required')
    return {
        'title': title.strip(),
        'exhibits': normalized,
        'order': order,
        'positions': positions,
        'space': space,
        'mode': mode,
        'appId': brief.get('appId') or 'exhibition-tour',
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description='Plan an exhibition-tour')
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
