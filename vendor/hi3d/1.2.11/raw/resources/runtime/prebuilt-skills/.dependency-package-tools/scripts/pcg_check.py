"""Validate skills/workflows pcg sidecars at ingest. No network, no capability import."""
from __future__ import annotations

from pathlib import Path
import json
import re
import sys

from bundle import CATEGORIES, IGNORED, credential_path, inventory, source_file
from pcg_architecture import ensure_missing
from pcg_yaml import load as load_yaml

LOCK_SCHEMA = 'pcg.ops.lock.v1'
KINDS = {'agent_workflow', 'agent_skill'}
PARTITIONS = {'software', 'hardware', 'make'}
IRREVERSIBLE = {
    'hi3d.submit', 'mdf.invoke', 'blender.write', 'overwrite.source',
    'publish', 'delete', 'network.write',
}
ID_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_]{0,63}$')


def check_repository(repo):
    repo = Path(repo).resolve()
    entries = inventory(repo)
    checked = []
    for name, owner in sorted(entries.items(), key=lambda item: item[0]):
        category = owner.split('/', 1)[0]
        if category == 'tools':
            sidecar = repo / owner / 'pcg'
            if sidecar.exists():
                raise ValueError('tools must not ship pcg sidecars: ' + owner)
            continue
        checked.append(name)
        try:
            check_entry(repo, name, owner)
        except FileNotFoundError as exc:
            raise ValueError('missing pcg sidecar: ' + str(exc)) from exc
    return {'entries': len(checked)}


def check_entry(repo, name, owner):
    root = repo / owner
    routes_path = owner + '/pcg/routes.yaml'
    lock_path = owner + '/pcg/ops.lock.json'
    source_file(repo, routes_path)
    source_file(repo, lock_path)
    routes = load_yaml(source_file(repo, routes_path).read_text())
    lock = json.loads(source_file(repo, lock_path).read_text())
    category = owner.split('/', 1)[0]
    expected_kind = 'agent_workflow' if category == 'workflows' else 'agent_skill'
    _check_lock(lock, name, expected_kind)
    _check_routes(repo, owner, routes, expected_kind, lock)
    source_file(repo, owner + '/pcg/architecture.yaml')
    architecture = load_yaml(source_file(repo, owner + '/pcg/architecture.yaml').read_text())
    _check_architecture(name, architecture, expected_kind, routes)


def _check_lock(lock, name, expected_kind):
    if lock.get('schema') != LOCK_SCHEMA:
        raise ValueError(name + ': ops.lock schema must be ' + LOCK_SCHEMA)
    if lock.get('skill') != name:
        raise ValueError(name + ': ops.lock skill must match entry name')
    if lock.get('kind') != expected_kind:
        raise ValueError(name + ': ops.lock kind must be ' + expected_kind)
    ops = lock.get('blueprint_pcg_ops')
    unmapped = lock.get('unmapped')
    if not isinstance(ops, list) or any(not isinstance(item, str) or not item for item in ops):
        raise ValueError(name + ': blueprint_pcg_ops must be a string list')
    if not isinstance(unmapped, list) or not unmapped:
        raise ValueError(name + ': unmapped checkpoints are required')
    if any(not isinstance(item, str) or not ID_RE.fullmatch(item) for item in unmapped):
        raise ValueError(name + ': unmapped ids must be identifiers')
    if len(set(unmapped)) != len(unmapped):
        raise ValueError(name + ': duplicate unmapped id')


