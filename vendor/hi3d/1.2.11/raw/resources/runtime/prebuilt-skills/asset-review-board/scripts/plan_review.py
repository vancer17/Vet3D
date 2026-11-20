"""Validate an asset-review-board brief. Does not treat unrelated files as sequential versions."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

KINDS = {'image', 'video', 'model'}
LAYOUTS = {'side_by_side', 'single'}
CRITERIA = {'appearance', 'structure', 'motion', 'free'}
VERSION_TOKEN = re.compile(r'(?:^|[_-])v(\d+)$', re.I)


def load_review(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('schemaVersion') != 1:
        raise ValueError('review.json must be schemaVersion 1')
    return data


def _safe_name(name):
    p = Path(name)
    if p.is_absolute() or '..' in p.parts:
        raise ValueError('file must be a relative filename')
    return p.name


def infer_version_label(filename):
    stem = Path(filename).stem
    match = VERSION_TOKEN.search(stem)
    if match:
        return 'v' + match.group(1), stem[: match.start()] or stem
    return None, stem


def validate_plan(brief, review=None):
    if not isinstance(brief, dict) or brief.get('schemaVersion') != 1:
        raise ValueError('brief schemaVersion must be 1')
    versions = brief.get('versions')
    if not isinstance(versions, list) or not versions:
        raise ValueError('versions must be a nonempty list')
    ids = []
    assets = {}
    inferred_groups = {}
    normalized = []
    for item in versions:
        if not isinstance(item, dict):
            raise ValueError('version must be an object')
        ident = item.get('id')
        if not isinstance(ident, str) or ident in ids:
            raise ValueError('version id must be unique')
        kind = item.get('kind')
        if kind not in KINDS:
            raise ValueError('kind must be image, video or model')
        asset_id = item.get('assetId')
        filename = _safe_name(item.get('file') or '')
        inferred, group = infer_version_label(filename)
        if not asset_id:
            if inferred and group:
                asset_id = group
                inferred_groups.setdefault(group, []).append(ident)
            else:
                raise ValueError('assetId required when filename version is ambiguous: ' + filename)
        label = item.get('label') or inferred or ident
        duration = item.get('durationSeconds')
        if kind == 'video' and duration is not None:
            if type(duration) not in (int, float) or isinstance(duration, bool) or duration <= 0:
                raise ValueError('video durationSeconds must be a positive number')
        assets.setdefault(asset_id, []).append(ident)
        normalized.append({
            'id': ident,
            'assetId': asset_id,
            'label': str(label),
            'kind': kind,
            'file': filename,
            'durationSeconds': duration,
        })
        ids.append(ident)
    if brief.get('confirmedGrouping') is not True:
        for group, members in inferred_groups.items():
            kinds = {v['kind'] for v in normalized if v['id'] in members}
            if len(kinds) > 1:
                raise ValueError('refusing to treat mixed kinds as sequential versions of ' + group)
    layout = brief.get('layout') or (review or {}).get('defaultLayout', 'side_by_side')
    if len(normalized) == 1:
        layout = 'single'
    if layout not in LAYOUTS:
        raise ValueError('layout must be side_by_side or single')
    criteria = brief.get('criteria') or (review or {}).get('defaultCriteria') or ['free']
    if not isinstance(criteria, list) or any(item not in CRITERIA for item in criteria):
        raise ValueError('criteria must be appearance, structure, motion or free')
    title = brief.get('title')
    if not isinstance(title, str) or not title.strip():
        raise ValueError('title is required')
    videos = [item for item in normalized if item['kind'] == 'video' and item.get('durationSeconds')]
    duration_warning = None
    if len({item['durationSeconds'] for item in videos}) > 1:
        duration_warning = '视频时长不同，同步播放不能对齐全部时间'
    return {
        'title': title.strip(),
        'versions': normalized,
        'layout': layout,
        'criteria': criteria,
        'durationWarning': duration_warning,
        'appId': brief.get('appId') or 'asset-review-board',
        'unimplemented': brief.get('unimplemented') or ['多人实时协作', '账号', '云端同步'],
        'note': '批注模板不是质量结论。批注绑定原版本，不自动迁到新版。',
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description='Plan an asset-review-board')
    parser.add_argument('--brief', required=True)
    parser.add_argument('--review', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    out = Path(args.output)
    if out.exists():
        raise SystemExit('output must be a new file')
    plan = validate_plan(json.loads(Path(args.brief).read_text(encoding='utf-8')), load_review(args.review))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
