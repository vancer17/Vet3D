"""Write a layered HTML page: product image and copy stay in separate elements."""
from __future__ import annotations

import html
from pathlib import Path


TEMPLATE = """<!DOCTYPE html>
<html lang="zh-Hans">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  body {{ margin: 0; background: #222; color: #eee; font-family: sans-serif; }}
  .stage {{ position: relative; width: {width}px; height: {height}px; margin: 24px auto;
            background: {background}; overflow: hidden; }}
  .stage img {{ position: absolute; left: {ix}px; top: {iy}px; width: {iw}px; height: {ih}px; object-fit: contain; }}
  .title, .body {{ position: absolute; margin: 0; white-space: pre-wrap; overflow: visible; }}
  .title {{ left: {tx}px; top: {ty}px; width: {tw}px; height: {th}px; font-size: {tfs}px; color: {tc}; }}
  .body {{ left: {bx}px; top: {by}px; width: {bw}px; height: {bh}px; font-size: {bfs}px; color: {bc}; }}
</style>
</head>
<body>
  <div class="stage">
    {image}
    <p class="title">{title_text}</p>
    <p class="body">{body_text}</p>
  </div>
</body>
</html>
"""


def render(size, brief, image_href):
    region = size['regions']
    image = ''
    if image_href:
        image = '<img src="{}" alt="">'.format(html.escape(image_href, quote=True))
    return TEMPLATE.format(
        title=html.escape(brief['title']),
        width=size['width'], height=size['height'],
        background=html.escape(brief['colors']['background'], quote=True),
        ix=region['image']['x'], iy=region['image']['y'],
        iw=region['image']['width'], ih=region['image']['height'],
        tx=region['title']['x'], ty=region['title']['y'],
        tw=region['title']['width'], th=region['title']['height'],
        tfs=region['title']['fontSize'],
        tc=html.escape(brief['colors']['title'], quote=True),
        bx=region['body']['x'], by=region['body']['y'],
        bw=region['body']['width'], bh=region['body']['height'],
        bfs=region['body']['fontSize'],
        bc=html.escape(brief['colors']['body'], quote=True),
        image=image,
        title_text=html.escape(brief['title']),
        body_text=html.escape(brief.get('body') or ''),
    )


def main(argv=None):
    import argparse, json
    parser = argparse.ArgumentParser(description='Write layered promo HTML')
    parser.add_argument('--plan', required=True)
    parser.add_argument('--size', required=True)
    parser.add_argument('--image-href', default='')
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    out = Path(args.output)
    if out.exists():
        raise SystemExit('output must be a new file')
    plan = json.loads(Path(args.plan).read_text(encoding='utf-8'))
    size = next(item for item in plan['sizes'] if item['id'] == args.size)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(size, plan['brief'], args.image_href), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
