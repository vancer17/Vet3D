"""Execution board: skill linear rollback chain or workflow spawn tree."""
from __future__ import annotations

from view_ir import BILLABLE, COLOR_PLACEHOLDERS, TONES

SCHEMA = 'pcg.board.v1'
ROLES = ('agent', 'subagent', 'local')
LAYOUTS = ('linear', 'tree')
RETAIN = ('keep', 'cache', 'ephemeral')
EMPTY_COST = {'hi3d_submit_count': 0, 'mdf_invoke_count': 0, 'flags': []}


def resolve_layout(architecture):
    """Skills are a rollback chain; workflows are an orchestration tree."""
    kind = architecture.get('kind')
    layout = architecture.get('layout')
    if layout is None:
        layout = 'linear' if kind == 'agent_skill' else 'tree'
    if layout not in LAYOUTS:
        raise ValueError('architecture.layout must be linear or tree')
    if kind == 'agent_skill' and layout != 'linear':
        raise ValueError('skill architecture.layout must be linear')
    if kind == 'agent_workflow' and layout != 'tree':
        raise ValueError('workflow architecture.layout must be tree')
    return layout


def compose_board(architecture, session=None):
    """Return a board from a declared architecture mapping.

    Skills (`layout=linear`) are a checkpoint chain with rollback edges.
    Workflows (`layout=tree`) are an orchestration org-chart. This is not the
    PCG user-option graph. Declared outputs become leaf artifact nodes.
    """
    session = session or {}
    if session and not isinstance(session, dict):
        raise ValueError('session must be a mapping')
    if session.get('schema') not in (None, 'pcg.session.v1'):
        raise ValueError('session schema must be pcg.session.v1')
    if not isinstance(architecture, dict):
        raise ValueError('architecture must be a mapping')
    if architecture.get('schema') != 'pcg.architecture.v1':
        raise ValueError('architecture schema must be pcg.architecture.v1')
    layout = resolve_layout(architecture)
    tasks = architecture.get('tasks')
    if not isinstance(tasks, list) or not tasks:
        raise ValueError('architecture.tasks is required')
    by_id = {}
    for item in tasks:
        if not isinstance(item, dict):
            raise ValueError('task must be a mapping')
        tid = item.get('id')
        role = item.get('role')
        parent = item.get('parent')
        label = item.get('label') or tid
        if not isinstance(tid, str) or not tid or tid in by_id:
            raise ValueError('invalid task id')
        if role not in ROLES:
            raise ValueError('task role must be agent, subagent or local')
        if parent is not None and not isinstance(parent, str):
            raise ValueError('task parent must be a string or null')
        if role == 'subagent' and not item.get('entry'):
            raise ValueError('subagent requires entry')
        rollback_to = item.get('rollback_to')
        if rollback_to is not None and not isinstance(rollback_to, str):
            raise ValueError('task rollback_to must be a string or null')
        flags = list(item.get('irreversible') or [])
        billable = [flag for flag in flags if flag in BILLABLE]
        if billable:
            tone = 'billable'
        elif flags:
            tone = 'irreversible'
        else:
            tone = 'reversible'
        members = []
        for member in item.get('members') or []:
            if not isinstance(member, dict) or not member.get('id'):
                raise ValueError('member needs an id')
            members.append({
                'id': member['id'],
                'say': member.get('label') or member['id'],
                'tone': 'reversible',
                'billable': [],
                'cost': {'hi3d_submit_count': 0, 'mdf_invoke_count': 0, 'flags': []},
            })
        cost = {
            'hi3d_submit_count': 1 if 'hi3d.submit' in billable else 0,
            'mdf_invoke_count': 1 if 'mdf.invoke' in billable else 0,
            'flags': list(billable),
        }
        if tone not in TONES:
            raise ValueError('invalid tone')
        by_id[tid] = {
            'id': tid,
            'parent': parent,
            'label': label,
            'say': label,
            'role': role,
            'function': item.get('function') or label,
            'entry': item.get('entry'),
            'optional': bool(item.get('optional')),
            'rollback_to': rollback_to,
            'tone': tone,
            'color': COLOR_PLACEHOLDERS[tone],
            'flags': flags,
            'cost': cost,
            'members': members,
            'rail_ids': [member['id'] for member in members],
            'outputs': _outputs(item),
        }
    roots = [node['id'] for node in by_id.values() if not node['parent']]
    if len(roots) != 1:
        raise ValueError('architecture must form one tree')
    children = {nid: [] for nid in by_id}
    for node in by_id.values():
        if node['parent'] and node['parent'] not in by_id:
            raise ValueError('task parent is unknown')
        if node['parent']:
            children[node['parent']].append(node['id'])

    def _walk(nid, stack):
        if nid in stack:
            raise ValueError('architecture has a cycle')
        nxt = stack | {nid}
        for child in children[nid]:
            _walk(child, nxt)

    _walk(roots[0], set())
    if layout == 'linear':
        stage_ids = _assert_linear_chain(by_id, children, roots[0])
    else:
        stage_ids = [node['id'] for node in by_id.values() if node['id'] != roots[0]]
    edges = []
    for node in by_id.values():
        if not node['parent']:
            continue
        if node['role'] == 'subagent':
            kind = 'spawn'
        elif layout == 'linear':
            kind = 'advance'
        else:
            kind = 'contains'
        edges.append({
            'from': node['parent'],
            'to': node['id'],
            'kind': kind,
            'tone': node['tone'],
            'color': node['color'],
            'cost': node['cost'],
        })
    if layout == 'linear':
        for node in by_id.values():
            target = node.get('rollback_to')
            if not target:
                continue
            if target not in by_id or target == node['id']:
                raise ValueError('rollback_to must name another task')
            edges.append({
                'from': node['id'],
                'to': target,
                'kind': 'rollback',
                'tone': 'reversible',
                'color': COLOR_PLACEHOLDERS['reversible'],
                'cost': dict(EMPTY_COST),
            })
    groups = []
    for index, node in enumerate(by_id.values(), start=1):
        if node['id'] == roots[0]:
            continue
        groups.append({
            'id': 'wg_%s' % index,
            'label': node['function'],
            'source': 'agent',
            'tone': node['tone'],
            'color': node['color'],
            'member_node_ids': [node['id']],
            'rail_ids': node['rail_ids'],
        })
    slotted, unslotted = _index_session(session)
    artifact_nodes = []
    for node in list(by_id.values()):
        for slot in node.get('outputs') or []:
            leaf = _artifact_node(node, slot, slotted.get((node['id'], slot['id'])))
            artifact_nodes.append(leaf)
            by_id[leaf['id']] = leaf
            children.setdefault(node['id'], []).append(leaf['id'])
            edges.append({
                'from': node['id'],
                'to': leaf['id'],
                'kind': 'produces',
                'tone': leaf['tone'],
                'color': leaf['color'],
                'cost': dict(EMPTY_COST),
            })
    for index, item in enumerate(unslotted, start=1):
        leaf = _unslotted_node(roots[0], item, index)
        artifact_nodes.append(leaf)
        by_id[leaf['id']] = leaf
        edges.append({
            'from': roots[0],
            'to': leaf['id'],
            'kind': 'produces',
            'tone': leaf['tone'],
            'color': leaf['color'],
            'cost': dict(EMPTY_COST),
        })
    catalog = [_catalog_item(leaf) for leaf in artifact_nodes]
    return {
        'schema': SCHEMA,
        'entry': architecture.get('entry'),
        'kind': architecture.get('kind'),
        'overview': {
            'kind': 'architecture',
            'layout': layout,
            'root': roots[0],
            'nodes': list(by_id.values()),
            'edges': edges,
            'groups': groups,
        },
        'catalog': {'artifacts': catalog},
        'color_catalog': {
            'status': 'placeholder',
            'note': 'example fills by tone; host/theme may replace',
            'by_tone': dict(COLOR_PLACEHOLDERS),
        },
        'host_actions': {
            'focus_overview': [node['id'] for node in by_id.values() if node['id'] != roots[0] and node.get('role') != 'artifact'],
            'advance': list(stage_ids),
            'rollback': [node['id'] for node in by_id.values() if node.get('rollback_to')],
            'spawn_subagent': [node['id'] for node in by_id.values() if node['role'] == 'subagent'],
            'focus_leaves': [node['id'] for node in artifact_nodes],
            'find_artifact': [item['id'] for item in catalog if item.get('findable')],
            'open_artifact': [item['id'] for item in catalog if item.get('status') == 'ready' and item.get('href')],
            'lod': ['preview', 'detail'] if layout == 'tree' else ['detail'],
            'note': (
                'catalog.artifacts is the finder for every board view. '
                'tree lod=preview is glyphs and tone color only; lod=detail reveals labels. '
                'select_purge matches retain=cache|ephemeral and requested semantics; keep is never selected.'
            ),
        },
    }


