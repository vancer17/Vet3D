"""Materialize explicitly declared skill dependencies into a new standalone distribution.

Only local source files are read. No import, subprocess, credential or network access.
"""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile

CATEGORIES = ('tools', 'skills', 'workflows')
IGNORED = {'__pycache__', '.DS_Store', '.git', '.pytest_cache', '.secrets'}

def credential_path(parts):
    return any(p == '.env' or p.startswith('.env.') or p == 'credentials.json' or p == '.secrets' for p in parts)



def safe_relative(value):
    """Validate one portable relative file path, rejecting traversal and absolute paths."""
    p = PurePosixPath(value)
    if not isinstance(value, str) or not value or '\\' in value or p.is_absolute() or any(x in ('..', '.') for x in value.split('/')):
        raise ValueError('Unsafe package path: ' + str(value))
    return p


def source_file(repo, relative):
    """Resolve a regular, non-symlink repository file; reject every symlink component."""
    relative = safe_relative(relative)
    if credential_path(relative.parts):
        raise ValueError('Credential files are not package resources')
    path = repo.joinpath(*relative.parts)
    if any(p.is_symlink() for p in [path, *path.parents] if p != repo.parent):
        raise ValueError('Package sources cannot contain symlinks: ' + str(relative))
    path.resolve().relative_to(repo)
    if not path.is_file():
        raise FileNotFoundError(str(relative))
    return path


def inventory(repo):
    """Return global name → category/name, rejecting ambiguous discovery names."""
    entries = {}
    for category in CATEGORIES:
        for entry in sorted((repo / category).glob('*/SKILL.md')):
            name = entry.parent.name
            if name in entries:
                raise ValueError('Duplicate skill name: ' + name)
            entries[name] = entry.parent.relative_to(repo).as_posix()
    return entries


def read_manifest(repo, owner):
    """Read explicit materializations and runtime dependencies; unknown schemas fail."""
    path = repo / owner / 'package.json'
    data = json.loads(path.read_text()) if path.exists() else {'schema': 1, 'files': {}, 'requires': []}
    if data.get('schema') != 1 or not isinstance(data.get('files'), dict) or not isinstance(data.get('requires'), list):
        raise ValueError('Unsupported package manifest: ' + owner)
    mappings = [data['files']]
    for name, profile in data.get('profiles', {}).items():
        safe_relative(name)
        if not isinstance(profile, dict) or set(profile) - {'files', 'remove', 'archiveBase'} or not isinstance(profile.get('files', {}), dict) or not isinstance(profile.get('remove', []), list):
            raise ValueError('Invalid package profile: ' + owner)
        if type(profile.get('archiveBase', False)) is not bool:
            raise ValueError('archiveBase must be boolean: ' + owner)
        mappings.append(profile.get('files', {}))
        for dest in profile.get('remove', []):
            safe_relative(dest)
    for mapping in mappings:
        for dest, source in mapping.items():
            safe_relative(dest)
            if PurePosixPath(dest).name == 'SKILL.md' and dest != 'SKILL.md':
                raise ValueError('Nested entry: ' + owner)
            source_file(repo, source)
    return data


def package_files(repo, owner):
    """Return destination-relative → canonical source map; no shadowing local files."""
    result = {}
    for path in sorted((repo / owner).rglob('*')):
        relative = path.relative_to(repo / owner)
        if credential_path(relative.parts) or any(p in IGNORED for p in relative.parts) or path.suffix in ('.pyc', '.pyo'):
            continue
        if path.is_symlink():
            raise ValueError('Package contains a symlink: ' + str(path))
        if path.is_file():
            result[relative.as_posix()] = path.relative_to(repo).as_posix()
    for dest, source in read_manifest(repo, owner)['files'].items():
        if dest in result:
            raise ValueError('Dependency would shadow local file: ' + owner + '/' + dest)
        result[dest] = source
    return result


def dependency_order(repo, names):
    """Topologically expand explicit dependencies; cycles and unknown entries fail."""
    entries = inventory(repo)
    ordered, active, visited = [], set(), set()
    def visit(name):
        if name in active:
            raise ValueError('Dependency cycle at ' + name)
        if name in visited:
            return
        if name not in entries:
            raise ValueError('Unknown dependency: ' + name)
        active.add(name)
        owner = entries[name]
        manifest = read_manifest(repo, owner)
        # Materialized providers need not be installed as callable dependencies.
        # Only requires declares independently callable runtime skills.
        for dep in manifest['requires']:
            visit(dep)
        active.remove(name)
        visited.add(name)
        ordered.append(owner)
    for name in names:
        visit(name)
    return ordered


LINK = re.compile(r'(?<!!)\[[^\]\n]*\]\(([^)\n]+)\)')

def rewrite_links(text, source, destination, files):
    """Relocate local Markdown links in materialized docs, preferring local aliases."""
    reverse = {}
    for dest, src in files.items():
        reverse.setdefault(src, dest)
    def replace(match):
        target = match.group(1)
        if target.startswith(('#', '/', 'http:', 'https:', 'mailto:', 'app:', 'codex:')) or ' ' in target:
            return match.group(0)
        path, sep, fragment = target.partition('#')
        resolved = os.path.normpath(str(PurePosixPath(source).parent / path))
        actual = reverse.get(resolved, resolved)
        relative = os.path.relpath(actual, str(PurePosixPath(destination).parent))
        return match.group(0).replace('(' + target + ')', '(' + relative + (sep + fragment if sep else '') + ')')
    return LINK.sub(replace, text)


