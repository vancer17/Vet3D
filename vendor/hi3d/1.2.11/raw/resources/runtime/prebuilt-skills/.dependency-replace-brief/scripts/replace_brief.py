"""Locate screenshot replacement boxes and emit material-request gaps; no network."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SCHEMA = 'replace-brief.v1'
ROLES = {'replace', 'keep', 'context'}
KINDS = ('single_photo', 'multi_view_photos', 'existing_glb', 'measured_size', 'clean_cutout')
KIND_LABEL = {
    'single_photo': '单张清晰照片',
    'multi_view_photos': '同一物件的多视图照片',
    'existing_glb': '已有 GLB',
    'measured_size': '可核对的外形尺寸说明',
    'clean_cutout': '透明底抠图 PNG',
}
KIND_ACCEPTS = {
    'single_photo': ['.png', '.jpg', '.jpeg', '.webp'],
    'multi_view_photos': ['.png', '.jpg', '.jpeg', '.webp'],
    'existing_glb': ['.glb'],
    'measured_size': ['.txt', '.json'],
    'clean_cutout': ['.png'],
}


def _as_path(value):
    if isinstance(value, Path):
        return value
    if type(value) is str and value:
        return Path(value)
    raise ValueError('path must be a nonempty string')


def image_size(path):
    """Return (width, height) of an existing raster image; load pixels only as needed."""
    from PIL import Image
    path = _as_path(path)
    if not path.is_file():
        raise ValueError(f'missing screenshot {path}')
    with Image.open(path) as image:
        image.load()
        width, height = image.size
    if type(width) is not int or type(height) is not int or width < 1 or height < 1:
        raise ValueError('screenshot must have positive integer size')
    return width, height


def _finite_number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{name} must be a finite number')
    if value != value or value in (float('inf'), float('-inf')):
        raise ValueError(f'{name} must be a finite number')
    return float(value)


def as_int_box(box, *, width, height):
    """Pixel xyxy integers inside the image; right/bottom are exclusive."""
    if type(box) is not list or len(box) != 4:
        raise ValueError('bbox_px_xyxy must be [x0, y0, x1, y1]')
    x0, y0, x1, y1 = [_finite_number(v, 'bbox') for v in box]
    ix0, iy0, ix1, iy1 = int(x0), int(y0), int(x1), int(y1)
    if (ix0, iy0, ix1, iy1) != (x0, y0, x1, y1):
        raise ValueError('bbox_px_xyxy must be integers')
    if not (0 <= ix0 < ix1 <= width and 0 <= iy0 < iy1 <= height):
        raise ValueError('bbox_px_xyxy is empty or outside the screenshot')
    return [ix0, iy0, ix1, iy1]


def norm_from_px(box, *, width, height):
    x0, y0, x1, y1 = box
    return [x0 / width, y0 / height, x1 / width, y1 / height]


def px_from_norm(box, *, width, height):
    if type(box) is not list or len(box) != 4:
        raise ValueError('bbox_norm_xyxy must be [x0, y0, x1, y1]')
    x0, y0, x1, y1 = [_finite_number(v, 'bbox_norm') for v in box]
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise ValueError('bbox_norm_xyxy must lie in 0..1 with positive area')
    return [round(x0 * width), round(y0 * height), round(x1 * width), round(y1 * height)]


def _kinds(value, name):
    if type(value) is not list or not value:
        raise ValueError(f'{name} must be a nonempty list')
    seen = []
    for item in value:
        if item not in KINDS:
            raise ValueError(f'unknown material kind {item}')
        if item in seen:
            raise ValueError(f'duplicate material kind {item}')
        seen.append(item)
    return seen


def _text(value, name, *, allow_empty=False):
    if type(value) is not str or (not allow_empty and not value.strip()):
        raise ValueError(f'{name} must be a nonempty string')
    return value


def _file_record(path, kind):
    path = _as_path(path)
    if kind not in KINDS:
        raise ValueError(f'unknown material kind {kind}')
    if path.suffix.lower() not in KIND_ACCEPTS[kind]:
        raise ValueError(f'{path} does not match kind {kind}')
    if not path.is_file():
        raise ValueError(f'missing provided file {path}')
    data = path.read_bytes()
    if not data:
        raise ValueError(f'empty provided file {path}')
    return {
        'kind': kind,
        'path': str(path.resolve()),
        'bytes': len(data),
        'sha256': hashlib.sha256(data).hexdigest(),
    }


def validate_brief(brief, *, sizes):
    """Return a shallow-copied brief with checked boxes; sizes maps screenshot id to (w, h)."""
    if type(brief) is not dict or brief.get('schema') != SCHEMA:
        raise ValueError(f'schema must be {SCHEMA}')
    if type(sizes) is not dict or not sizes:
        raise ValueError('screenshot sizes are required')
    if 'intent' not in brief:
        raise ValueError('intent is required')
    _text(brief.get('intent'), 'intent', allow_empty=True)
    shots = brief.get('screenshots')
    if type(shots) is not list or not shots:
        raise ValueError('screenshots must be a nonempty list')
    shot_ids = []
    for shot in shots:
        if type(shot) is not dict:
            raise ValueError('each screenshot must be an object')
        sid = _text(shot.get('id'), 'screenshot id')
        if sid in shot_ids:
            raise ValueError(f'duplicate screenshot id {sid}')
        if sid not in sizes:
            raise ValueError(f'missing size for screenshot {sid}')
        width, height = sizes[sid]
        if shot.get('width') not in (None, width) or shot.get('height') not in (None, height):
            raise ValueError(f'screenshot {sid} size does not match the file')
        shot_ids.append(sid)
    targets = brief.get('targets')
    if type(targets) is not list or not targets:
        raise ValueError('targets must be a nonempty list')
    ids = []
    checked = []
    for target in targets:
        if type(target) is not dict:
            raise ValueError('each target must be an object')
        tid = _text(target.get('id'), 'target id')
        if tid in ids:
            raise ValueError(f'duplicate target id {tid}')
        ids.append(tid)
        role = target.get('role')
        if role not in ROLES:
            raise ValueError(f'target {tid} has invalid role')
        sid = target.get('screenshot_id', shot_ids[0])
        if sid not in sizes:
            raise ValueError(f'target {tid} references unknown screenshot {sid}')
        width, height = sizes[sid]
        box = as_int_box(target.get('bbox_px_xyxy'), width=width, height=height)
        expected = norm_from_px(box, width=width, height=height)
        if 'bbox_norm_xyxy' in target:
            from_norm = as_int_box(px_from_norm(target['bbox_norm_xyxy'], width=width, height=height),
                                   width=width, height=height)
            if from_norm != box:
                raise ValueError(f'target {tid} pixel and normalized boxes disagree')
        item = dict(target)
        item['screenshot_id'] = sid
        item['bbox_px_xyxy'] = box
        item['bbox_norm_xyxy'] = expected
        item['label'] = _text(item.get('label'), f'target {tid} label')
        item['evidence'] = _text(item.get('evidence'), f'target {tid} evidence')
        inferred = item.get('inferred', [])
        if type(inferred) is not list or any(type(v) is not str for v in inferred):
            raise ValueError(f'target {tid} inferred must be a string list')
        item['inferred'] = inferred
        if role == 'replace':
            needed = item.get('material_needed')
            if type(needed) is not dict:
                raise ValueError(f'target {tid} material_needed is required')
            item['material_needed'] = {
                'minimum': _kinds(needed.get('minimum'), f'target {tid} minimum'),
                'preferred': _kinds(needed.get('preferred'), f'target {tid} preferred'),
                'notes': _text(needed.get('notes', ''), f'target {tid} notes', allow_empty=True),
            }
        provided = item.get('provided', [])
        if type(provided) is not list:
            raise ValueError(f'target {tid} provided must be a list')
        records = []
        for entry in provided:
            if type(entry) is not dict:
                raise ValueError(f'target {tid} provided entries must be objects')
            records.append(_file_record(entry.get('path'), entry.get('kind')))
        item['provided'] = records
        checked.append(item)
    out = dict(brief)
    out['targets'] = checked
    out['screenshots'] = [
        dict(shot, width=sizes[shot['id']][0], height=sizes[shot['id']][1])
        for shot in shots
    ]
    return out


def request_gaps(targets):
    """Return request objects for replace targets whose minimum kinds are not all provided."""
    if type(targets) is not list:
        raise ValueError('targets must be a list')
    requests = []
    updated = []
    for target in targets:
        item = dict(target)
        if item.get('role') != 'replace':
            item['status'] = 'skipped_keep'
            updated.append(item)
            continue
        have = {entry['kind'] for entry in item.get('provided', [])}
        missing = [kind for kind in item['material_needed']['minimum'] if kind not in have]
        if not missing:
            item['status'] = 'ready'
            updated.append(item)
            continue
        item['status'] = 'awaiting_material'
        notes = item['material_needed']['notes'].strip()
        preferred = '、'.join(KIND_LABEL[k] for k in item['material_needed']['preferred'])
        ask = (
            f"请提供「{item['label']}」的替换素材。"
            f"至少需要：{'、'.join(KIND_LABEL[k] for k in missing)}。"
            f"更有利于还原的：{preferred}。"
        )
        if notes:
            ask += notes if notes.endswith(('。', '！', '？')) else notes + '。'
        accepts = []
        for kind in missing:
            for ext in KIND_ACCEPTS[kind]:
                if ext not in accepts:
                    accepts.append(ext)
        requests.append({
            'target_id': item['id'],
            'label': item['label'],
            'ask': ask,
            'accepts': accepts,
            'missing': missing,
        })
        updated.append(item)
    return requests, updated


def annotate_image(image, targets):
    """Return a new RGB copy with boxes and ids; never alter the source image."""
    from PIL import ImageDraw, ImageFont
    canvas = image.convert('RGB').copy()
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for target in targets:
        x0, y0, x1, y1 = target['bbox_px_xyxy']
        color = (220, 64, 48) if target.get('role') == 'replace' else (48, 140, 96)
        draw.rectangle([x0, y0, x1 - 1, y1 - 1], outline=color, width=2)
        draw.text((x0 + 2, y0 + 2), target['id'], fill=color, font=font)
    return canvas


def crop_targets(image, targets):
    """Return {id: cropped RGB image} for replace targets; source image is unchanged."""
    crops = {}
    source = image.convert('RGB')
    original = source.tobytes()
    for target in targets:
        if target.get('role') != 'replace':
            continue
        x0, y0, x1, y1 = target['bbox_px_xyxy']
        crops[target['id']] = source.crop((x0, y0, x1, y1))
    if source.tobytes() != original:
        raise RuntimeError('screenshot pixels changed')
    return crops


def _load_json(path):
    path = _as_path(path)
    with path.open() as handle:
        value = json.load(handle)
    if type(value) is not dict:
        raise ValueError('JSON root must be an object')
    return value


def build_output(brief, screenshots, output_dir):
    """Validate, crop, annotate and write a new directory. screenshots maps id -> path."""
    from PIL import Image
    output_dir = _as_path(output_dir)
    if output_dir.exists():
        raise FileExistsError(output_dir)
    sizes = {}
    images = {}
    for sid, path in screenshots.items():
        path = _as_path(path).resolve()
        sizes[sid] = image_size(path)
        with Image.open(path) as image:
            image.load()
            images[sid] = image.convert('RGB')
    checked = validate_brief(brief, sizes=sizes)
    requests, targets = request_gaps(checked['targets'])
    checked['targets'] = targets
    checked['requests'] = requests
    for shot in checked['screenshots']:
        path = _as_path(screenshots[shot['id']]).resolve()
        shot['path'] = str(path)
        shot['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    output_dir.mkdir(parents=True)
    crop_dir = output_dir / 'crops'
    crop_dir.mkdir()
    try:
        for sid, image in images.items():
            overlay = annotate_image(image, [t for t in targets if t['screenshot_id'] == sid])
            name = 'overlay.png' if len(images) == 1 else f'overlay-{sid}.png'
            overlay_path = output_dir / name
            overlay.save(overlay_path, format='PNG')
            shot = next(item for item in checked['screenshots'] if item['id'] == sid)
            shot['overlay'] = str(overlay_path.resolve())
        crops = {}
        for sid, image in images.items():
            crops.update(crop_targets(image, [t for t in targets if t['screenshot_id'] == sid]))
        for tid, crop in crops.items():
            dest = crop_dir / f'{tid}.png'
            crop.save(dest, format='PNG')
            target = next(item for item in targets if item['id'] == tid)
            target['crop'] = str(dest.resolve())
        (output_dir / 'brief.json').write_text(json.dumps(checked, ensure_ascii=False, indent=2) + '\n')
        (output_dir / 'requests.json').write_text(json.dumps(requests, ensure_ascii=False, indent=2) + '\n')
    except Exception:
        raise
    return {
        'output': str(output_dir.resolve()),
        'brief': str((output_dir / 'brief.json').resolve()),
        'requests': str((output_dir / 'requests.json').resolve()),
        'awaiting': [item['target_id'] for item in requests],
        'ready': [item['id'] for item in targets if item.get('status') == 'ready'],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--brief', type=Path, required=True)
    parser.add_argument('--screenshot', action='append', nargs=2, metavar=('ID', 'PATH'), required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check', action='store_true', help='validate only; do not write files')
    args = parser.parse_args(argv)
    brief = _load_json(args.brief)
    screenshots = {sid: Path(path) for sid, path in args.screenshot}
    if args.check:
        sizes = {sid: image_size(path) for sid, path in screenshots.items()}
        checked = validate_brief(brief, sizes=sizes)
        requests, targets = request_gaps(checked['targets'])
        print(json.dumps({
            'ok': True,
            'targets': [item['id'] for item in targets],
            'awaiting': [item['target_id'] for item in requests],
        }, ensure_ascii=False, indent=2))
        return 0
    if args.output is None:
        parser.error('--output is required unless --check')
    print(json.dumps(build_output(brief, screenshots, args.output), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