def _assert_linear_chain(by_id, children, root):
    cur = root
    seen = {root}
    stages = []
    while True:
        kids = list(children.get(cur) or [])
        if len(kids) > 1:
            raise ValueError('linear architecture must be a single chain')
        if not kids:
            break
        nxt = kids[0]
        if nxt in seen:
            raise ValueError('architecture has a cycle')
        target = by_id[nxt].get('rollback_to')
        if target:
            if target not in by_id or target == nxt:
                raise ValueError('rollback_to must name another task')
            if target not in seen:
                raise ValueError('rollback_to must name an earlier task')
        seen.add(nxt)
        stages.append(nxt)
        cur = nxt
    if seen != set(by_id):
        raise ValueError('linear architecture must visit every task')
    return stages


def _outputs(item):
    outputs = []
    seen = set()
    for slot in item.get('outputs') or []:
        if not isinstance(slot, dict) or not slot.get('id'):
            raise ValueError('output needs an id')
        oid = slot['id']
        if oid in seen:
            raise ValueError('duplicate output id')
        seen.add(oid)
        outputs.append({
            'id': oid,
            'label': slot.get('label') or oid,
            'kind': slot.get('kind') or 'file',
            'retain': _retain(slot),
            'semantics': _semantics(slot),
        })
    return outputs


