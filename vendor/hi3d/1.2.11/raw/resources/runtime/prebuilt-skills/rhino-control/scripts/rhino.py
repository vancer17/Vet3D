#!/usr/bin/env python3
"""rhino-control：探测 Rhino 5–8、安装 RhinoMCP，并生成原生 Python 脚本与执行宏。"""
import argparse
import json
import os
import platform
import plistlib
import re
import shutil
import subprocess
from pathlib import Path

MCP_VERSION = '0.4.1.1'


def python_command(major, engine='ironpython'):
    if major not in (5, 6, 7, 8) or engine not in ('ironpython', 'cpython'):
        raise ValueError('Unsupported version or Python engine')
    if engine == 'cpython':
        if major != 8:
            raise ValueError('CPython ScriptEditor requires Rhino 8')
        return '_-ScriptEditor _Run'
    return '_-RunPythonScript'


def installation(path):
    path = Path(path).expanduser().resolve()
    if path.suffix.lower() == '.app':
        with (path / 'Contents/Info.plist').open('rb') as stream:
            info = plistlib.load(stream)
        identifier = str(info.get('CFBundleIdentifier', '')).lower()
        if not identifier.startswith('com.mcneel.') or 'rhino' not in identifier:
            raise ValueError('Expected a McNeel Rhino application bundle')
        name = info.get('CFBundleExecutable', '')
        if not isinstance(name, str) or not name or any(c in name for c in ('/', '\\')) or name in ('.', '..'):
            raise ValueError('Invalid CFBundleExecutable')
        executable = path / 'Contents/MacOS' / name
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise ValueError('Rhino bundle has no executable application')
        version = info.get('CFBundleShortVersionString', '')
        full = info.get('CFBundleVersion', version)
        yak = path / 'Contents/Resources/bin/yak'
        system = 'Darwin'
    elif path.is_file() and path.name.lower() == 'rhino.exe':
        executable = path
        # 读取指定可执行文件的版本；安装目录名不能证明实际版本。
        script = '& { param([string]$p) (Get-Item -LiteralPath $p).VersionInfo.FileVersion }'
        result = subprocess.run(['powershell', '-NoProfile', '-Command', script, str(path)],
                                check=True, capture_output=True, text=True, timeout=15)
        version = result.stdout.strip()
        full = version
        yak = path.with_name('Yak.exe')
        system = 'Windows'
    else:
        raise ValueError('Expected a Rhino .app bundle or Rhino.exe')
    if not isinstance(version, str):
        raise ValueError('Invalid Rhino version metadata')
    match = re.match(r'([5-8])(?:\.|,|$)', version)
    if not match:
        raise ValueError('Only verified Rhino 5–8 installations are accepted: ' + version)
    major = int(match.group(1))
    return {'path': str(path), 'platform': system, 'major': major, 'version': version,
            'executable': str(executable),
            'build': full, 'evidence': 'installed_file_metadata',
            'yak': str(yak) if yak.exists() else None,
            'preferred_transport': 'mcp' if major == 8 else 'python',
            'python_entries': [{'engine': engine, 'command': python_command(major, engine),
                                'evidence': 'documented_command', 'runtime_verified': False}
                               for engine in (('ironpython', 'cpython') if major == 8 else ('ironpython',))],
            'bundled_mcp_supported': major == 8,
            'runtime_version_verified': False}


