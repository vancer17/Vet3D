"""Local, dependency-free picture chooser. Preview only; never calls generation APIs.

start --output DIR [--port 0]   starts a loopback chooser; prints session URL
status --output DIR           reads submitted choices for the invoking agent
recommend --output DIR        reads a submission or returns full-workflow defaults
stop --output DIR             closes this chooser, preserving the brief
"""
import argparse
import json
import mimetypes
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, unquote
from urllib.request import Request, urlopen
from page_assets import read_asset

ASSETS = Path(__file__).resolve().parents[1] / 'assets' / 'experience'
SCENES = {'bedside': '床头氛围', 'desk': '书桌陪伴', 'accent': '客厅艺术摆件'}
GOALS = {'full': '完成全流程：设计图到数字制作包与展示网页',
         'concepts': '本次只出 3 张设计图', 'fdm': '本次只做 FDM 工程包',
         'lighting': '本次只迭代示例光效'}
COMPLEXITY = {'balanced': '层次丰富，轮廓清楚', 'rich': '更复杂的曲面与层次', 'quiet': '简洁克制'}

def write_json(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)

def brief_from_selection(data, catalog):
    styles = {x['id']: x for x in catalog['styles']}
    if not isinstance(data, dict):
        raise ValueError('请选择有效选项。')
    values = {}
    for key, allowed in [('style', styles), ('scene', SCENES), ('goal', GOALS), ('complexity', COMPLEXITY)]:
        value = data.get(key)
        if not isinstance(value, str) or value not in allowed:
            raise ValueError('请选择有效的 ' + key)
        values[key] = value
    notes = data.get('notes', '')
    if not isinstance(notes, str) or len(notes) > 1000:
        raise ValueError('补充说明请控制在 1000 字以内。')
    values['notes'] = notes.strip()
    style = styles[values['style']]
    defaults = {'height_mm': [250, 300], 'print_bed_mm': [256, 256, 256],
                'process': 'FDM', 'light_source': '低压成品 LED，具体器件待选',
                'material': '单色外壳；实际透光材料待试片', 'environment': '室内桌面'}
    prompt = (f"使用 $lamp-design。用途：{SCENES[values['scene']]}；"
              f"造型方向：{style['title']}（示例 {style['name']} {style['revision']}）；"
              f"复杂度：{COMPLEXITY[values['complexity']]}；这轮目标：{GOALS[values['goal']]}。"
              '采用室内桌灯、约 25–30 cm、256 mm FDM 平台和低压成品 LED 默认条件。'
              '优先有内腔、能隐藏和维护光源的外壳。')
    if values['goal'] == 'full':
        prompt += ('先创作 3 个有明确差异的原创概念，推荐一款并继续三维建模、内腔与装配结构、'
                   'FDM 分件和数字检查、同版 OFF/ON 图与 MP4、产品卡/BOM/装配打印说明、'
                   '展示网页及制作包，打开检查后交付。偏好选择约 60 秒未回复时采用推荐项并记录为助手默认，'
                   '不在概念图或其他中间阶段结束；用户明确限定范围或要求等待时尊重该要求。'
                   '未完成实物验证的部分如实标注，外部服务和发布按现有授权执行。')
    elif values['goal'] == 'concepts':
        prompt += '借鉴所选形态规律，创作 3 张有明确差异的原创概念图；这轮只做设计图。'
    elif values['goal'] == 'fdm':
        prompt += '本次仅完成 FDM 工程包：落实硬件尺寸、可打印分件、装配路径、制造文件和检查记录，未验证部分标注待定。'
    else:
        prompt += '本次仅迭代光效：保留示例原孔与可见凹面，核实模型来源，再改灯路和厚度，交付修订场景、开关灯图与视频及变更说明。'
    if values['notes']:
        prompt += '\n用户补充：' + values['notes']
    return {'schema_version': 2, 'selection_source': 'user', 'selection': values, 'labels': {'style': style['title'],
            'scene': SCENES[values['scene']], 'goal': GOALS[values['goal']],
            'complexity': COMPLEXITY[values['complexity']]}, 'defaults': defaults,
            'example': {'id': style['id'], 'name': style['name'], 'revision': style['revision'],
                        'asset_directory_relative_to_experience': 'media/' + style['id']},
            'prompt': prompt, 'generation_started': False,
            'example_preview_only': True, 'external_upload_authorized_by_this_selection': False}

def recommended_brief(catalog):
    brief = brief_from_selection({'style': catalog['default_style'], 'scene': 'bedside',
                                  'goal': 'full', 'complexity': 'balanced', 'notes': ''}, catalog)
    brief['selection_source'] = 'assistant_default'
    return brief

def read_catalog(assets):
    raw,_=read_asset(assets,'catalog.json')
    catalog=json.loads(raw)
    for style in catalog['styles']:
        for name in style['files']:
            read_asset(assets,'media/'+style['id']+'/'+name)
    return catalog

