"""Build per-size svg-edit specs and region maps from a promo brief. No rendering."""
from __future__ import annotations

import json
from pathlib import Path


def load_layouts(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('schemaVersion') != 1 or 'formats' not in data or 'regions' not in data:
        raise ValueError('layouts.json must be schemaVersion 1 with formats and regions')
    return data


def validate_brief(brief):
    if not isinstance(brief, dict) or brief.get('schemaVersion') != 1:
        raise ValueError('brief schemaVersion must be 1')
    brand = brief.get('brand')
    title = brief.get('title')
    body = brief.get('body')
    if not isinstance(brand, str) or not brand.strip():
        raise ValueError('brand is required')
    if not isinstance(title, str) or not title.strip():
        raise ValueError('title is required accurate copy')
    if not isinstance(body, str):
        raise ValueError('body must be a string; use empty string when unused')
    formats = brief.get('formats')
    if formats is None:
        formats = ['square', 'banner', 'portrait']
    if not isinstance(formats, list) or not formats:
        raise ValueError('formats must be a nonempty list')
    text_only = brief.get('textOnly')
    product = brief.get('productImage')
    if text_only is True:
        if product:
            raise ValueError('textOnly cannot include productImage')
    elif product is None:
        raise ValueError('missing productImage; set textOnly true for copy-only layouts')
    elif not isinstance(product, str) or not product.strip() or '://' in product:
        raise ValueError('productImage must be a local path')
    colors = brief.get('colors') or {}
    if not isinstance(colors, dict):
        raise ValueError('colors must be an object')
    return {
        'brand': brand.strip(),
        'title': title,
        'body': body,
        'formats': list(formats),
        'textOnly': bool(text_only),
        'productImage': None if text_only else product,
        'crop': brief.get('crop'),
        'colors': {
            'background': colors.get('background', '#111111'),
            'title': colors.get('title', '#ffffff'),
            'body': colors.get('body', '#dddddd'),
        },
        'fontFamily': brief.get('fontFamily', 'sans-serif'),
    }


def svg_spec(brief, size_id, layout):
    fmt = layout['formats'][size_id]
    region = layout['regions'][size_id]
    colors = brief['colors']
    width, height = fmt['width'], fmt['height']
    ops = [
        {
            'op': 'add', 'id': 'bg', 'tag': 'rect',
            'attrs': {'width': width, 'height': height, 'fill': colors['background']},
        },
        {
            'op': 'add', 'id': 'title', 'tag': 'text',
            'attrs': {
                'x': region['title']['x'],
                'y': region['title']['y'] + region['title']['fontSize'],
                'fill': colors['title'],
                'font-size': region['title']['fontSize'],
                'font-family': brief['fontFamily'],
            },
            'text': brief['title'],
        },
    ]
    if brief['body']:
        ops.append({
            'op': 'add', 'id': 'body', 'tag': 'text',
            'attrs': {
                'x': region['body']['x'],
                'y': region['body']['y'] + region['body']['fontSize'],
                'fill': colors['body'],
                'font-size': region['body']['fontSize'],
                'font-family': brief['fontFamily'],
            },
            'text': brief['body'],
        })
    return {
        'schemaVersion': 1,
        'width': width,
        'height': height,
        'operations': ops,
        'formats': ['png'],
    }


def plan(brief, layout):
    checked = validate_brief(brief)
    unknown = [name for name in checked['formats'] if name not in layout['formats']]
    if unknown:
        raise ValueError('unsupported format: ' + ','.join(unknown))
    sizes = []
    for size_id in checked['formats']:
        sizes.append({
            'id': size_id,
            'label': layout['formats'][size_id].get('label', size_id),
            'width': layout['formats'][size_id]['width'],
            'height': layout['formats'][size_id]['height'],
            'regions': layout['regions'][size_id],
            'svg': svg_spec(checked, size_id, layout),
        })
    return {'brief': checked, 'sizes': sizes}


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='Plan promo layout specs')
    parser.add_argument('--brief', required=True)
    parser.add_argument('--layouts', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    out = Path(args.output)
    if out.exists():
        raise SystemExit('output must be a new file')
    result = plan(
        json.loads(Path(args.brief).read_text(encoding='utf-8')),
        load_layouts(args.layouts),
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
