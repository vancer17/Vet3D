"""Baseline pcg.architecture.v1 from routes.yaml. Ingest unique source."""
from __future__ import annotations

from pathlib import Path

from bundle import inventory, source_file
from pcg_yaml import dump, load as load_yaml

NOTE_TREE = (
    '执行架构：编排 agent 与显式独立入口；不是 routes.yaml 的用户选项图。'
    '缺省由 package-tools 自 routes 按入库格式生成，手调后不再覆盖。'
)
NOTE_LINEAR = (
    '线形进程：检查点顺序前进，rollback_to 回退到更早步骤；不是 workflow 编排树。'
    '缺省由 package-tools 自 routes 生成，手调后不再覆盖。'
)

# Irreversible flags that spawn an independent entry. Other flags stay local.
FLAG_SPAWN = {
    'hi3d.submit': 'hi3d-api',
    'mdf.invoke': 'mdf-call',
    'publish': 'game-deploy',
}


def root_id(name):
    return name.replace('-', '_')


def optional_checkpoints(routes):
    """Checkpoints missing from at least one route are optional."""
    ids = [item['id'] for item in routes.get('checkpoints') or [] if isinstance(item, dict) and item.get('id')]
    sets = []
    for route in routes.get('routes') or []:
        nodes = route.get('nodes') if isinstance(route, dict) else None
        if isinstance(nodes, list) and nodes:
            sets.append(set(nodes))
    if not sets:
        return set()
    required = sets[0].intersection(*sets[1:])
    return set(ids) - required


def spawn_entry(irreversible):
    for flag in irreversible or []:
        if flag in FLAG_SPAWN:
            return FLAG_SPAWN[flag]
    return None


def architecture_from_routes(name, kind, routes):
    """Return a one-tree architecture mapping from an already-parsed routes document."""
    if not isinstance(routes, dict):
        raise ValueError(name + ': routes must be a mapping')
    checkpoints = routes.get('checkpoints')
    if not isinstance(checkpoints, list) or not checkpoints:
        raise ValueError(name + ': routes.checkpoints is required to seed architecture')
    rid = root_id(name)
    if any(item.get('id') == rid for item in checkpoints if isinstance(item, dict)):
        raise ValueError(name + ': checkpoint id collides with architecture root ' + rid)
    skippable = optional_checkpoints(routes)
    first = checkpoints[0]
    first_say = first.get('say') if isinstance(first, dict) else name
    layout = 'linear' if kind == 'agent_skill' else 'tree'
    tasks = [{
        'id': rid,
        'parent': None,
        'role': 'agent',
        'label': first_say or name,
        'function': '编排 ' + name,
    }]
    previous = rid
    for item in checkpoints:
        if not isinstance(item, dict) or not item.get('id'):
            raise ValueError(name + ': checkpoint needs an id')
        cid = item['id']
        say = item.get('say') or cid
        flags = list(item.get('irreversible') or [])
        entry = spawn_entry(flags)
        parent = previous if layout == 'linear' else rid
        task = {
            'id': cid,
            'parent': parent,
            'label': say,
            'outputs': [{
                'id': cid,
                'label': say,
                'kind': 'file',
                'retain': 'keep',
                'semantics': ['deliverable'],
            }],
        }
        rollback = item.get('rollback_to')
        if rollback:
            task['rollback_to'] = rollback
        if entry:
            task['role'] = 'subagent'
            task['entry'] = entry
            task['function'] = '派出 ' + entry
            task['members'] = [{'id': 'invoke', 'label': '调用 ' + entry}]
            if cid in skippable:
                task['optional'] = True
        else:
            task['role'] = 'local'
            task['function'] = '本 agent ' + say
            task['members'] = [{'id': 'work', 'label': say}]
        if flags:
            task['irreversible'] = flags
        tasks.append(task)
        previous = cid
    return {
        'schema': 'pcg.architecture.v1',
        'entry': name,
        'kind': kind,
        'layout': layout,
        'note': NOTE_LINEAR if layout == 'linear' else NOTE_TREE,
        'tasks': tasks,
    }


def ensure_missing(repo):
    """Write architecture.yaml only when absent. Never overwrite a hand-tuned file."""
    repo = Path(repo).resolve()
    written = []
    for name, owner in sorted(inventory(repo).items(), key=lambda item: item[0]):
        category = owner.split('/', 1)[0]
        if category == 'tools':
            continue
        path = repo / owner / 'pcg' / 'architecture.yaml'
        if path.exists():
            continue
        routes = load_yaml(source_file(repo, owner + '/pcg/routes.yaml').read_text())
        kind = 'agent_workflow' if category == 'workflows' else 'agent_skill'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dump(architecture_from_routes(name, kind, routes)).rstrip() + '\n')
        written.append(owner + '/pcg/architecture.yaml')
    return written
