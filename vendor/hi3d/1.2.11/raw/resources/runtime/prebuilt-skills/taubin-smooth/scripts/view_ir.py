"""Split a pcg run into overview subjects, a compact rail, and a credit-board."""
from __future__ import annotations

import importlib.util
from pathlib import Path

SCHEMA = 'pcg.view.v1'
BILLABLE = {'hi3d.submit', 'mdf.invoke'}
TONES = ('billable', 'irreversible', 'reversible')
AGENT_ROLES = ('agent', 'subagent')
# Example fills only; hosts replace. Not a brand or debit spec.
COLOR_PLACEHOLDERS = {
    'billable': '#2AA8A4',
    'irreversible': '#E06B9A',
    'reversible': '#9A8F7A',
}
# Published Hi3D Credits reference (hi3d-api parameters.md, 2026-09-07). Not live debit.
HI3D_CREDIT_HINTS = {
    'geometry_quality': 90,
    'texture': 10,
    'pbr': 5,
    'relief': 10,
    'parts': 20,
    'multicolor': 20,
}


def compose_view(routes, session=None, tool_results=None):
    """Overview tree + zoomed detail nodes; options reuse the PCG popup.

    Billable cost hangs on overview edges and on detail members after zoom.
    Route alternatives are option_popup (existing option buttons), not a panel.
    """
    if not isinstance(routes, dict):
        raise ValueError('routes must be a mapping')
    checkpoints = routes.get('checkpoints')
    route_list = routes.get('routes')
    if not isinstance(checkpoints, list) or not checkpoints:
        raise ValueError('routes.checkpoints is required')
    if not isinstance(route_list, list) or not route_list:
        raise ValueError('routes.routes is required')
    by_id = {}
    for item in checkpoints:
        cid = item.get('id')
        if not isinstance(cid, str) or cid in by_id:
            raise ValueError('invalid checkpoint id')
        by_id[cid] = item
    session = session or {}
    active_id = session.get('route') or route_list[0].get('id')
    active = next((item for item in route_list if item.get('id') == active_id), route_list[0])
    chain = list(active.get('nodes') or [])
    if any(node not in by_id for node in chain):
        raise ValueError('active route references unknown checkpoints')
    states = _node_states(chain, session.get('checkpoint'), session.get('status') or 'running')
    rail = []
    for cid in chain:
        item = by_id[cid]
        flags = list(item.get('irreversible') or [])
        billable = [flag for flag in flags if flag in BILLABLE]
        rail.append({
            'id': cid,
            'say': item.get('say') or cid,
            'state': states.get(cid, 'pending'),
            'irreversible': flags,
            'billable': billable,
            'confirm_required': bool(item.get('confirm_required')),
            'resume_allowed': not flags,
            'rollback_to': item.get('rollback_to'),
        })
    overview = _annotate_graph(_overview(routes, session, rail), rail)
    popup = {
        'role': (routes.get('ui') or {}).get('choice_role') or 'option',
        'surface': 'popup',
        'visible': (session.get('status') or 'running') == 'waiting_choice',
        'choices': _schemes(routes.get('choices_example') or [], route_list, by_id),
        'stage': None,
    }
    _attach_web_options(popup, session, by_id)
    confirm = [step['id'] for step in rail if step['billable']]
    return {
        'schema': SCHEMA,
        'entry': routes.get('entry') or 'SKILL.md',
        'active_route': active.get('id'),
        'session_status': session.get('status') or 'running',
        'overview': overview,
        'rail': rail,
        'option_popup': popup,
        'color_catalog': {
            'status': 'placeholder',
            'note': 'example overview fills by tone; host/theme may replace',
            'by_tone': dict(COLOR_PLACEHOLDERS),
        },
        'credit_catalog': {
            'source': 'hi3d-api/references/runtime/parameters.md',
            'as_of': '2026-09-07',
            'unit': 'Hi3D Credits (reference, not live debit)',
            'hints': dict(HI3D_CREDIT_HINTS),
        },
        'host_actions': {
            'resume_rail': [step['id'] for step in rail if step['resume_allowed']],
            'confirm_nodes': confirm,
            'focus_overview': [node['id'] for node in overview['nodes'] if node['id'] != overview['root']],
            'show_option_popup': popup['visible'],
            'note': (
                'zoom an overview subject to read member cost on detail nodes or on the edge into that subject. '
                'waiting_choice uses the existing PCG option popup; it is not a separate schemes panel. '
                'Hi3D membership gems reuse option_popup.web_options from hi3d-api web_option_gates. '
                'confirm_nodes are irreversible billable submits and are not undone.'
            ),
        },
    }


