"""Refuse silent truncation: measure title/body boxes against the canvas."""
from __future__ import annotations

from pathlib import Path


def load_font(font_path, size):
    from PIL import ImageFont
    if font_path:
        return ImageFont.truetype(str(font_path), size), False
    try:
        return ImageFont.truetype('DejaVuSans.ttf', size), True
    except OSError:
        return ImageFont.load_default(), True


def text_size(font, text):
    if hasattr(font, 'getbbox'):
        box = font.getbbox(text)
        return box[2] - box[0], box[3] - box[1]
    return font.getsize(text)


def check_boxes(width, height, boxes, font_path=None):
    issues = []
    substitute = False
    for item in boxes:
        ident = item['id']
        text = item.get('text') or ''
        if not text:
            continue
        font, used_sub = load_font(font_path, int(item['fontSize']))
        substitute = substitute or used_sub
        tw, th = text_size(font, text)
        box_w, box_h = item['width'], item['height']
        if tw > box_w or th > box_h:
            issues.append({
                'id': ident,
                'reason': 'overflow',
                'text_width': tw,
                'text_height': th,
                'box_width': box_w,
                'box_height': box_h,
            })
        if item['x'] < 0 or item['y'] < 0 or item['x'] + box_w > width or item['y'] + box_h > height:
            issues.append({'id': ident, 'reason': 'outside_canvas'})
    return {'ok': not issues, 'font_substituted': substitute, 'issues': issues}


def boxes_from_size(size, brief):
    regions = size['regions']
    mapping = [('title', brief['title']), ('body', brief.get('body') or '')]
    boxes = []
    for key, text in mapping:
        region = regions[key]
        boxes.append({
            'id': key,
            'text': text,
            'x': region['x'],
            'y': region['y'],
            'width': region['width'],
            'height': region['height'],
            'fontSize': region['fontSize'],
        })
    return boxes


def main(argv=None):
    import argparse, json
    parser = argparse.ArgumentParser(description='Check promo text overflow')
    parser.add_argument('--plan', required=True)
    parser.add_argument('--font', default='')
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    plan = json.loads(Path(args.plan).read_text(encoding='utf-8'))
    reports = []
    failed = False
    for size in plan['sizes']:
        report = check_boxes(
            size['width'], size['height'],
            boxes_from_size(size, plan['brief']),
            args.font or None,
        )
        report['id'] = size['id']
        reports.append(report)
        if not report['ok']:
            failed = True
    out = Path(args.output)
    if out.exists():
        raise SystemExit('output must be a new file')
    out.write_text(json.dumps({'reports': reports}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
