"""Write a local single-algorithm demo service into a new directory."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

CSS = """
:root { font-family: sans-serif; color: #111; }
body { margin: 1rem auto; max-width: 640px; }
.notice { background: #f4f4f4; padding: .75rem; }
.error { color: #a40000; }
label { display: block; margin: .5rem 0; }
textarea, input { width: 100%; }
pre { background: #111; color: #eee; padding: 1rem; overflow: auto; }
"""


def write_demo(plan, skill_dir: Path, algorithm: Path, output: Path):
    if output.exists():
        raise ValueError('output must be a new directory')
    if not algorithm.is_file():
        raise ValueError('algorithm file required')
    output.mkdir(parents=True)
    dest = output / plan['entry']
    shutil.copy2(algorithm, dest)
    shutil.copy2(skill_dir / 'scripts' / 'runner.py', output / 'runner.py')
    shutil.copy2(skill_dir / 'scripts' / 'contract.py', output / 'contract.py')
    shutil.copy2(skill_dir / 'scripts' / 'serve_demo.py', output / 'serve_demo.py')
    (output / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (output / 'app.css').write_text(CSS, encoding='utf-8')
    unimplemented = ''.join(f'<li>{item}：未实现</li>' for item in plan.get('unimplemented') or [])
    fields = []
    for field in plan['fields']:
        if field['type'] == 'file':
            fields.append(f'<label>{field["label"]} <input name="{field["id"]}" type="file" data-file="1"></label>')
        elif field['type'] == 'boolean':
            fields.append(f'<label>{field["label"]} <select name="{field["id"]}"><option value="false">否</option><option value="true">是</option></select></label>')
        else:
            itype = 'number' if field['type'] == 'number' else 'text'
            fields.append(f'<label>{field["label"]} <input name="{field["id"]}" type="{itype}"></label>')
    title = plan['title']
    note = plan.get('note') or ''
    plan_json = json.dumps(plan, ensure_ascii=False)
    field_html = ''.join(fields)
    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="stylesheet" href="app.css">
</head>
<body>
<h1>__TITLE__</h1>
<p>__NOTE__</p>
<form id="demo">
__FIELDS__
<p><button type="submit">提交</button></p>
</form>
<p data-busy hidden>执行中，请勿重复提交</p>
<pre data-result></pre>
<div id="unimplemented"></div>
<noscript><aside class="notice" role="note"><ul>__UNIMPLEMENTED__</ul></aside></noscript>
<script>
const PLAN = __PLAN__;
const unimplemented = (PLAN.unimplemented || []).map((name) => '<li>' + name + '：未实现</li>').join('');
document.getElementById('unimplemented').innerHTML = '<aside class="notice" role="note"><p>以下能力未实现，页面不索取密钥：</p><ul>' + unimplemented + '</ul></aside>';
document.getElementById('demo').addEventListener('submit', async (event) => {
  event.preventDefault();
  const busy = document.querySelector('[data-busy]');
  const out = document.querySelector('[data-result]');
  const body = {};
  for (const field of PLAN.fields) {
    const input = event.currentTarget.elements[field.id];
    if (field.type === 'file') {
      const file = input.files && input.files[0];
      if (file) {
        const buf = new Uint8Array(await file.arrayBuffer());
        body[field.id] = { name: file.name, data: Array.from(buf) };
      }
    } else if (field.type === 'boolean') body[field.id] = input.value;
    else if (field.type === 'number') body[field.id] = input.value === '' ? '' : Number(input.value);
    else body[field.id] = input.value;
  }
  busy.hidden = false;
  out.textContent = '';
  try {
    const response = await fetch('/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = await response.json();
    if (data.jobId) {
      let job = data;
      while (job.status === 'running') {
        await new Promise((r) => setTimeout(r, 200));
        job = await (await fetch('/jobs/' + data.jobId)).json();
      }
      out.textContent = JSON.stringify(job, null, 2);
    } else out.textContent = JSON.stringify(data, null, 2);
  } catch (error) {
    out.textContent = String(error);
  } finally {
    busy.hidden = true;
  }
});
</script>
</body>
</html>
""".replace('__TITLE__', title).replace('__NOTE__', note).replace('__FIELDS__', field_html).replace('__UNIMPLEMENTED__', unimplemented).replace('__PLAN__', plan_json)
    (output / 'index.html').write_text(html, encoding='utf-8')
    (output / 'README.txt').write_text(
        '在本目录运行: python3 serve_demo.py --root .\n'
        '只封装这一个算法。不要把请求字段拼进命令行。面板不索取密钥。\n'
        '公开部署需另行授权。输入校验失败与算法失败是不同响应。\n',
        encoding='utf-8',
    )
    (output / 'API.txt').write_text(
        'POST /run application/json\n'
        'GET /jobs/<id>  （background 模式）\n'
        '校验失败 kind=validation；算法失败 kind=execution；超时 kind=timeout；忙碌 409 kind=busy\n',
        encoding='utf-8',
    )
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description='Build api-demo-service')
    parser.add_argument('--plan', required=True)
    parser.add_argument('--algorithm', required=True)
    parser.add_argument('--skill-dir', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    plan = json.loads(Path(args.plan).read_text(encoding='utf-8'))
    write_demo(plan, Path(args.skill_dir), Path(args.algorithm), Path(args.output))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
