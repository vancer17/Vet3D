"""Write a local exhibition hall page into a new directory."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

CSS = """
:root { font-family: sans-serif; color: #111; }
body { margin: 0; }
main { display: grid; grid-template-columns: 1.4fr .8fr; min-height: 100vh; }
#hall { position: relative; background: #e8e4dc; min-height: 480px; }
.space { width: 100%; height: 70%; object-fit: cover; display: block; }
.space.virtual { height: 70%; background: linear-gradient(#d9d2c5, #c2b8a4); }
.spots { position: absolute; inset: 0; }
.hotspot { position: absolute; transform: translate(-50%,-50%); border: 2px solid #222; background: #fff; padding: .25rem .4rem; }
.hotspot.active { background: #ffe08a; }
.hotspot.missing { border-style: dashed; }
#panel { padding: 1rem; border-left: 1px solid #ccc; }
#panel img, #panel model-viewer { width: 100%; height: 240px; object-fit: contain; background: #eee; }
.notice, .pending { background: #f4f4f4; padding: .5rem .75rem; }
#tour-controls { grid-column: 1 / -1; padding: .75rem 1rem; border-top: 1px solid #ccc; display: flex; gap: .5rem; align-items: center; flex-wrap: wrap; }
"""


def copy_named(src: Path, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest.name


def write_hall(plan, skill_dir: Path, media_root: Path, output: Path):
    if output.exists():
        raise ValueError('output must be a new directory')
    plan = json.loads(json.dumps(plan))
    output.mkdir(parents=True)
    copied = []
    media_dir = output / 'media'
    media_dir.mkdir()
    for exhibit in plan['exhibits']:
        if exhibit['kind'] == 'missing' or not exhibit.get('file'):
            continue
        src = media_root / exhibit['file']
        if not src.is_file():
            exhibit['kind'] = 'missing'
            continue
        copy_named(src, media_dir / exhibit['file'])
        copied.append('media/' + exhibit['file'])
    if plan['space']['kind'] == 'existing':
        src = media_root / plan['space']['file']
        if not src.is_file():
            raise ValueError('existing space file is missing')
        space_dir = output / 'space'
        copy_named(src, space_dir / plan['space']['file'])
        copied.append('space/' + plan['space']['file'])
    has_model = any(item.get('kind') == 'model' for item in plan['exhibits']) or (
        plan['space']['kind'] == 'existing' and str(plan['space'].get('file', '')).lower().endswith('.glb')
    )
    runtime = '<script type="module" src="https://cdn.jsdelivr.net/npm/@google/model-viewer@4.0.0/dist/model-viewer.min.js"></script>' if has_model else ''
    plan_json = json.dumps(plan, ensure_ascii=False)
    (output / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (output / 'app.css').write_text(CSS, encoding='utf-8')
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{plan['title']}</title>
<link rel="stylesheet" href="app.css">
{runtime}
</head>
<body>
<main>
  <div id="hall"></div>
  <section id="panel"></section>
  <div id="tour-controls"></div>
</main>
<script>window.APP_PLAN = {plan_json};</script>
<script type="module" src="hall.js"></script>
</body>
</html>
"""
    (output / 'index.html').write_text(html, encoding='utf-8')
    shutil.copy2(skill_dir / 'scripts' / 'hall.js', output / 'hall.js')
    shutil.copy2(skill_dir / 'scripts' / 'tour.mjs', output / 'tour.mjs')
    core = skill_dir / 'scripts' / 'hi3d-core.mjs'
    if not core.is_file():
        raise FileNotFoundError('hi3d-core.mjs missing; materialize package.json first')
    shutil.copy2(core, output / 'hi3d-core.mjs')
    (output / 'README.txt').write_text(
        '用本地 HTTP 打开本目录。虚拟展厅不是测绘或 BIM。缺失展位可继续看其他展品。\n',
        encoding='utf-8',
    )
    (output / 'copied.json').write_text(json.dumps({'files': copied}, indent=2) + '\n', encoding='utf-8')
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description='Build exhibition-tour hall')
    parser.add_argument('--plan', required=True)
    parser.add_argument('--media', required=True)
    parser.add_argument('--skill-dir', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    plan = json.loads(Path(args.plan).read_text(encoding='utf-8'))
    write_hall(plan, Path(args.skill_dir), Path(args.media), Path(args.output))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