def optional_doc_links(text, destination, directory):
    """Keep optional source references legible without emitting broken installed links.

    Applied only to the repository documentation mirror, never runtime package
    instructions: a missing runtime dependency must remain a validation failure.
    """
    def replace(match):
        target = match.group(1)
        if target.startswith(('#', '/', 'http:', 'https:', 'mailto:', 'app:', 'codex:')) or ' ' in target:
            return match.group(0)
        relative = target.split('#')[0]
        resolved = os.path.normpath(str(PurePosixPath(destination).parent / relative))
        if (directory / resolved).exists():
            return match.group(0)
        label = match.group(0).split('](', 1)[0][1:]
        return label + '（源仓库 `' + resolved + '`，本次未打包）'
    return LINK.sub(replace, text)


def build(repo, names, output):
    """Write all selected entries and declared dependencies to a NEW output.

    Output must be outside the source repository. Existing output is never replaced.
    Canonical files remain unchanged; materialized copies are disposable build products.
    """
    repo, output = Path(repo).resolve(), Path(output).absolute()
    try:
        output.resolve().relative_to(repo)
    except ValueError:
        pass
    else:
        raise ValueError('Output must be outside the repository')
    if output.exists() or output.is_symlink():
        raise FileExistsError(str(output))
    order = dependency_order(repo, names)
    plans = {owner: package_files(repo, owner) for owner in order}
    # Include document-referenced providers, never turn backlinks into execution dependencies.
    queue = list(order)
    while queue:
        owner = queue.pop()
        for src in plans[owner].values():
            provider = '/'.join(PurePosixPath(src).parts[:2])
            if provider != owner and (repo / provider / 'SKILL.md').is_file() and provider not in plans:
                plans[provider] = package_files(repo, provider)
                queue.append(provider)
    # Local documentation links are a graph too; retain linked source entry resources.
    changed = True
    while changed:
        changed = False
        for owner, plan in list(plans.items()):
            for src in list(plan.values()):
                if not src.endswith('.md'):
                    continue
                for target in LINK.findall(source_file(repo, src).read_text()):
                    if target.startswith(('http:', 'https:', '/', '#', 'mailto:', 'app:', 'codex:')):
                        continue
                    target = os.path.normpath(str(PurePosixPath(src).parent / target.split('#')[0]))
                    parts = PurePosixPath(target).parts
                    if len(parts) > 2 and parts[0] in CATEGORIES:
                        provider = '/'.join(parts[:2])
                        if provider not in plans and (repo / provider / 'SKILL.md').is_file():
                            plans[provider] = package_files(repo, provider)
                            changed = True
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix='.skill-bundle-', dir=output.parent))
    try:
        for owner, plan in plans.items():
            filemap = {owner + '/' + dest: src for dest, src in plan.items()}
            for dest, src in plan.items():
                path = temp / owner / dest
                path.parent.mkdir(parents=True, exist_ok=True)
                original = source_file(repo, src)
                if path.suffix == '.md':
                    path.write_text(rewrite_links(original.read_text(), src, owner + '/' + dest, filemap))
                else:
                    shutil.copy2(original, path)
        # Maintenance docs are linked by legacy contracts and carry no runtime code.
        if (repo / 'doc').exists():
            shutil.copytree(repo / 'doc', temp / 'doc')
        if (repo / 'AGENTS.md').exists():
            shutil.copy2(repo / 'AGENTS.md', temp / 'AGENTS.md')
        navigation = '# 独立能力分发包\n\n各目录的 SKILL.md 是调用入口；此目录为生成产物，修改应回到源仓库的唯一维护文件。\n\n'
        navigation += '\n'.join('- [' + owner.split('/')[1] + '](' + owner + '/SKILL.md)' for owner in sorted(plans)) + '\n'
        (temp / 'README.md').write_text(navigation)
        for page in (temp / 'doc').rglob('*.md'):
            page.write_text(optional_doc_links(page.read_text(), page.relative_to(temp).as_posix(), temp))
        (temp / 'bundle.json').write_text(json.dumps({'schema': 1, 'entries': names, 'packages': sorted(plans)}, indent=2) + '\n')
        # Exclusive directory creation closes the overwrite race, including empty directories.
        # Readers should wait for bundle.json: it is moved last as the completion marker.
        output.mkdir()
        try:
            for child in sorted(temp.iterdir(), key=lambda p: p.name == 'bundle.json'):
                child.rename(output / child.name)
            temp.rmdir()
        except BaseException:
            shutil.rmtree(output)
            raise
    except BaseException:
        if temp.exists():
            shutil.rmtree(temp)
        raise
    return {'output': str(output), 'packages': len(plans), 'materialized_files': sum(len(p) for p in plans.values())}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, type=Path)
    parser.add_argument('--entry', action='append', help='Global skill/workflow name; repeat to select several')
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    if bool(args.entry) == bool(args.all):
        parser.error('Choose --entry (repeatable) or --all')
    names = sorted(inventory(args.repo)) if args.all else args.entry
    print(json.dumps(build(args.repo, names, args.output), ensure_ascii=False))


if __name__ == '__main__':
    main()
