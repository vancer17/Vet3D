"""Flatten a confirmed crop of the product image under already-measured text boxes."""
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))


def crop_image(source, crop, box):
    from PIL import Image
    image = Image.open(source).convert('RGBA')
    if crop:
        x, y, w, h = crop['x'], crop['y'], crop['width'], crop['height']
        if x < 0 or y < 0 or x + w > image.width or y + h > image.height:
            raise ValueError('crop is outside the product image')
        image = image.crop((x, y, x + w, y + h))
    target_w, target_h = box['width'], box['height']
    fitted = image.copy()
    fitted.thumbnail((target_w, target_h))
    canvas = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))
    ox = (target_w - fitted.width) // 2
    oy = (target_h - fitted.height) // 2
    canvas.paste(fitted, (ox, oy))
    return canvas


def compose(size, brief, product_path, overlay_png, destination, font_path=None):
    from PIL import Image, ImageDraw
    from overflow_check import load_font, boxes_from_size
    canvas = Image.new('RGB', (size['width'], size['height']), brief['colors']['background'])
    if product_path:
        placed = crop_image(product_path, brief.get('crop'), size['regions']['image'])
        layer = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        box = size['regions']['image']
        layer.paste(placed, (box['x'], box['y']))
        canvas = Image.alpha_composite(canvas.convert('RGBA'), layer).convert('RGB')
    if overlay_png:
        overlay = Image.open(overlay_png).convert('RGBA')
        canvas = Image.alpha_composite(canvas.convert('RGBA'), overlay).convert('RGB')
    else:
        draw = ImageDraw.Draw(canvas)
        for item in boxes_from_size(size, brief):
            if not item['text']:
                continue
            font, _ = load_font(font_path, item['fontSize'])
            color = brief['colors']['title'] if item['id'] == 'title' else brief['colors']['body']
            draw.text((item['x'], item['y']), item['text'], fill=color, font=font)
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, 'PNG')
    return destination


def main(argv=None):
    import argparse, json
    parser = argparse.ArgumentParser(description='Compose a flattened promo PNG')
    parser.add_argument('--plan', required=True)
    parser.add_argument('--size', required=True)
    parser.add_argument('--product', default='')
    parser.add_argument('--overlay', default='')
    parser.add_argument('--font', default='')
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    out = Path(args.output)
    if out.exists():
        raise SystemExit('output must be a new file')
    plan = json.loads(Path(args.plan).read_text(encoding='utf-8'))
    size = next(item for item in plan['sizes'] if item['id'] == args.size)
    compose(
        size, plan['brief'],
        args.product or plan['brief'].get('productImage'),
        args.overlay or None,
        out,
        args.font or None,
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