def _load_web_option_gates():
    here = Path(__file__).resolve().parent
    candidates = (
        here / 'web_option_gates.py',
        here.parents[1] / 'hi3d-api' / 'scripts' / 'web_option_gates.py',
    )
    for path in candidates:
        if path.is_file():
            spec = importlib.util.spec_from_file_location('web_option_gates', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    return None


def _attach_web_options(popup, session, by_id):
    if not popup.get('visible'):
        return
    raw = session.get('hi3d_options') if isinstance(session.get('hi3d_options'), dict) else {}
    waiting = session.get('waiting_context') if isinstance(session.get('waiting_context'), dict) else {}
    stage = waiting.get('stage') or raw.get('stage')
    kind = raw.get('kind')
    if not kind:
        item = by_id.get(session.get('checkpoint')) if session.get('checkpoint') else None
        flags = list((item or {}).get('irreversible') or [])
        if 'hi3d.submit' not in flags and stage != 'parameters':
            return
        kind = 'model'
    gates = _load_web_option_gates()
    if gates is None:
        return
    selected = raw.get('selected') if isinstance(raw.get('selected'), dict) else {}
    by_kind = raw.get('selected_by_kind') if isinstance(raw.get('selected_by_kind'), dict) else {}
    if kind in by_kind and isinstance(by_kind[kind], dict):
        selected = by_kind[kind]
    if stage == 'billing':
        # Legacy sessions may still carry the removed authorization stage.
        # Never recreate that UI; a new parameter dry-run will project current state.
        popup['stage'] = None
        return
    popup['stage'] = stage or 'parameters'
    identity = raw.get('identity') or 'standard'
    surface = raw.get('surface') or 'agent'
    popup['web_options'] = gates.project_web_options(kind, identity, selected, surface)


def _tone(step):
    if step.get('billable'):
        return 'billable'
    if step.get('irreversible'):
        return 'irreversible'
    return 'reversible'


def _overview(routes, session, rail):
    agents = session.get('agents')
    if isinstance(agents, list) and agents:
        return _agent_tree(agents, rail, session)
    return _stage_tree(routes, session, rail)


def _stage_tree(routes, session, rail):
    root_id = session.get('task_id') or session.get('entry') or 'run'
    root_label = session.get('entry') or routes.get('kind') or '当前任务'
    rank = {'reversible': 0, 'irreversible': 1, 'billable': 2}
    root_tone = 'reversible'
    for step in rail:
        candidate = _tone(step)
        if rank[candidate] > rank[root_tone]:
            root_tone = candidate
    root = _subject(
        root_id, None, root_label, 'agent', root_tone,
        session.get('status') or 'running', rail_ids=[step['id'] for step in rail],
        entry=session.get('entry'),
    )
    subjects = [root]
    groups = []
    edges = []
    for index, cluster in enumerate(_stage_clusters(rail), start=1):
        node_id = 'region_%s' % index
        subjects.append(_subject(
            node_id, root_id, cluster['label'], 'group', cluster['tone'],
            cluster['state'], rail_ids=cluster['rail_ids'],
            function=cluster['label'], members=cluster['members'],
            flags=cluster['flags'],
        ))
        edges.append(_edge(root_id, node_id, 'contains'))
        groups.append({
            'id': 'wg_%s' % index,
            'label': cluster['label'],
            'source': 'agent',
            'tone': cluster['tone'],
            'color': _color(cluster['tone']),
            'member_node_ids': [node_id],
            'rail_ids': cluster['rail_ids'],
        })
    return {
        'kind': 'stage_groups',
        'root': root_id,
        'nodes': subjects,
        'edges': edges,
        'groups': groups,
    }


def _stage_clusters(rail):
    clusters = []
    bucket = []
    current = None
    for step in rail:
        tone = _tone(step)
        if bucket and current != tone:
            clusters.append(_cluster(bucket, current))
            bucket = []
        bucket.append(step)
        current = tone
    if bucket:
        clusters.append(_cluster(bucket, current))
    return clusters


def _cluster(steps, tone):
    first = steps[0]
    flags = []
    for step in steps:
        for flag in step.get('irreversible') or []:
            if flag not in flags:
                flags.append(flag)
    states = [step.get('state') for step in steps]
    if 'failed' in states:
        state = 'failed'
    elif 'running' in states or 'waiting_choice' in states:
        state = 'running' if 'running' in states else 'waiting_choice'
    elif states and all(item == 'done' for item in states):
        state = 'done'
    elif states and all(item == 'skipped' for item in states):
        state = 'skipped'
    else:
        state = states[0] if states else 'pending'
    return {
        'label': first.get('say') or first['id'],
        'tone': tone,
        'state': state,
        'rail_ids': [step['id'] for step in steps],
        'members': [_member(step) for step in steps],
        'flags': flags,
    }


def _agent_tree(agents, rail, session):
    nodes = {}
    for item in agents:
        if not isinstance(item, dict):
            raise ValueError('agent must be a mapping')
        aid = item.get('id')
        role = item.get('role')
        parent = item.get('parent')
        label = item.get('label') or aid
        if not isinstance(aid, str) or not aid or aid in nodes:
            raise ValueError('invalid agent id')
        if role not in AGENT_ROLES:
            raise ValueError('agent role must be agent or subagent')
        if parent is not None and not isinstance(parent, str):
            raise ValueError('agent parent must be a string or null')
        if not isinstance(label, str) or not label:
            raise ValueError('agent label is required')
        rail_ids = list(item.get('rail_ids') or [])
        if not rail_ids:
            checkpoint = item.get('checkpoint')
            if checkpoint:
                rail_ids = [checkpoint] if any(step['id'] == checkpoint for step in rail) else []
            elif parent is None:
                rail_ids = [step['id'] for step in rail]
        members = [_member(step) for step in rail if step['id'] in rail_ids]
        flags = []
        tone = 'reversible'
        for step in rail:
            if step['id'] not in rail_ids:
                continue
            for flag in step.get('irreversible') or []:
                if flag not in flags:
                    flags.append(flag)
            candidate = _tone(step)
            if candidate == 'billable' or (candidate == 'irreversible' and tone == 'reversible'):
                tone = candidate
        nodes[aid] = _subject(
            aid, parent, label, role, tone,
            item.get('status') or session.get('status') or 'running',
            rail_ids=rail_ids, entry=item.get('entry'),
            function=item.get('function') or label, members=members, flags=flags,
        )
    roots = [node['id'] for node in nodes.values() if not node['parent']]
    if len(roots) != 1:
        raise ValueError('agents must form one tree')
    children = {nid: [] for nid in nodes}
    for node in nodes.values():
        if node['parent'] and node['parent'] not in nodes:
            raise ValueError('agent parent is unknown')
        if node['parent']:
            children[node['parent']].append(node['id'])

    def _walk(nid, stack):
        if nid in stack:
            raise ValueError('agent tree has a cycle')
        nxt = stack | {nid}
        for child in children[nid]:
            _walk(child, nxt)

    _walk(roots[0], set())
    edges = [
        _edge(node['parent'], node['id'], 'spawn')
        for node in nodes.values() if node['parent']
    ]
    groups = []
    for index, node in enumerate(nodes.values(), start=1):
        if node['id'] == roots[0]:
            continue
        groups.append({
            'id': 'wg_%s' % index,
            'label': node['function'] or node['label'],
            'source': 'agent',
            'tone': node['tone'],
            'color': _color(node['tone']),
            'member_node_ids': [node['id']],
            'rail_ids': node['rail_ids'],
        })
    return {
        'kind': 'agent_tree',
        'root': roots[0],
        'nodes': list(nodes.values()),
        'edges': edges,
        'groups': groups,
    }


def _cost_from_steps(steps):
    flags = []
    hi3d = 0
    mdf = 0
    for step in steps:
        for flag in step.get('billable') or []:
            if flag not in flags:
                flags.append(flag)
            if flag == 'hi3d.submit':
                hi3d += 1
            elif flag == 'mdf.invoke':
                mdf += 1
    return {
        'hi3d_submit_count': hi3d,
        'mdf_invoke_count': mdf,
        'flags': flags,
    }


def _member(step):
    return {
        'id': step['id'],
        'say': step.get('say') or step['id'],
        'state': step.get('state'),
        'tone': _tone(step),
        'billable': list(step.get('billable') or []),
        'resume_allowed': bool(step.get('resume_allowed')),
        'cost': _cost_from_steps([step]),
    }


def _edge(src, dst, kind):
    return {'from': src, 'to': dst, 'kind': kind}


def _annotate_graph(overview, rail):
    by_rail = {step['id']: step for step in rail}
    for node in overview['nodes']:
        steps = [by_rail[cid] for cid in node.get('rail_ids') or [] if cid in by_rail]
        node['cost'] = _cost_from_steps(steps)
        if not node.get('members'):
            node['members'] = [_member(step) for step in steps]
    by_node = {node['id']: node for node in overview['nodes']}
    annotated = []
    for edge in overview.get('edges') or []:
        target = by_node.get(edge.get('to')) or {}
        cost = target.get('cost') or _cost_from_steps([])
        annotated.append({
            'from': edge['from'],
            'to': edge['to'],
            'kind': edge.get('kind'),
            'tone': target.get('tone'),
            'color': target.get('color'),
            'cost': cost,
        })
    overview['edges'] = annotated
    return overview


def _color(tone):
    return COLOR_PLACEHOLDERS[tone]


def _subject(node_id, parent, label, role, tone, state, *, rail_ids, entry=None,
             function=None, members=None, flags=None):
    if tone not in TONES:
        raise ValueError('invalid tone')
    return {
        'id': node_id,
        'parent': parent,
        'label': label,
        'role': role,
        'function': function or label,
        'tone': tone,
        'color': _color(tone),
        'state': state,
        'entry': entry,
        'rail_ids': list(rail_ids or []),
        'members': list(members or []),
        'flags': list(flags or []),
    }


def _node_states(chain, current, session_status):
    states = {}
    if not chain:
        return states
    if session_status == 'completed':
        return {nid: 'done' for nid in chain}
    if current not in chain:
        index = 0 if session_status == 'running' else -1
    else:
        index = chain.index(current)
    for i, nid in enumerate(chain):
        if index < 0:
            states[nid] = 'pending'
        elif i < index:
            states[nid] = 'done'
        elif i == index:
            if session_status == 'waiting_choice':
                states[nid] = 'waiting_choice'
            elif session_status == 'failed':
                states[nid] = 'failed'
            else:
                states[nid] = 'running'
        else:
            states[nid] = 'pending'
    return states


def _schemes(choices, route_list, by_id):
    routes = {item.get('id'): list(item.get('nodes') or []) for item in route_list}
    schemes = []
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        if choice.get('route') in routes:
            nodes = routes[choice['route']]
            kind = 'route'
            target = choice['route']
        elif choice.get('rollback_to') in by_id:
            nodes = []
            kind = 'rollback'
            target = choice['rollback_to']
        else:
            continue
        submits = []
        for nid in nodes:
            flags = [flag for flag in (by_id[nid].get('irreversible') or []) if flag in BILLABLE]
            if flags:
                submits.append({'checkpoint': nid, 'flags': flags})
        schemes.append({
            'id': choice.get('id'),
            'title': choice.get('title'),
            'kind': kind,
            'target': target,
            'billable_steps': submits,
            'hi3d_submit_count': sum(1 for item in submits if 'hi3d.submit' in item['flags']),
            'mdf_invoke_count': sum(1 for item in submits if 'mdf.invoke' in item['flags']),
        })
    return schemes
