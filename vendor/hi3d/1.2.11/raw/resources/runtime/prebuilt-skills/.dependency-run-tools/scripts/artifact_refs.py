"""Conversation artifact aliases on a package-external session. No network."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from session_schema import validate_session

NAME_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_-]{0,63}$')
TOKEN_RE = re.compile(r'(?<![A-Za-z0-9_])@([A-Za-z][A-Za-z0-9_-]{0,63})\b')
RESERVED = frozenset({'last'})


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _name(value):
    if not isinstance(value, str) or not NAME_RE.fullmatch(value):
        raise ValueError('ref name must match [A-Za-z][A-Za-z0-9_-]{0,63}')
    if value in RESERVED:
        raise ValueError('ref name last is reserved for the most recent mark')
    return value


def _token_name(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('ref token is required')
    token = value.strip()
    if token.startswith('ref:'):
        token = token[4:]
    if token.startswith('@'):
        token = token[1:]
    return token


def _quote(path):
    if any(ch.isspace() for ch in path) or any(ch in path for ch in '"\''):
        return json.dumps(path, ensure_ascii=False)
    return path


def _index(refs, name):
    for index, item in enumerate(refs):
        if item.get('name') == name:
            return index
    return None


def mark_ref(session, *, name, path, label=None, task=None, output=None, entry=None, at=None):
    """Bind a conversation alias to a task-directory path. Same name updates in place."""
    validate_session(session)
    name = _name(name)
    if not isinstance(path, str) or not path:
        raise ValueError('ref path is required')
    if path.lower().startswith(('http://', 'https://', 'javascript:')):
        raise ValueError('ref path must be a local task path, not a URL')
    if (task is None) != (output is None):
        raise ValueError('ref task and output must be set together')
    refs = list(session.get('refs') or [])
    record = {
        'name': name,
        'path': path,
        'label': label if isinstance(label, str) else '',
        'task': task,
        'output': output,
        'entry': entry,
        'at': at or _utc_now(),
    }
    index = _index(refs, name)
    if index is None:
        refs.append(record)
    else:
        refs[index] = record
    session['refs'] = refs
    return validate_session(session)


def mark_slot(session, *, name, task, output, label=None, at=None):
    """Copy path from an existing artifact slot, then mark it."""
    validate_session(session)
    if not task or not output:
        raise ValueError('slot task and output are required')
    for item in session.get('artifacts') or []:
        if item.get('task') == task and item.get('output') == output:
            return mark_ref(
                session,
                name=name,
                path=item['path'],
                label=label,
                task=task,
                output=output,
                entry=session.get('entry'),
                at=at,
            )
    raise ValueError('unknown artifact slot ' + task + '/' + output)


def list_refs(session):
    validate_session(session)
    return [dict(item) for item in session.get('refs') or []]


def resolve_ref(session, token, *, task_root=None):
    """Return the ref record for @name, ref:name, or @last."""
    validate_session(session)
    name = _token_name(token)
    refs = list_refs(session)
    if name == 'last':
        if not refs:
            raise ValueError('no marked refs in this session')
        chosen = max(refs, key=lambda item: (item.get('at') or '', refs.index(item)))
    else:
        matches = [item for item in refs if item['name'] == name]
        if not matches:
            raise ValueError('unknown ref @' + name)
        chosen = matches[0]
    record = dict(chosen)
    if task_root is not None:
        root = Path(task_root).resolve()
        candidate = Path(record['path'])
        located = candidate if candidate.is_absolute() else root / candidate
        record['exists'] = located.is_file()
        record['resolved'] = str(located)
        if root not in located.parents and located != root:
            raise ValueError('ref path escapes task_root: ' + record['path'])
    return record


def rewrite_instruction(text, session):
    """Replace known @name / @last tokens with quoted paths; leave other @text unchanged."""
    if not isinstance(text, str):
        raise ValueError('instruction text is required')
    validate_session(session)
    names = {item['name'] for item in list_refs(session)}

    def replace(match):
        name = match.group(1)
        if name != 'last' and name not in names:
            return match.group(0)
        record = resolve_ref(session, name)
        return _quote(record['path'])

    return TOKEN_RE.sub(replace, text)


def load_session(path):
    path = Path(path)
    with path.open(encoding='utf-8') as handle:
        document = json.load(handle)
    return validate_session(document)


def save_session(path, session):
    validate_session(session)
    path = Path(path)
    text = json.dumps(session, ensure_ascii=False, indent=2) + '\n'
    path.write_text(text, encoding='utf-8')
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)

    mark = sub.add_parser('mark', help='bind @name to a local path or existing slot')
    mark.add_argument('--session', type=Path, required=True)
    mark.add_argument('--name', required=True)
    mark.add_argument('--path')
    mark.add_argument('--label', default='')
    mark.add_argument('--task')
    mark.add_argument('--output')

    listed = sub.add_parser('list', help='print conversation refs')
    listed.add_argument('--session', type=Path, required=True)

    resolve = sub.add_parser('resolve', help='resolve @name or @last')
    resolve.add_argument('--session', type=Path, required=True)
    resolve.add_argument('--ref', required=True)
    resolve.add_argument('--task-root', type=Path)

    rewrite = sub.add_parser('rewrite', help='substitute known @name tokens in an instruction')
    rewrite.add_argument('--session', type=Path, required=True)
    rewrite.add_argument('--text', required=True)

    args = parser.parse_args(argv)
    session = load_session(args.session)
    if args.command == 'mark':
        if args.task and args.output and not args.path:
            mark_slot(session, name=args.name, task=args.task, output=args.output, label=args.label or None)
        elif args.path:
            mark_ref(
                session,
                name=args.name,
                path=args.path,
                label=args.label or None,
                task=args.task,
                output=args.output,
                entry=session.get('entry'),
            )
        else:
            parser.error('mark requires --path or both --task and --output')
        save_session(args.session, session)
        print(json.dumps(resolve_ref(session, args.name), ensure_ascii=False, indent=2))
        return 0
    if args.command == 'list':
        print(json.dumps(list_refs(session), ensure_ascii=False, indent=2))
        return 0
    if args.command == 'resolve':
        record = resolve_ref(session, args.ref, task_root=args.task_root)
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 0
    print(rewrite_instruction(args.text, session))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