def serve(output, port, assets):
    catalog = read_catalog(assets)
    output.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(24)
    prefix = '/s/' + token + '/'
    lock = threading.Lock()
    server = None

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def allowed_host(self):
            return self.headers.get('Host') == '127.0.0.1:' + str(server.server_port)

        def send_json(self, data, code=200):
            raw = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if not self.allowed_host():
                return self.send_json({'error': 'Invalid host'}, 403)
            path = unquote(urlsplit(self.path).path)
            if not path.startswith(prefix):
                return self.send_json({'error': 'Session not found'}, 404)
            route = path[len(prefix):]
            if route == 'api/status':
                return self.send_json({'status': 'running', 'submitted': (output / 'selection.json').exists()})
            if route == 'api/selection':
                with lock:
                    data = json.loads((output / 'selection.json').read_text()) if (output / 'selection.json').exists() else None
                return self.send_json({'selection': data})
            if route == 'api/brief':
                return self.send_json(json.loads((output / 'selection.json').read_text())) if (output / 'selection.json').exists() else self.send_json({'error': '尚未提交'}, 404)
            target = (assets / (route or 'index.html')).resolve()
            if not target.is_relative_to(assets.resolve()) or not target.is_file():
                return self.send_json({'error': 'File not found'}, 404)
            total = target.stat().st_size
            start, end, code = 0, total - 1, 200
            range_header = self.headers.get('Range')
            if range_header:
                try:
                    if not range_header.startswith('bytes=') or ',' in range_header:
                        raise ValueError()
                    left, right = range_header[6:].split('-', 1)
                    if left:
                        start = int(left); end = min(int(right), total - 1) if right else total - 1
                    else:
                        start = max(0, total - int(right))
                    if not 0 <= start <= end < total:
                        raise ValueError()
                    code = 206
                except ValueError:
                    self.send_response(416); self.send_header('Content-Range', f'bytes */{total}'); self.end_headers(); return
            self.send_response(code)
            self.send_header('Content-Type', mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
            self.send_header('Content-Length', str(end - start + 1))
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; worker-src 'self' blob:; connect-src 'self'; media-src 'self' blob:; frame-ancestors 'self'")
            if code == 206:
                self.send_header('Content-Range', f'bytes {start}-{end}/{total}')
            self.end_headers()
            try:
                with target.open('rb') as f:
                    f.seek(start); remaining = end - start + 1
                    while remaining:
                        chunk = f.read(min(65536, remaining))
                        if not chunk: break
                        self.wfile.write(chunk); remaining -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_POST(self):
            if not self.allowed_host() or self.headers.get('X-Lamp-Session') != token:
                return self.send_json({'error': 'Invalid session'}, 403)
            origin = self.headers.get('Origin')
            if origin and origin != 'http://127.0.0.1:' + str(server.server_port):
                return self.send_json({'error': 'Invalid origin'}, 403)
            if self.path == prefix + 'api/stop':
                self.send_json({'stopped': True}); threading.Thread(target=server.shutdown, daemon=True).start(); return
            if self.path != prefix + 'api/selection':
                return self.send_json({'error': 'Not found'}, 404)
            try:
                length = int(self.headers.get('Content-Length', 0))
                if not 0 < length <= 8192: raise ValueError('请求过大或为空。')
                brief = brief_from_selection(json.loads(self.rfile.read(length)), catalog)
            except (ValueError, TypeError):
                return self.send_json({'error': '选项无效，请检查后重试。'}, 400)
            with lock:
                path = output / 'selection.json'
                old = json.loads(path.read_text()) if path.exists() else None
                # Duplicate submit retries are idempotent; changed choices increment revision.
                if old and old['selection'] == brief['selection']:
                    brief = old
                else:
                    brief['revision'] = old['revision'] + 1 if old else 1
                    brief['submitted_at'] = time.time()
                    write_json(path, brief)
                    (output / 'design-brief.md').write_text(brief['prompt'], encoding='utf-8')
            self.send_json({'saved': True, 'revision': brief['revision'], 'brief': brief})

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    write_json(output / 'session.json', {'url': f'http://127.0.0.1:{server.server_port}{prefix}',
                                       'pid': os.getpid(), 'token': token, 'output': str(output),
                                       'created_at': time.time()})
    server.serve_forever()
    server.server_close()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['start', 'serve', 'status', 'recommend', 'stop'])
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--port', type=int, default=0)
    a = p.parse_args(); out = a.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    info_path = out / 'session.json'
    if a.command == 'serve':
        return serve(out, a.port, ASSETS)
    info = json.loads(info_path.read_text()) if info_path.exists() else None
    if a.command in ('status', 'recommend'):
        brief = json.loads((out / 'selection.json').read_text()) if (out / 'selection.json').exists() else None
        submitted = brief is not None
        if a.command == 'recommend' and brief is None:
            brief = recommended_brief(read_catalog(ASSETS))
        print(json.dumps({'submitted': submitted, 'brief': brief}, ensure_ascii=False)); return
    if a.command == 'stop':
        if info:
            req = Request(info['url'] + 'api/stop', data=b'{}', headers={'X-Lamp-Session': info['token']}, method='POST')
            try:
                with urlopen(req, timeout=3) as response: response.read()
            except OSError: pass
        print(json.dumps({'stopped': True})); return
    if info:
        try:
            with urlopen(info['url'] + 'api/status', timeout=2) as response:
                if json.load(response)['status'] == 'running':
                    print(json.dumps({'url': info['url'], 'output': str(out), 'reused': True})); return
        except OSError: pass
    previous = info_path.stat().st_mtime_ns if info_path.exists() else 0
    with (out / 'server.log').open('ab') as log:
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'serve', '--output', str(out), '--port', str(a.port)],
                                 stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    for _ in range(100):
        if child.poll() is not None: raise RuntimeError('体验入口未能启动，请检查 server.log。')
        if info_path.exists() and info_path.stat().st_mtime_ns != previous:
            info = json.loads(info_path.read_text()); print(json.dumps({'url': info['url'], 'output': str(out), 'reused': False})); return
        time.sleep(.05)
    raise RuntimeError('体验入口启动超时。')

if __name__ == '__main__':
    main()