def search_installations(root, max_depth=6, max_entries=20000):
    """仅在给定目录内有界查找安装；不跟随子链接、不启动找到的程序。"""
    root = Path(root).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(root)
    if not 0 <= max_depth <= 20 or not 1 <= max_entries <= 100000:
        raise ValueError('Search limits: max_depth 0..20, max_entries 1..100000')
    found, errors = [], []
    pending = [(root, 0)]
    scanned, truncated = 0, False
    while pending:
        path, depth = pending.pop()
        if path.suffix.lower() == '.app' or path.name.lower() == 'rhino.exe':
            try:
                found.append(installation(path))
            except (OSError, ValueError, plistlib.InvalidFileException, subprocess.SubprocessError) as exc:
                errors.append({'path': str(path), 'error': type(exc).__name__})
            continue  # 应用包不是搜索根中的普通目录，不进入其他应用内部。
        if not path.is_dir():
            continue
        if depth >= max_depth or scanned >= max_entries:
            truncated = True
            continue
        try:
            with os.scandir(path) as entries:
                for entry in entries:
                    if scanned >= max_entries:
                        truncated = True
                        break
                    scanned += 1
                    if entry.name.startswith('.') or entry.is_symlink():
                        continue
                    # 常用包名含 Rhino/Rhinoceros；改名的应用可直接作为 root/app 指定。
                    if entry.name.lower().endswith('.app') and 'rhino' not in entry.name.lower():
                        continue
                    if entry.is_dir(follow_symlinks=False) or entry.name.lower() == 'rhino.exe':
                        pending.append((Path(entry.path), depth + 1))
        except OSError as exc:
            errors.append({'path': str(path), 'error': type(exc).__name__})
    return {'root': str(root), 'installations': sorted(found, key=lambda x: (-x['major'], x['path'])),
            'scanned_entries': scanned, 'max_depth': max_depth, 'max_entries': max_entries,
            'truncated': truncated, 'errors': errors}


def discover():
    paths = []
    if platform.system() == 'Darwin':
        for root in (Path('/Applications'), Path.home() / 'Applications'):
            paths.extend(root.glob('*Rhino*.app'))
            paths.extend(root.glob('*Rhinoceros*.app'))
    elif platform.system() == 'Windows':
        import winreg
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            for major in range(5, 9):
                key = r'SOFTWARE\McNeel\Rhinoceros\%d.0\Install' % major
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key, 0,
                                        winreg.KEY_READ | view) as handle:
                        base = Path(winreg.QueryValueEx(handle, 'Path')[0])
                    paths.append(base / 'Rhino.exe')
                except OSError:
                    pass
        for root in ('C:/Program Files', 'C:/Program Files (x86)'):
            for major in range(5, 9):
                paths.append(Path(root) / ('Rhino %d' % major) / 'System/Rhino.exe')
                paths.append(Path(root) / ('Rhinoceros %d.0 (64-bit)' % major) / 'System/Rhino.exe')
    found = []
    for path in sorted(set(paths)):
        if path.exists():
            try:
                found.append(installation(path))
            except (OSError, ValueError, plistlib.InvalidFileException, subprocess.SubprocessError):
                pass
    return sorted(found, key=lambda item: item['major'], reverse=True)


def choose_transport(major, mcp_runtime_major=None, python_verified=False):
    if major not in (5, 6, 7, 8):
        raise ValueError('Unsupported Rhino major')
    if mcp_runtime_major == major:
        return 'mcp'
    if python_verified:
        return 'python'
    return 'computer_use'


def install_mcp(app, version=MCP_VERSION):
    info = installation(app)
    if info['major'] != 8 or not info['yak']:
        raise ValueError('The supplied RhinoMCP plugin supports Rhino 8 only; use Python')
    if not re.fullmatch(r'\d+(?:\.\d+){2,3}', version):
        raise ValueError('Use an explicit released numeric version')
    uv = shutil.which('uv')
    if not uv:
        raise RuntimeError('uv is required; install from https://docs.astral.sh/uv/getting-started/installation/')
    # Yak 安装 Rhino 插件，uv 安装同版本的 MCP 服务；两端均成功才返回完成。
    subprocess.run([info['yak'], 'install', 'rhinomcp', version], check=True, timeout=180)
    subprocess.run([uv, 'tool', 'install', '--python', '3.11', 'rhinomcp==' + version],
                   check=True, timeout=300)
    bin_dir = subprocess.run([uv, 'tool', 'dir', '--bin'], check=True, capture_output=True,
                             text=True, timeout=15).stdout.strip()
    return {'installed': True, 'version': version, 'next': 'Save open work, restart Rhino, run mcpstart',
            'server_command': [str(Path(bin_dir) / ('rhinomcp.exe' if os.name == 'nt' else 'rhinomcp'))],
            'environment': {'RHINO_MCP_HOST': '127.0.0.1'}}


