"""Write a local asset review board into a new directory."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

CSS = """
:root { font-family: sans-serif; color: #111; }
body { margin: 0; }
header { padding: 1rem; }
.panes { display: grid; gap: 1rem; padding: 0 1rem 2rem; }
.layout-side .panes { grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }
.layout-single .panes { grid-template-columns: 1fr; }
.pane img, .pane video, .pane model-viewer { width: 100%; height: 280px; background: #eee; object-fit: contain; }
.notice { background: #f4f4f4; padding: .75rem; margin: 1rem; }
.warn, .error { color: #a40000; }
textarea { width: 100%; min-height: 4rem; }
"""


def write_board(plan, skill_dir: Path, media_root: Path, output: Path):
    if output.exists():
        raise ValueError('output must be a new directory')
    output.mkdir(parents=True)
    media_out = output / 'media'
    media_out.mkdir()
    copied = []
    for version in plan.get('versions') or []:
        src = media_root / version['file']
        if not src.is_file():
            raise ValueError('missing media: ' + version['file'])
        dest = media_out / version['file']
        if dest.exists():
            dest = media_out / f"{version['id']}-{version['file']}"
            version['file'] = dest.name
        shutil.copy2(src, dest)
        copied.append(f'media/{dest.name}')
    (output / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (output / 'app.css').write_text(CSS, encoding='utf-8')
    unimplemented = ''.join(f'<li>{item}：未实现</li>' for item in plan.get('unimplemented') or [])
    plan_json = json.dumps(plan, ensure_ascii=False)
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{plan['title']}</title>
<link rel="stylesheet" href="app.css">
<script type="module" src="https://cdn.jsdelivr.net/npm/@google/model-viewer@4.0.0/dist/model-viewer.min.js"></script>
</head>
<body>
<div id="board"></div>
<div id="unimplemented"></div>
<noscript><aside class="notice" role="note"><p>{plan.get('note','')}</p><ul>{unimplemented}</ul></aside></noscript>
<script>window.APP_PLAN = {plan_json};</script>
<script type="module" src="board.js"></script>
</body>
</html>
"""
    (output / 'index.html').write_text(html, encoding='utf-8')
    shutil.copy2(skill_dir / 'scripts' / 'board.js', output / 'board.js')
    shutil.copy2(skill_dir / 'scripts' / 'notes.mjs', output / 'notes.mjs')
    core = skill_dir / 'scripts' / 'hi3d-core.mjs'
    if not core.is_file():
        raise FileNotFoundError('hi3d-core.mjs missing; materialize package.json first')
    shutil.copy2(core, output / 'hi3d-core.mjs')
    (output / 'README.txt').write_text(
        '用本地 HTTP 打开本目录。批注绑定原版本，不自动迁到新版。\n'
        '导入失败不覆盖现有批注。覆盖导入需要确认并保留备份。\n'
        '存储失败时立刻导出。多人协作、账号、云端同步未实现。\n',
        encoding='utf-8',
    )
    (output / 'copied.json').write_text(json.dumps({'files': copied}, indent=2) + '\n', encoding='utf-8')
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description='Build asset-review-board page')
    parser.add_argument('--plan', required=True)
    parser.add_argument('--media', required=True)
    parser.add_argument('--skill-dir', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    plan = json.loads(Path(args.plan).read_text(encoding='utf-8'))
    write_board(plan, Path(args.skill_dir), Path(args.media), Path(args.output))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