def _index_session(session):
    slotted = {}
    unslotted = []
    for item in session.get('artifacts') or []:
        if not isinstance(item, dict) or not item.get('path'):
            raise ValueError('session artifact needs a path')
        task = item.get('task')
        output = item.get('output')
        if (task is None) != (output is None):
            raise ValueError('session artifact task and output must be set together')
        if task:
            slotted[(task, output)] = item
        else:
            unslotted.append(item)
    return slotted, unslotted


def _artifact_node(parent, slot, bound):
    bound = bound or {}
    nid = '%s__%s' % (parent['id'], slot['id'])
    path = bound.get('path')
    href = bound.get('href')
    traces = list(bound.get('traces') or [])
    status = 'pending'
    if bound.get('purged'):
        status = 'purged'
    elif path or href:
        status = 'ready'
    return {
        'id': nid,
        'parent': parent['id'],
        'label': slot['label'],
        'say': slot['label'],
        'role': 'artifact',
        'function': slot['kind'],
        'entry': None,
        'optional': False,
        'tone': 'reversible',
        'color': COLOR_PLACEHOLDERS['reversible'],
        'flags': [],
        'cost': dict(EMPTY_COST),
        'members': _trace_members(traces, path, href),
        'rail_ids': [event.get('at') or event.get('path') for event in traces],
        'output_id': slot['id'],
        'kind': slot['kind'],
        'retain': slot['retain'],
        'semantics': list(slot['semantics']),
        'path': path,
        'href': href or path,
        'digest': bound.get('hash') or bound.get('digest'),
        'status': status,
        'traces': traces,
        'findable': bool(path or href or traces),
    }


def _unslotted_node(root, item, index):
    nid = 'unslotted_%s' % index
    path = item.get('path')
    href = item.get('href')
    traces = list(item.get('traces') or [])
    label = path.rsplit('/', 1)[-1] if path else nid
    return {
        'id': nid,
        'parent': root,
        'label': label,
        'say': label,
        'role': 'artifact',
        'function': 'unslotted',
        'entry': None,
        'optional': False,
        'tone': 'reversible',
        'color': COLOR_PLACEHOLDERS['reversible'],
        'flags': [],
        'cost': dict(EMPTY_COST),
        'members': _trace_members(traces, path, href),
        'rail_ids': [],
        'output_id': None,
        'kind': 'file',
        'output_id': None,
        'path': path,
        'href': href or path,
        'digest': item.get('hash'),
        'status': 'purged' if item.get('purged') else ('ready' if path else 'pending'),
        'traces': traces,
        'retain': item.get('retain') or 'cache',
        'semantics': list(item.get('semantics') or ['unslotted']),
        'findable': bool(path or href or traces),
    }