def _check_routes(repo, owner, routes, expected_kind, lock):
    name = lock['skill']
    if routes.get('kind') != expected_kind:
        raise ValueError(name + ': routes.kind must be ' + expected_kind)
    if routes.get('entry') != 'SKILL.md':
        raise ValueError(name + ': routes.entry must be SKILL.md')
    if routes.get('partition') not in PARTITIONS:
        raise ValueError(name + ': routes.partition must be software|hardware|make')
    ui = routes.get('ui')
    if not isinstance(ui, dict) or ui.get('option_buttons') is not True:
        raise ValueError(name + ': ui.option_buttons must be true for frontend option cards')
    checkpoints = routes.get('checkpoints')
    if not isinstance(checkpoints, list) or len(checkpoints) < 2:
        raise ValueError(name + ': at least two checkpoints are required')
    ids = []
    for item in checkpoints:
        cid = item.get('id') if isinstance(item, dict) else None
        if not isinstance(cid, str) or not ID_RE.fullmatch(cid) or cid in ids:
            raise ValueError(name + ': invalid or duplicate checkpoint id')
        ids.append(cid)
    for item in checkpoints:
        _check_checkpoint(repo, owner, name, item, ids)
    if ids != lock['unmapped']:
        raise ValueError(name + ': ops.lock unmapped must match checkpoint ids in order')
    routes_list = routes.get('routes')
    if not isinstance(routes_list, list) or not routes_list:
        raise ValueError(name + ': routes[] is required')
    route_ids = []
    id_set = set(ids)
    for route in routes_list:
        if not isinstance(route, dict):
            raise ValueError(name + ': route must be a mapping')
        rid = route.get('id')
        if not isinstance(rid, str) or not ID_RE.fullmatch(rid):
            raise ValueError(name + ': invalid route id')
        if rid in route_ids:
            raise ValueError(name + ': duplicate route id ' + rid)
        route_ids.append(rid)
        nodes = route.get('nodes')
        if not isinstance(nodes, list) or not nodes or any(node not in id_set for node in nodes):
            raise ValueError(name + ': route ' + rid + ' nodes must be checkpoint ids')
        rollback = route.get('rollback_to')
        if rollback is not None and rollback not in id_set:
            raise ValueError(name + ': route rollback_to must be a checkpoint')
    choices = routes.get('choices_example')
    if not isinstance(choices, list) or not (2 <= len(choices) <= 4):
        raise ValueError(name + ': choices_example must have 2-4 frontend option buttons')
    choice_ids = []
    for choice in choices:
        if not isinstance(choice, dict):
            raise ValueError(name + ': choice must be a mapping')
        cid = choice.get('id')
        title = choice.get('title')
        if not isinstance(cid, str) or not ID_RE.fullmatch(cid) or cid in choice_ids:
            raise ValueError(name + ': invalid or duplicate choice id')
        if not isinstance(title, str) or not (2 <= len(title) <= 40):
            raise ValueError(name + ': choice title must be 2-40 characters')
        choice_ids.append(cid)
        has_route = choice.get('route') in route_ids
        has_rollback = choice.get('rollback_to') in id_set
        if has_route == has_rollback:
            raise ValueError(name + ': each choice needs exactly one of route or rollback_to')
        if 'confirm' in choice and not isinstance(choice.get('confirm'), bool):
            raise ValueError(name + ': choice.confirm must be boolean')


def _check_architecture(name, architecture, expected_kind, routes=None):
    if not isinstance(architecture, dict):
        raise ValueError(name + ': architecture.yaml must be a mapping')
    if architecture.get('schema') != 'pcg.architecture.v1':
        raise ValueError(name + ': architecture schema must be pcg.architecture.v1')
    if architecture.get('entry') != name:
        raise ValueError(name + ': architecture.entry must match the package name')
    if architecture.get('kind') != expected_kind:
        raise ValueError(name + ': architecture.kind must be ' + expected_kind)
    layout = architecture.get('layout')
    expected_layout = 'linear' if expected_kind == 'agent_skill' else 'tree'
    if layout != expected_layout:
        raise ValueError(name + ': architecture.layout must be ' + expected_layout)
    tasks = architecture.get('tasks')
    if not isinstance(tasks, list) or not tasks:
        raise ValueError(name + ': architecture.tasks is required')
    by_id = {}
    roles = {'agent', 'subagent', 'local'}
    rollbacks = {}
    for item in tasks:
        if not isinstance(item, dict):
            raise ValueError(name + ': architecture task must be a mapping')
        tid = item.get('id')
        role = item.get('role')
        parent = item.get('parent')
        if not isinstance(tid, str) or not ID_RE.fullmatch(tid) or tid in by_id:
            raise ValueError(name + ': invalid or duplicate architecture task id')
        if role not in roles:
            raise ValueError(name + ': architecture role must be agent, subagent or local')
        if parent is not None and not isinstance(parent, str):
            raise ValueError(name + ': architecture parent must be a string or null')
        if role == 'subagent' and not item.get('entry'):
            raise ValueError(name + ': subagent requires entry')
        rollback = item.get('rollback_to')
        if rollback is not None and (not isinstance(rollback, str) or not ID_RE.fullmatch(rollback)):
            raise ValueError(name + ': architecture rollback_to must be a task id')
        flags = item.get('irreversible') or []
        if not isinstance(flags, list) or any(flag not in IRREVERSIBLE for flag in flags):
            raise ValueError(name + ': architecture irreversible must use known permission flags')
        members = item.get('members') or []
        if not isinstance(members, list):
            raise ValueError(name + ': architecture members must be a list')
        member_ids = []
        for member in members:
            if not isinstance(member, dict) or not isinstance(member.get('id'), str):
                raise ValueError(name + ': architecture member needs an id')
            if member['id'] in member_ids:
                raise ValueError(name + ': duplicate architecture member id')
            member_ids.append(member['id'])
        output_ids = []
        for slot in item.get('outputs') or []:
            if not isinstance(slot, dict) or not isinstance(slot.get('id'), str) or not ID_RE.fullmatch(slot['id']):
                raise ValueError(name + ': architecture output needs an id')
            if slot['id'] in output_ids:
                raise ValueError(name + ': duplicate architecture output id')
            output_ids.append(slot['id'])
            kind = slot.get('kind') or 'file'
            if kind not in ('file', 'url'):
                raise ValueError(name + ': architecture output kind must be file or url')
            retain = slot.get('retain') or 'keep'
            if retain not in ('keep', 'cache', 'ephemeral'):
                raise ValueError(name + ': architecture output retain must be keep, cache or ephemeral')
            tags = slot.get('semantics') or []
            if not isinstance(tags, list) or any(not isinstance(tag, str) or not ID_RE.fullmatch(tag) for tag in tags):
                raise ValueError(name + ': architecture output semantics must be identifiers')
        by_id[tid] = parent
        rollbacks[tid] = rollback
    roots = [tid for tid, parent in by_id.items() if not parent]
    if len(roots) != 1:
        raise ValueError(name + ': architecture must form one tree')
    seen = set()

    def walk(tid, stack):
        if tid in stack:
            raise ValueError(name + ': architecture has a cycle')
        if tid in seen:
            return
        seen.add(tid)
        nxt = stack | {tid}
        for child, parent in by_id.items():
            if parent == tid:
                walk(child, nxt)

    walk(roots[0], set())
    if seen != set(by_id):
        raise ValueError(name + ': architecture parent is unknown or disconnected')
    for tid, parent in by_id.items():
        if parent and parent not in by_id:
            raise ValueError(name + ': architecture parent is unknown')
    if layout == 'linear':
        _check_linear_skill(name, by_id, rollbacks, roots[0], routes)


