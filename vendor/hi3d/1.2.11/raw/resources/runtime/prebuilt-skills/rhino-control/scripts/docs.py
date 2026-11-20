#!/usr/bin/env python3
"""归档 McNeel 帮助索引主题，并检索或读取离线正文与保留缩进的代码。"""
import argparse
import concurrent.futures
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from html.parser import HTMLParser
from pathlib import Path


def archive_rows(archive):
    """Use the original index, or expose actual text members of source archives."""
    if 'index.json' in archive.namelist():
        return json.loads(archive.read('index.json'))
    source = json.loads(archive.read('source.json')) if 'source.json' in archive.namelist() else {}
    url = source.get('url', '') if isinstance(source, dict) else ''
    return [{'path': name, 'title': name, 'url': url} for name in sorted(archive.namelist())
            if Path(name).suffix.lower() in ('.md', '.txt', '.py', '.xml')]


def raw_text(archive, name):
    """Read an explicit archived text member without extracting or guessing paths."""
    if (Path(name).is_absolute() or '..' in Path(name).parts
            or Path(name).suffix.lower() not in ('.md', '.txt', '.py', '.xml')):
        raise ValueError('Expected a safe archived text member')
    value = archive.read(name).decode('utf-8-sig')
    if '\x00' in value:
        raise ValueError('Binary archive member is not documentation text')
    return value


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip += 1
        if tag in ('p', 'div', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'br', 'pre'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

    def value(self):
        return '\n'.join(x.strip() for x in ''.join(self.parts).splitlines() if x.strip())


class TopicMarkup(HTMLParser):
    """提取 HTML 跳转目标与 pre 代码块，保留代码缩进。"""
    def __init__(self):
        super().__init__()
        self.redirect = None
        self.depth = 0
        self.parts = []
        self.blocks = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta' and attrs.get('http-equiv', '').lower() == 'refresh':
            match = re.search(r'\burl\s*=\s*(.+)', attrs.get('content', ''), re.I)
            if match:
                self.redirect = match.group(1).strip().strip('\"\'')
        if tag == 'pre':
            if not self.depth:
                self.parts = []
            self.depth += 1
        if tag == 'br' and self.depth:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag == 'pre' and self.depth:
            self.depth -= 1
            if not self.depth:
                self.blocks.append(''.join(self.parts))

    def handle_data(self, data):
        if self.depth:
            self.parts.append(data)


def read_topic(archive, path):
    """仅解析归档内已索引的跳转；缺目标时失败，不把占位页当正文。"""
    rows = archive_rows(archive)
    if path in archive.namelist() and Path(path).suffix.lower() in ('.md', '.txt', '.py', '.xml'):
        return {'path': path, 'url': next((row['url'] for row in rows if row['path'] == path), ''),
                'redirect_chain': [path], 'text': raw_text(archive, path), 'code_blocks': []}
    paths = {row['path'].casefold(): row for row in rows}
    urls = {urllib.parse.unquote(row['url'].split('#')[0]).casefold(): row for row in rows}
    row = paths[path.split('#')[0].casefold()]
    visited = []
    for _ in range(32):
        if row['path'] in visited:
            raise ValueError('Documentation redirect cycle: ' + ' -> '.join(visited))
        visited.append(row['path'])
        markup = TopicMarkup()
        html_path = 'html/' + row['path']
        if html_path in archive.namelist():
            markup.feed(archive.read(html_path).decode('utf-8-sig', errors='replace'))
        if not markup.redirect:
            member = 'text/' + row['path'] + '.txt'
            if member not in archive.namelist():
                member = row['path']
            return {'path': row['path'], 'url': row['url'], 'redirect_chain': visited,
                    'text': raw_text(archive, member),
                    'code_blocks': markup.blocks}
        url = urllib.parse.urljoin(row['url'], markup.redirect).split('#')[0]
        target = urls.get(urllib.parse.unquote(url).casefold())
        if target is None:
            raise FileNotFoundError('Redirect target is not archived; consult its official URL: ' + url)
        row = target
    raise ValueError('Documentation redirect depth exceeds 32')


def fetch(url):
    url = urllib.parse.quote(url, safe=':/%?=&+#')
    request = urllib.request.Request(url, headers={'User-Agent': 'RhinoDocumentationArchive/1.0'})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
        except (TimeoutError, urllib.error.URLError):
            if attempt == 2:
                raise
        time.sleep(1 + attempt)


def indexed_topics(base):
    """枚举官方 SearchUrl 分块中的全部帮助主题，超出边界时显式失败。"""
    metadata = {}
    urls = set()
    for i in range(30):
        name = 'Data/SearchUrl_Chunk%d.js' % i
        try:
            body = fetch(base + name)
        except urllib.error.HTTPError as exc:
            if i > 0 and exc.code in (403, 404):
                break
            raise
        metadata[name] = body
        raw = body.decode('utf-8-sig').strip()
        # 旧版 MadCap 索引对象可能带尾逗号，解析前按该格式处理。
        payload = raw[len('define('):].rstrip(';')[:-1]
        entries = json.loads(re.sub(r',\s*}', '}', payload))
        for rel in entries:
            url = urllib.parse.urljoin(base + 'Data/', rel).split('#')[0]
            if url.startswith(base):
                urls.add(url)
    else:
        raise ValueError('Search index exceeds bound; inspect chunk format')
    return sorted(urls), metadata


def mirror(base, destination, workers=8, allow_missing=False):
    """复用下载缓存；只有显式允许缺页时才发布带缺项清单的归档。"""
    if not base.startswith('https://docs.mcneel.com/rhino/') or not base.endswith('/'):
        raise ValueError('Expected an official Rhino help base URL ending in /')
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    cache = destination.with_suffix('.cache')
    cache.mkdir(exist_ok=True)
    urls, metadata = indexed_topics(base)
    print(json.dumps({'base': base, 'indexed_topics': len(urls)}), flush=True)

    def one(url):
        rel = urllib.parse.unquote(url[len(base):])
        target = cache / rel
        if Path(rel).is_absolute() or '..' in Path(rel).parts:
            raise ValueError('Unexpected topic path')
        if not target.exists():
            data = fetch(url)
            if b'<html' not in data.lower():
                raise ValueError('Not HTML: ' + url)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        return rel, url, target

    rows = []
    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = {pool.submit(one, u): u for u in urls}
        for future in concurrent.futures.as_completed(jobs):
            try:
                rows.append(future.result())
            except Exception as exc:
                failures.append({'url': jobs[future], 'error': str(exc)})
            if (len(rows) + len(failures)) % 100 == 0:
                print(json.dumps({'base': base, 'downloaded': len(rows), 'failed': len(failures)}), flush=True)
    if failures:
        destination.with_suffix('.errors.json').write_text(json.dumps(failures, indent=2))
        if not allow_missing:
            raise RuntimeError('%d missing topics; cache retained for explicit resume' % len(failures))
    index = []
    temporary = destination.with_suffix('.partial.zip')
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for rel, url, target in sorted(rows):
            data = target.read_bytes()
            html = data.decode('utf-8-sig', errors='replace')
            parser = Text()
            parser.feed(html)
            title = re.search(r'<title>(.*?)</title>', html, re.S | re.I)
            archive.writestr('html/' + rel, data)
            archive.writestr('text/' + rel + '.txt', parser.value())
            index.append({'path': rel, 'url': url, 'title': title.group(1) if title else rel})
        for name, data in metadata.items():
            archive.writestr(name, data)
        archive.writestr('index.json', json.dumps(index, ensure_ascii=False, indent=2))
        archive.writestr('missing.json', json.dumps(failures, ensure_ascii=False, indent=2))
    temporary.replace(destination)
    summary = {'base_url': base, 'topics': len(rows), 'indexed_topics': len(urls),
               'missing_topics': len(failures), 'archive': destination.name,
               'complete_index_coverage': not failures,
               'scope': 'Available search-indexed HTML topics and extracted full text; media remain upstream links.'}
    destination.with_suffix('.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('mirror')
    p.add_argument('--base', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--workers', type=int, default=8, choices=range(1, 17))
    p.add_argument('--allow-missing', action='store_true', help='Publish available pages with explicit missing.json')
    p = sub.add_parser('search')
    p.add_argument('archive')
    p.add_argument('query')
    p.add_argument('--limit', type=int, default=20)
    p.add_argument('--full-text', action='store_true')
    p = sub.add_parser('read')
    p.add_argument('archive')
    p.add_argument('path')
    p.add_argument('--code-blocks', action='store_true', help='以 JSON 返回原 HTML pre 代码块，保留缩进')
    p.add_argument('--start-line', type=int, help='正文 1 起点行号；与 --end-line 同用')
    p.add_argument('--end-line', type=int, help='正文结束行，包含该行')
    p = sub.add_parser('lookup', help='按 Rhino 版本检索二级接口索引，不加载正文')
    p.add_argument('--major', type=int, required=True, choices=(5, 6, 7, 8))
    p.add_argument('--query', action='append', help='可重复，批量查询多个接口；省略则列目录')
    p.add_argument('--kind', choices=('rs', 'rc', 'mcp', 'guide'))
    p.add_argument('--limit', type=int, default=12)
    p.add_argument('--sources', action='store_true', help='需要回查实现时附原归档路径和行号')
    p.add_argument('--format', choices=('json', 'text'), default='json', help='text 为精简行目录；默认保留 JSON 接口')
    p.add_argument('--rs-variant', help='仅筛选本版 Python 分支，不影响 rc/guide/mcp')
    p.add_argument('--rc-variant', help='仅筛选本版 RhinoCommon 框架，不影响 rs/guide/mcp')
    p = sub.add_parser('section', help='按精确 ID 读取索引行段，可批量 --id')
    p.add_argument('--major', type=int, required=True, choices=(5, 6, 7, 8))
    p.add_argument('--id', action='append', required=True)
    p.add_argument('--variant', help='查到不同契约时明确选择分支/框架，不默认最新版本')
    p.add_argument('--with-notes', action='store_true', help='同时读取本版索引中与精确 API ID 关联的注意事项，共用段仅输出一次')
    p.add_argument('--rs-variant', help='选择本版 Python 分支，可与 rc/guide 混合批量读取')
    p.add_argument('--rc-variant', help='选择本版 RhinoCommon 框架，可与 rs/guide 混合批量读取')
    p = sub.add_parser('catalog-build', help='维护用：从随包资料生成新目录归档')
    p.add_argument('--output', required=True)
    sub.add_parser('catalog-check', help='维护用：完整重建比较，拒绝过期行号/契约')
    args = parser.parse_args()
    if args.action in ('lookup', 'section', 'catalog-build', 'catalog-check'):
        import catalog
        if args.action == 'lookup':
            queries = args.query or ['']
            try:
                with catalog.Catalog(args.major, rs_variant=args.rs_variant, rc_variant=args.rc_variant) as reader:
                    results = [reader.lookup(query, args.kind, args.limit, sources=args.sources)
                               for query in queries]
            except ValueError as error:
                parser.exit(1, 'error: %s\n' % error)
            value = results[0] if len(results) == 1 else [dict(result, query=query)
                     for query, result in zip(queries, results)]
            if args.format == 'json':
                print(json.dumps(value, ensure_ascii=False, indent=2))
            else:
                for query, result in zip(queries, results):
                    print('Rhino %d | query=%s | total=%d | truncated=%s' % (
                        args.major, json.dumps(query, ensure_ascii=False), result['total'],
                        str(result['truncated']).lower()))
                    for row in result['matches']:
                        print('%s | %s:%d-%d | %s | %s' % (row['id'], row['path'],
                            row['start'], row['end'], ','.join(row['variants']), row['summary']))
                        for source in row.get('sources', []):
                            print('  %s | %s:%d-%d' % (source['variant'], source['source'],
                                source['source_start'], source['source_end']))
        elif args.action == 'section':
            # Resolve the whole batch first: no partial successful answer before
            # an ambiguous version or missing contract is reported.
            try:
                with catalog.Catalog(args.major, rs_variant=args.rs_variant, rc_variant=args.rc_variant) as reader:
                    sections = reader.sections(args.id, args.variant, args.with_notes)
            except ValueError as error:
                parser.exit(1, 'error: %s\n' % error)
            for result in sections:
                print('%s:%d-%d [%s]\n%s\n' % (result['path'], result['start'], result['end'],
                      ', '.join(result['variants']), result['text']))
        elif args.action == 'catalog-build':
            catalog.write_catalog(catalog.build(), args.output)
            print(json.dumps({'output': str(Path(args.output).resolve())}))
        else:
            print(json.dumps(catalog.check()))
        return
    if args.action == 'mirror':
        print(json.dumps(mirror(args.base, args.output, args.workers, args.allow_missing), indent=2))
    else:
        with zipfile.ZipFile(args.archive) as archive:
            if args.action == 'read':
                topic = read_topic(archive, args.path)
                if args.start_line is not None or args.end_line is not None:
                    lines = topic['text'].splitlines()
                    if (args.code_blocks or args.start_line is None or args.end_line is None
                            or not 1 <= args.start_line <= args.end_line <= len(lines)):
                        parser.error('Use both valid inclusive line bounds; cannot combine with --code-blocks')
                    print('\n'.join(lines[args.start_line - 1:args.end_line]))
                    return
                if args.code_blocks:
                    print(json.dumps({key: value for key, value in topic.items() if key != 'text'},
                                     ensure_ascii=False, indent=2))
                else:
                    print(topic['text'])
            else:
                rows = archive_rows(archive)
                q = args.query.casefold()
                selected = []
                for row in rows:
                    haystack = row.get('title', '') + ' ' + row['path']
                    if args.full_text:
                        member = 'text/' + row['path'] + '.txt'
                        if member not in archive.namelist():
                            member = row['path']
                        haystack += raw_text(archive, member)
                    if q in haystack.casefold():
                        selected.append(row)
                    if len(selected) >= args.limit:
                        break
                print(json.dumps(selected[:args.limit], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
