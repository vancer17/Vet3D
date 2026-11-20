"""Generate and check the repository's evidence-based capability usage index.

Local maintenance only. Never import capability code or infer execution from links.
"""
import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import unquote

from bundle import CATEGORIES, IGNORED, LINK, credential_path, inventory, package_files, read_manifest, source_file
from pcg_architecture import ensure_missing
from pcg_check import check_repository

DECLARATIONS = 'doc/capability-usage-declarations.json'
DOCUMENT = 'doc/capability-usage.md'
KINDS = {
    'requires': '必需入口', 'code': '代码物化', 'resource': '资料物化',
    'link': '文档引用', 'call': '条件调用', 'contract': '契约使用',
    'handoff': '下游交接', 'indirect': '间接交接', 'context': '非调用说明',
}
MARKS = dict(zip(KINDS, ('Q', 'C', 'F', 'R', 'A', 'K', 'H', 'I', 'X')))


def named_entries(text, entries):
    """Find known full entry names; naming mentions alone do not prove usage."""
    return {name for name in entries
            if re.search(r'(?<![\w-])' + re.escape(name) + r'(?![\w-])', text)}


def collect(repo):
    """Return discovered entries and typed, source-backed edges; reject stale data."""
    repo = Path(repo).resolve()
    for category in CATEGORIES:
        directory = repo / category
        if not directory.is_dir() or directory.is_symlink():
            raise ValueError('Missing or invalid capability directory: ' + category)
        # inventory's */SKILL.md glob cannot discover incomplete or misplaced
        # entries. Reject them before rendering a misleadingly complete index.
        if (directory / 'SKILL.md').exists():
            raise ValueError('Entry must have its own direct child directory: ' + category + '/SKILL.md')
        for child in sorted(directory.iterdir()):
            if child.name in IGNORED or credential_path((child.name,)):
                continue
            if child.is_dir() and not (child / 'SKILL.md').is_file():
                raise ValueError('Capability directory missing SKILL.md: ' + child.relative_to(repo).as_posix())
    entries = inventory(repo)
    owners = {owner: name for name, owner in entries.items()}
    plans, entry_text = {}, {}
    for name, owner in entries.items():
        entry_text[name] = source_file(repo, owner + '/SKILL.md').read_text()
        frontmatter = entry_text[name].split('---', 2)
        match = re.search(r'^name:\s*[\"\']?([^\s\"\']+)', frontmatter[1], re.M) if len(frontmatter) == 3 else None
        if not match or match.group(1) != name:
            raise ValueError('Entry name mismatch: ' + owner)
        source_file(repo, owner + '/package.json')
        plans[name] = package_files(repo, owner)
        for destination in plans[name]:
            if Path(destination).name == 'SKILL.md' and destination != 'SKILL.md':
                raise ValueError('Nested entry is not independently discoverable: ' + owner + '/' + destination)
    # Map installed aliases back to their unique source, without materializing them.
    aliases = {owner + '/' + dest: src for name, owner in entries.items()
               for dest, src in plans[name].items()}
    edges = defaultdict(set)
    instruction_mentions = defaultdict(set)

    def add(consumer, provider, kind, evidence, detail=''):
        if consumer != provider:
            edges[(consumer, provider, kind)].add((evidence, detail))

    for name, owner in entries.items():
        manifest = read_manifest(repo, owner)
        for provider in manifest['requires']:
            if provider not in entries or provider == name:
                raise ValueError('Invalid required entry: ' + owner + ': ' + str(provider))
            add(name, provider, 'requires', owner + '/package.json', 'requires')
        materializations = list(manifest['files'].items())
        for profile, settings in manifest.get('profiles', {}).items():
            materializations.extend((profile + ':' + dest, src) for dest, src in settings.get('files', {}).items())
        for dest, src in materializations:
            provider = owners.get('/'.join(src.split('/')[:2]))
            if provider:
                kind = 'code' if Path(src).suffix in {'.py', '.js', '.mjs', '.ts', '.sh'} else 'resource'
                add(name, provider, kind, owner + '/package.json', dest + ' ← ' + src)
        # Only canonical instructions are scanned. Materialized docs are already F edges.
        for dest, src in plans[name].items():
            if src != owner + '/' + dest or not src.endswith('.md'):
                continue
            text = source_file(repo, src).read_text()
            instruction_mentions[name].update(named_entries(text, entries))
            for target in LINK.findall(text):
                if target.startswith(('#', '/', 'http:', 'https:', 'mailto:', 'app:', 'codex:')):
                    continue
                if ' ' in target:  # Same portable link subset as the existing bundler.
                    continue
                resolved = os.path.normpath(str(Path(src).parent / unquote(target.split('#')[0])))
                resolved = aliases.get(resolved, resolved)
                provider = owners.get('/'.join(resolved.split('/')[:2]))
                if provider:
                    source_file(repo, resolved + '/SKILL.md' if resolved in owners else resolved)
                    add(name, provider, 'link', src, target)

    data = json.loads(source_file(repo, DECLARATIONS).read_text())
    if data.get('schema') != 1 or not isinstance(data.get('relations'), list):
        raise ValueError('Invalid usage declarations schema')
    declared = set()
    for row in data['relations']:
        consumer, provider, kind = row['consumer'], row['provider'], row['kind']
        if consumer not in entries or provider not in entries or consumer == provider:
            raise ValueError('Unknown or self usage declaration: ' + str((consumer, provider)))
        if kind not in {'call', 'contract', 'handoff', 'indirect', 'context'}:
            raise ValueError('Invalid declared usage kind: ' + str(kind))
        key = (consumer, provider, kind)
        if key in declared:
            raise ValueError('Duplicate usage declaration: ' + str(key))
        declared.add(key)
        evidence, quote = row['evidence'], row['quote']
        if not evidence.startswith(entries[consumer] + '/') or not evidence.endswith('.md'):
            raise ValueError('Declaration evidence must be consumer-owned Markdown')
        if not isinstance(quote, str) or not quote or quote not in source_file(repo, evidence).read_text():
            raise ValueError('Stale declaration evidence: ' + str(key))
        if provider not in named_entries(quote, entries):
            raise ValueError('Evidence does not name its provider: ' + str(key))
        add(consumer, provider, kind, evidence, quote)

    # Prevent a newly added bare dependency name from escaping classification.
    covered = defaultdict(set)
    for consumer, provider, _ in edges:
        covered[consumer].add(provider)
    for name, mentions in instruction_mentions.items():
        missing = mentions - covered[name] - {name}
        if missing:
            raise ValueError('Unclassified entry mentions in ' + entries[name] + ': ' + ', '.join(sorted(missing)))
    return entries, dict(edges)