def _check_linear_skill(name, by_id, rollbacks, root, routes):
    cur = root
    stages = []
    seen = {root}
    while True:
        kids = [tid for tid, parent in by_id.items() if parent == cur]
        if len(kids) > 1:
            raise ValueError(name + ': skill architecture must be a single chain')
        if not kids:
            break
        nxt = kids[0]
        target = rollbacks.get(nxt)
        if target:
            if target not in seen or target == nxt:
                raise ValueError(name + ': rollback_to must name an earlier task')
        seen.add(nxt)
        stages.append(nxt)
        cur = nxt
    if seen != set(by_id):
        raise ValueError(name + ': skill architecture must visit every task')
    checkpoints = []
    if isinstance(routes, dict):
        checkpoints = [
            item for item in (routes.get('checkpoints') or [])
            if isinstance(item, dict) and item.get('id')
        ]
    expected = [item['id'] for item in checkpoints]
    if expected and stages != expected:
        raise ValueError(name + ': linear tasks must match checkpoint ids in order')
    for item in checkpoints:
        cid = item['id']
        expected_rb = item.get('rollback_to') or None
        actual = rollbacks.get(cid) or None
        if actual != expected_rb:
            raise ValueError(name + ': architecture rollback_to must match routes checkpoint ' + cid)


def _check_checkpoint(repo, owner, name, item, seen):
    if not isinstance(item, dict):
        raise ValueError(name + ': checkpoint must be a mapping')
    cid = item.get('id')
    say = item.get('say')
    if not isinstance(say, str) or not (2 <= len(say) <= 24):
        raise ValueError(name + ': checkpoint.say must be a short user-facing label')
    rollback = item.get('rollback_to')
    if rollback is not None and (rollback not in seen or rollback == cid):
        raise ValueError(name + ': rollback_to must name another checkpoint')
    load = item.get('load')
    if not isinstance(load, list) or not load or load[0] != 'SKILL.md':
        raise ValueError(name + ': checkpoint.load must start with SKILL.md')
    # Catalog only. Hosts inject with pending_inject; do not re-send every turn.
    root = repo / owner
    for relative in load:
        if not isinstance(relative, str) or relative.startswith('/') or '..' in Path(relative).parts:
            raise ValueError(name + ': load path must stay in the entry: ' + str(relative))
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise ValueError(name + ': load path missing: ' + owner + '/' + relative)
    flags = item.get('irreversible')
    if not isinstance(flags, list) or any(flag not in IRREVERSIBLE for flag in flags):
        raise ValueError(name + ': irreversible must use known permission flags')
    if flags and item.get('confirm_required') is not True:
        raise ValueError(name + ': irreversible checkpoints need confirm_required: true')
    if not flags and item.get('confirm_required') not in (False, None):
        raise ValueError(name + ': confirm_required is only for irreversible steps')
    return cid


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, type=Path)
    parser.add_argument(
        '--write-missing-architecture',
        action='store_true',
        help='create pcg/architecture.yaml from routes when the file is absent; never overwrite',
    )
    args = parser.parse_args(argv)
    try:
        seeded = ensure_missing(args.repo) if args.write_missing_architecture else []
        result = check_repository(args.repo)
        if seeded:
            result['seeded_architecture'] = seeded
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