def _trace_members(traces, path, href):
    members = []
    if path:
        members.append({
            'id': 'current',
            'say': path,
            'href': href,
            'tone': 'reversible',
            'billable': [],
            'cost': dict(EMPTY_COST),
        })
    for index, event in enumerate(traces, start=1):
        members.append({
            'id': 'trace_%s' % index,
            'say': '%s · %s' % (event.get('op') or 'add', event.get('path') or ''),
            'href': event.get('href'),
            'tone': 'reversible',
            'billable': [],
            'cost': dict(EMPTY_COST),
        })
    return members


def select_purge(architecture, session=None, *, semantics=()):
    """Return cache/ephemeral file slots matching semantics. Never selects retain=keep."""
    wanted = set(semantics or ())
    if any(not isinstance(tag, str) or not tag for tag in wanted):
        raise ValueError('semantics tags must be strings')
    board = compose_board(architecture, session)
    targets = []
    for item in board['catalog']['artifacts']:
        if item.get('retain') not in ('cache', 'ephemeral'):
            continue
        if item.get('kind') == 'url' or item.get('status') == 'purged' or not item.get('path'):
            continue
        tags = set(item.get('semantics') or [])
        if wanted and not wanted.intersection(tags):
            continue
        targets.append({
            'id': item['id'],
            'task': item['id'].rsplit('__', 1)[0] if item.get('output_id') else None,
            'output': item.get('output_id'),
            'path': item['path'],
            'retain': item['retain'],
            'semantics': list(item.get('semantics') or []),
        })
    return targets


def locate_board(board, task_root):
    """Mark ready leaves missing on disk without deleting records. URLs are not fetched."""
    from pathlib import Path
    if board.get('schema') != SCHEMA:
        raise ValueError('locate requires pcg.board.v1')
    root = Path(task_root).resolve()
    by_id = {item['id']: item for item in (board.get('catalog') or {}).get('artifacts') or []}
    for node in (board.get('overview') or {}).get('nodes') or []:
        if node.get('role') != 'artifact' or node.get('status') == 'purged':
            continue
        if node.get('kind') == 'url':
            continue
        path = node.get('path')
        if not path:
            continue
        candidate = Path(path)
        located = root / path if not candidate.is_absolute() else candidate.resolve()
        if root not in located.parents and located != root:
            node['status'] = 'missing'
        elif located.is_file() or located.is_dir():
            node['status'] = 'ready'
        else:
            node['status'] = 'missing'
        if node['id'] in by_id:
            by_id[node['id']]['status'] = node['status']
    board['host_actions']['open_artifact'] = [
        item['id'] for item in by_id.values() if item.get('status') == 'ready' and item.get('href')
    ]
    board['host_actions']['find_artifact'] = [
        item['id'] for item in by_id.values() if item.get('findable')
    ]
    return board


def _catalog_item(leaf):
    return {
        'id': leaf['id'],
        'label': leaf.get('label') or leaf['id'],
        'task': leaf.get('parent'),
        'output': leaf.get('output_id'),
        'kind': leaf.get('kind') or 'file',
        'retain': leaf.get('retain') or 'keep',
        'semantics': list(leaf.get('semantics') or []),
        'status': leaf.get('status') or 'pending',
        'path': leaf.get('path'),
        'href': leaf.get('href'),
        'findable': bool(leaf.get('findable')),
    }


def _retain(slot):
    value = slot.get('retain') or 'keep'
    if value not in RETAIN:
        raise ValueError('output retain must be keep, cache or ephemeral')
    return value


def _semantics(slot):
    tags = slot.get('semantics') or []
    if not isinstance(tags, list) or any(not isinstance(tag, str) or not tag for tag in tags):
        raise ValueError('output semantics must be a string list')
    return list(tags)