def cell(text):
    """Escape source text for a Markdown table without interpreting its markup."""
    return (text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('[', '&#91;').replace(']', '&#93;').replace('|', '&#124;').replace('\n', ' '))


def integration_status(entries, edges):
    """Classify static incoming use, without treating links as execution proof."""
    result = {}
    for provider, owner in sorted(entries.items()):
        if owner.split('/')[0] not in ('tools', 'skills'):
            continue
        users, executable, workflows = set(), set(), set()
        for consumer, target, kind in edges:
            if target != provider or kind == 'context' or entries[consumer].split('/')[0] not in ('skills', 'workflows'):
                continue
            users.add(consumer)
            if kind in ('code', 'requires', 'call'):
                executable.add(consumer)
            if entries[consumer].startswith('workflows/'):
                workflows.add(consumer)
        result[provider] = dict(users=sorted(users), executable=sorted(executable), workflows=sorted(workflows))
    return result


def render(entries, edges):
    """Render stable reverse tables for every tool/skill and all evidence edges."""
    def link(name):
        return '[' + name + '](../' + entries[name] + '/SKILL.md)'

    def consumers(provider, category):
        found = defaultdict(set)
        for consumer, target, kind in edges:
            if target == provider and entries[consumer].startswith(category + '/') and kind != 'context':
                found[consumer].add(MARKS[kind])
        return '；'.join(link(name) + ' (' + '/'.join(sorted(marks)) + ')'
                        for name, marks in sorted(found.items())) or '无已记录使用方'

    lines = [
        '# 能力使用关系', '',
        '<!-- Generated by tools/package-tools/scripts/usage.py; do not edit manually. -->', '',
        '由当前三层入口、`package.json`、包内 Markdown 链接和[显式交接声明](capability-usage-declarations.json)生成。'
        '维护要求见 [AGENTS](../AGENTS.md#能力使用关系必须同步维护)，生成/校验方法见 [package-tools](package-tools.md#使用关系索引)。', '',
        '本表记录静态的直接复用、条件调用、契约引用和交接，不代表某次实际运行。'
        '文件物化不等于调用整个入口，资料引用不等于执行依赖；已有中间产物允许跳过上游。'
        '只将明确写出的间接交接标为 I，不把资料链接或兼容层的包级环展开成必需调用链。'
        '“无已记录使用方”只表示当前仓库未记录，独立调用和仓库外使用无法由此统计。', '',
        '| 标记 | 含义 |', '| --- | --- |',
    ]
    for kind, label in KINDS.items():
        lines.append('| ' + MARKS[kind] + ' | ' + label + ' |')
    counts = {category: sum(owner.startswith(category + '/') for owner in entries.values()) for category in CATEGORIES}
    lines += ['', f"覆盖：{counts['tools']} tools、{counts['skills']} skills、{counts['workflows']} workflows。"
              '以下对每个 tool/skill 保留一行；workflow 的组合关系也在后面的证据表中。', '']
    for category in ('tools', 'skills'):
        lines += ['## ' + category + ' 的使用方', '',
                  '| 能力 | 使用它的 skills | 使用它的 workflows | 使用或交接它的 tools |',
                  '| --- | --- | --- | --- |']
        for name, owner in sorted(entries.items()):
            if owner.startswith(category + '/'):
                lines.append('| ' + link(name) + ' | ' + ' | '.join(consumers(name, c) for c in ('skills', 'workflows', 'tools')) + ' |')
        lines.append('')
    status = integration_status(entries, edges)
    def listed(names):
        return '、'.join(link(name) for name in names) or '无'
    lines += ['## 孤立与接入口径', '',
              '以下只统计 skills/workflows 作为使用方，排除 X 非调用说明和仅由 tools 发起的关系。'
              '“无使用记录”是待排查的静态孤立标记，不是删除能力的依据；独立或仓库外使用不在本表。', '',
              '- 无 skill/workflow 使用或交接记录：' + listed(n for n, r in status.items() if not r['users']) + '。',
              '- 只有资料、契约或交接记录，没有 C/Q/A：' + listed(n for n, r in status.items() if r['users'] and not r['executable']) + '。',
              '- 有 skill 使用或交接，但没有 workflow 直接记录：' + listed(n for n, r in status.items() if r['users'] and not r['workflows']) + '。', '',
              '第二类需阅读原文判断：规则型能力可通过契约执行，CLI 交接也可独立完成；不能仅因没有 Python import 判为孤立。'
              'C 只证明文件物化，A/Q 只证明声明调用，均不证明历史执行成功。确认正确接入仍需检查真实调用参数、依赖与相应验证；'
              '不为清空孤立列表强加无关业务调用。', '',
              '## 关系证据', '',
              '按使用方排序，列出全部三层入口，包含无出边的入口。Q/C/F 来源于物化清单；R 是资料引用；'
              'A/K/H/I/X 来源于人工核对的原文声明。反向表不计 X。每条关系保留来源文件与映射/引用目标；'
              '需要判断运行条件时读取来源正文，不能根据名称或标记推测。', '']
    for consumer in sorted(entries):
        lines += ['### ' + consumer, '', link(consumer), '']
        rows = [(key, value) for key, value in edges.items() if key[0] == consumer]
        if not rows:
            lines += ['无已记录出边。', '']
            continue
        lines += ['| 使用/引用目标 | 类型 | 来源与交接依据 |', '| --- | --- | --- |']
        for (_, provider, kind), evidence in sorted(rows):
            sources = defaultdict(list)
            for path, detail in sorted(evidence):
                sources[path].append(detail)
            evidence_text = '<br>'.join('[' + path + '](../' + path + ')：' + '<br>'.join(cell(x) for x in details)
                                      for path, details in sorted(sources.items()))
            lines.append('| ' + link(provider) + ' | ' + MARKS[kind] + ' ' + KINDS[kind] + ' | ' + evidence_text + ' |')
        lines.append('')
    return '\n'.join(lines)


def update(repo, write=False):
    """Check drift without writing, or regenerate the one fixed documentation path."""
    repo = Path(repo).resolve()
    entries, edges = collect(repo)
    expected = render(entries, edges)
    path = repo / DOCUMENT
    if path.exists() or path.is_symlink():
        source_file(repo, DOCUMENT)
    elif not path.parent.is_dir() or path.parent.is_symlink():
        raise ValueError('Documentation directory must be a regular local directory')
    seeded = []
    if write:
        seeded = ensure_missing(repo)
        path.write_text(expected)
    elif not path.is_file() or path.read_text() != expected:
        raise ValueError('Usage index is stale; run usage.py --repo <repository> --write and review the diff')
    pcg = check_repository(repo)
    result = {'entries': len(entries), 'relations': len(edges), 'document': DOCUMENT, 'pcg_entries': pcg['entries']}
    if seeded:
        result['seeded_architecture'] = seeded
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--write', action='store_true')
    args = parser.parse_args(argv)
    try:
        result = update(args.repo, write=args.write)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
