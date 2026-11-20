"""GET generated demo files over loopback HTTP."""
from __future__ import annotations

import argparse
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen


def serve(root: Path):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def check(root: Path):
    names = ['index.html', 'app.css', 'plan.json', 'runner.py', 'contract.py', 'serve_demo.py', 'API.txt']
    plan = json.loads((root / 'plan.json').read_text(encoding='utf-8'))
    names.append(plan['entry'])
    missing = [name for name in names if not (root / name).is_file()]
    if missing:
        raise ValueError('missing ' + ', '.join(missing))
    server = serve(root)
    host, port = server.server_address
    base = f'http://{host}:{port}'
    report = {'base': base, 'ok': True, 'files': {}}
    try:
        for name in names:
            with urlopen(f'{base}/{name}', timeout=5) as response:
                body = response.read()
                report['files'][name] = {'status': response.status, 'bytes': len(body)}
                if response.status != 200 or not body:
                    report['ok'] = False
        html = (root / 'index.html').read_text(encoding='utf-8')
        if '/run' not in html:
            report['ok'] = False
            report['reason'] = 'test page must POST /run'
        if 'password' in html.lower() or 'HI3D_' in html:
            report['ok'] = False
            report['reason'] = 'panel must not ask for secrets'
        if '<button' in html and '部署' in html and '未实现' not in html:
            report['ok'] = False
            report['reason'] = 'must not present unimplemented deploy as buttons'
    finally:
        server.shutdown()
        server.server_close()
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description='HTTP-load api-demo-service files')
    parser.add_argument('--root', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    out = Path(args.output)
    if out.exists():
        raise SystemExit('output must be a new file')
    report = check(Path(args.root))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
