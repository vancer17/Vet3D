"""Write a local product configurator page into a new directory."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

CSS = """
:root { font-family: sans-serif; color: #111; }
body { margin: 0; }
body.style-simple main { max-width: 880px; margin: 0 auto; padding: 1rem; }
body.style-product main { display: grid; grid-template-columns: 1.2fr .8fr; gap: 1rem; padding: 1rem; }
body.style-fullscreen model-viewer { width: 100vw; height: 100vh; }
body.style-fullscreen #controls { position: fixed; right: 0; top: 0; width: min(320px, 90vw); background: #fff; padding: 1rem; max-height: 100vh; overflow: auto; }
model-viewer { width: 100%; height: 420px; background: #eee; }
.notice { background: #f4f4f4; padding: .75rem; }
.error { color: #a40000; }
fieldset button { width: 2rem; height: 2rem; border: 1px solid #333; margin-right: .25rem; }
"""


def write_page(plan, skill_dir: Path, model: Path, output: Path):
    if output.exists():
        raise ValueError('output must be a new directory')
    if not model.is_file():
        raise ValueError('model file required')
    output.mkdir(parents=True)
    dest_model = output / Path(plan.get('modelFile') or 'model.glb').name
    shutil.copy2(model, dest_model)
    copied = [dest_model.name]
    root = model.parent.resolve()
    for uri in plan.get('externalTextures') or []:
        if Path(uri).is_absolute() or '..' in Path(uri).parts:
            raise ValueError('texture uri must be a relative file next to the model')
        src = (root / uri).resolve()
        if not src.is_file() or root not in src.parents and src.parent != root:
            raise ValueError('texture must be a real file next to the model: ' + uri)
        target = output / Path(uri).name
        shutil.copy2(src, target)
        copied.append(target.name)
    plan_json = json.dumps(plan, ensure_ascii=False)
    (output / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (output / 'app.css').write_text(CSS, encoding='utf-8')
    unimplemented = ''.join(f'<li>{item}：未实现</li>' for item in plan.get('unimplemented') or [])
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{plan['title']}</title>
<link rel="stylesheet" href="app.css">
<script type="module" src="https://cdn.jsdelivr.net/npm/@google/model-viewer@4.0.0/dist/model-viewer.min.js"></script>
</head>
<body class="style-{plan['style']}">
<main>
  <model-viewer src="{dest_model.name}" camera-controls alt="{plan['title']}"></model-viewer>
  <p data-load-status></p>
  <noscript><aside class="notice" role="note"><p>{plan.get('note','')}</p><ul>{unimplemented}</ul></aside></noscript>
  <div id="controls"></div>
</main>
<script>window.APP_PLAN = {plan_json};</script>
<script type="module" src="viewer.js"></script>
</body>
</html>
"""
    (output / 'index.html').write_text(html, encoding='utf-8')
    shutil.copy2(skill_dir / 'scripts' / 'viewer.js', output / 'viewer.js')
    shutil.copy2(skill_dir / 'scripts' / 'rules.mjs', output / 'rules.mjs')
    core = skill_dir / 'scripts' / 'hi3d-core.mjs'
    if not core.is_file():
        raise FileNotFoundError('hi3d-core.mjs missing; materialize package.json first')
    shutil.copy2(core, output / 'hi3d-core.mjs')
    (output / 'README.txt').write_text(
        '用本地 HTTP 打开本目录。颜色切换只改变显示，不是物理材质验证。\n'
        '支付、库存、订单未实现。导入配置失败不覆盖现有存档。\n',
        encoding='utf-8',
    )
    (output / 'copied.json').write_text(json.dumps({'files': copied}, indent=2) + '\n', encoding='utf-8')
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description='Build product-configurator page')
    parser.add_argument('--plan', required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--skill-dir', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    plan = json.loads(Path(args.plan).read_text(encoding='utf-8'))
    write_page(plan, Path(args.skill_dir), Path(args.model), Path(args.output))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