def python_macro(script, major, engine='ironpython'):
    command = python_command(major, engine)
    path = Path(script).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    if any(c in str(path) for c in ('"', '\n', '\r')):
        raise ValueError('Path cannot be represented safely in a Rhino command macro')
    return command + ' "' + str(path) + '"'


def prepare(kind, script, output, major, engine='ironpython'):
    if kind not in ('probe', 'smoke20') or major not in (5, 6, 7, 8):
        raise ValueError('Unsupported preparation kind or Rhino major')
    if engine not in ('ironpython', 'cpython') or (engine == 'cpython' and major != 8):
        raise ValueError('CPython preparation requires Rhino 8; otherwise use ironpython')
    script = Path(script).expanduser().resolve()
    output = Path(output).expanduser().resolve()
    package = Path(__file__).resolve().parents[1]
    if package in script.parents or package in output.parents:
        raise ValueError('Generated scripts and evidence must be outside the skill')
    if script.exists() or output.exists() or script == output:
        raise ValueError('Use new script/output paths')
    source = Path(__file__).with_name('probe.py' if kind == 'probe' else 'smoke20.py').read_text(encoding='utf-8')
    # 在 future import 后内联共享探针，使生成文件不依赖包路径或 Rhino 导入缓存。
    marker = 'from runtime_compat import runtime_info\n'
    if source.count(marker) != 1:
        raise ValueError('Expected one runtime compatibility import')
    helper = Path(__file__).with_name('runtime_compat.py').read_text(encoding='utf-8')
    source = source.replace(marker, helper + '\n')
    if engine == 'cpython':
        source = '#! python 3\n' + source
    # ASCII JSON 转义配合 u 前缀，兼容 Python 2.7/3 的非 ASCII 路径。
    target = 'u' + json.dumps(str(output), ensure_ascii=True)
    implementation = 'CPython' if engine == 'cpython' else 'IronPython'
    ending = '\nif runtime_info()["implementation"] != %r:\n    raise RuntimeError("Wrong Python engine; use the generated macro")\n' % implementation
    ending += '\nrun(%s%s)\n' % (target, ', compatibility_target=%d' % major if kind == 'smoke20' else '')
    script.parent.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    with script.open('x', encoding='utf-8') as stream:
        stream.write(source + ending)
    return {'script': str(script), 'output': str(output), 'compatibility_target': major,
            'engine': engine, 'macro': python_macro(script, major, engine)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('detect', help='定位安装、应用程序与待验证的 Python 命令入口')
    target = p.add_mutually_exclusive_group()
    target.add_argument('--app', help='明确的 Rhino .app 或 Rhino.exe')
    target.add_argument('--root', help='只在此文件夹下有界搜索，不跟随子目录符号链接')
    p.add_argument('--max-depth', type=int, default=6)
    p.add_argument('--max-entries', type=int, default=20000)
    p = sub.add_parser('install-mcp')
    p.add_argument('--app', required=True)
    p.add_argument('--version', default=MCP_VERSION)
    p = sub.add_parser('macro')
    p.add_argument('--script', required=True)
    p.add_argument('--major', type=int, choices=range(5, 9), required=True)
    p.add_argument('--engine', choices=('ironpython', 'cpython'), default='ironpython')
    p = sub.add_parser('prepare')
    p.add_argument('--kind', choices=('probe', 'smoke20'), required=True)
    p.add_argument('--script', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--major', type=int, choices=range(5, 9), required=True)
    p.add_argument('--engine', choices=('ironpython', 'cpython'), default='ironpython')
    args = parser.parse_args()
    if args.action == 'detect':
        if args.root:
            result = search_installations(args.root, args.max_depth, args.max_entries)
        else:
            result = [installation(args.app)] if args.app else discover()
    elif args.action == 'install-mcp':
        result = install_mcp(args.app, args.version)
    elif args.action == 'prepare':
        result = prepare(args.kind, args.script, args.output, args.major, args.engine)
    else:
        result = {'macro': python_macro(args.script, args.major, args.engine)}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
