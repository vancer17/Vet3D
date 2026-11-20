"""Write list/detail/edit HTML into a new directory."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

PAGES = {
    'index.html': 'list',
    'detail.html': 'detail',
    'edit.html': 'edit',
}

CSS = """
:root { font-family: sans-serif; color: #111; }
body { margin: 0; }
#app { max-width: 960px; margin: 0 auto; padding: 1rem; }
.notice { background: #f4f4f4; padding: .75rem 1rem; }
.notice ul { margin: .25rem 0 0; }
.error { color: #a40000; min-height: 1em; }
.example { color: #6b4f00; font-size: .9em; }
.toolbar { display: flex; flex-wrap: wrap; gap: .5rem; align-items: center; margin: 1rem 0; }
.field { margin-bottom: 1rem; }
.cards { display: none; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; }
th, td { border-bottom: 1px solid #ddd; padding: .4rem; text-align: left; }
body.layout-cards .table-wrap { display: none; }
body.layout-cards .cards { display: grid; gap: 1rem; }
body.layout-adaptive .cards { display: none; }
@media (max-width: 720px) {
  body.layout-adaptive .table-wrap { display: none; }
  body.layout-adaptive .cards { display: grid; gap: 1rem; }
}
.card { border: 1px solid #ddd; padding: 1rem; }
"""


def shell_html(page, plan):
    title = {'list': '列表', 'detail': '详情', 'edit': '编辑'}[page]
    plan_json = json.dumps(plan, ensure_ascii=False)
    unimplemented = ''.join(f'<li>{item}：未实现</li>' for item in plan.get('unimplemented') or [])
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="app.css">
</head>
<body data-page="{page}">
<noscript><aside class="notice" role="note"><p>需要 JavaScript。以下能力未实现：</p><ul>{unimplemented}</ul></aside></noscript>
<div id="app"></div>
<script>window.APP_PLAN = {plan_json};</script>
<script type="module" src="app.js"></script>
</body>
</html>
"""


def write_app(plan, skill_dir: Path, output: Path):
    if output.exists():
        raise ValueError('output must be a new directory')
    output.mkdir(parents=True)
    (output / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (output / 'app.css').write_text(CSS, encoding='utf-8')
    for name, page in PAGES.items():
        (output / name).write_text(shell_html(page, plan), encoding='utf-8')
    shutil.copy2(skill_dir / 'scripts' / 'app.js', output / 'app.js')
    shutil.copy2(skill_dir / 'scripts' / 'records.mjs', output / 'records.mjs')
    core = skill_dir / 'scripts' / 'hi3d-core.mjs'
    if not core.is_file():
        raise FileNotFoundError('hi3d-core.mjs missing; materialize package.json first')
    shutil.copy2(core, output / 'hi3d-core.mjs')
    (output / 'README.txt').write_text(
        '用本地 HTTP 打开本目录，例如 python3 -m http.server。不要用 file:// 检查模块导入。\n'
        '导入备份前会先 decode；失败不覆盖现有存档。登录、支付、多人同步未实现。\n',
        encoding='utf-8',
    )
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description='Build app-prototype HTML')
    parser.add_argument('--plan', required=True)
    parser.add_argument('--skill-dir', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    plan = json.loads(Path(args.plan).read_text(encoding='utf-8'))
    write_app(plan, Path(args.skill_dir), Path(args.output))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
