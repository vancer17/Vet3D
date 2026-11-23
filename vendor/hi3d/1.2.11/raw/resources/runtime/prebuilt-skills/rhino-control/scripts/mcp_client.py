#!/usr/bin/env python3
"""通过官方 MCP SDK 的 stdio 调用 RhinoMCP，保留调用进度且不自动重放修改。"""
import argparse
import asyncio
import json
import shutil
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def decoded(result):
    value = result.model_dump(mode='json', by_alias=True, exclude_none=True)
    if value.get('isError') or value.get('is_error'):
        raise RuntimeError(json.dumps(value, ensure_ascii=False))
    # MCP 信封成功不代表业务成功，仍须检查工具返回的 success/status。
    bodies = []
    structured = value.get('structuredContent')
    if isinstance(structured, dict):
        bodies.append(structured.get('result', structured))
    for block in value.get('content', []):
        if block.get('type') == 'text':
            try:
                inner = json.loads(block['text'])
            except (ValueError, KeyError):
                continue
            bodies.append(inner)
    for inner in bodies:
        if isinstance(inner, dict) and (inner.get('success') is False or inner.get('status') == 'error'):
            raise RuntimeError(json.dumps(inner, ensure_ascii=False))
    return value


def error_messages(exc):
    """展开 SDK 异步任务组异常，保留实际叶节点错误。"""
    children = getattr(exc, 'exceptions', None)
    if children:
        return [message for child in children for message in error_messages(child)]
    return [type(exc).__name__ + ': ' + str(exc)]


async def request(server, calls, timeout=60, progress=None):
    params = StdioServerParameters(command=server, args=[], env={
        'RHINO_MCP_HOST': '127.0.0.1', 'RHINO_MCP_TIMEOUT': str(timeout),
    })
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=timeout + 10) as session:
            initialized = await session.initialize()
            catalog = await session.list_tools()
            if calls is None:
                return {'server': initialized.server_info.model_dump(mode='json'),
                        'tools': catalog.model_dump(mode='json', by_alias=True)}
            names = {tool.name for tool in catalog.tools}
            results = []
            for call in calls:
                if not isinstance(call, dict) or not isinstance(call.get('name'), str):
                    raise ValueError('Each call requires a string name')
                if not isinstance(call.get('arguments', {}), dict):
                    raise ValueError('Arguments must be an object')
                if call['name'] not in names:
                    raise ValueError('Tool is not advertised: ' + call['name'])
            for call in calls:
                if progress:
                    progress('calling', results, call['name'])
                result = await session.call_tool(call['name'], call.get('arguments', {}))
                results.append({'name': call['name'], 'result': result.model_dump(
                    mode='json', by_alias=True, exclude_none=True)})
                if progress:
                    progress('received', results, None)
                decoded(result)
            return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', default=shutil.which('rhinomcp'))
    parser.add_argument('--request', help='JSON 调用列表 {name,arguments}；省略时读取 tools/list')
    parser.add_argument('--output', required=True, help='包外的新结果 JSON 路径；拒绝覆盖')
    parser.add_argument('--timeout', type=float, default=60)
    args = parser.parse_args()
    if not 0 < args.timeout <= 600:
        parser.error('Timeout must be greater than zero and at most 600 seconds')
    if not args.server:
        parser.error('rhinomcp is not installed or not on PATH')
    output = Path(args.output).expanduser().resolve()
    if output.exists():
        parser.error('Output already exists; inspect it before deciding to call again')
    package = Path(__file__).resolve().parents[1]
    if output == package or package in output.parents:
        parser.error('Results must be outside the installed skill')
    calls = json.loads(Path(args.request).read_text()) if args.request else None
    if calls is not None and (not isinstance(calls, list) or not calls):
        parser.error('Request must be a nonempty list')
    output.parent.mkdir(parents=True, exist_ok=True)
    # 发出请求前排他创建结果文件；中断后同一路径不能静默重发。
    with output.open('x') as stream:
        json.dump({'state': 'started', 'retry': False}, stream)

    def progress(state, results, active):
        output.write_text(json.dumps({'state': state, 'data': results, 'active_call': active,
                                      'retry': False}, ensure_ascii=False, indent=2))

    try:
        value = asyncio.run(request(args.server, calls, args.timeout, progress))
    except BaseException as exc:
        prior = json.loads(output.read_text())
        prior.update({'state': 'interrupted_or_failed', 'retry': False,
                      'error': error_messages(exc), 'type': type(exc).__name__})
        output.write_text(json.dumps(prior, ensure_ascii=False, indent=2))
        raise
    output.write_text(json.dumps({'state': 'completed', 'data': value}, ensure_ascii=False, indent=2))
    print(json.dumps({'state': 'completed', 'output': str(output)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
