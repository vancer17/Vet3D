"""Project pcg.board.v1 into AntV G6 Graph data. Source of truth stays the board."""
from __future__ import annotations

from architecture_ir import SCHEMA as BOARD_SCHEMA

SCHEMA = 'pcg.g6.v1'
# G6 demo names overview/detailed; board lod is preview/detail.
LEVEL = {
    'preview': 'overview',
    'detail': 'detailed',
}
NODE_TYPE = {
    'agent': 'pcg-agent',
    'local': 'pcg-local',
    'subagent': 'pcg-subagent',
    'artifact': 'pcg-artifact',
}
EDGE_TYPE = {
    'spawn': 'polyline',
    'contains': 'polyline',
    'advance': 'polyline',
    'rollback': 'polyline',
    'produces': 'polyline',
}


def board_to_g6(board, *, lod=None):
    """Return G6 5.x `{nodes, edges}` plus our catalog/host_actions.

    Node/edge `data` copies board fields (role, tone, entry, cost, retain…).
    Does not embed AntV org-chart fields (phone, position) or required hex colors.
    """
    if not isinstance(board, dict) or board.get('schema') != BOARD_SCHEMA:
        raise ValueError('board_to_g6 requires pcg.board.v1')
    overview = board.get('overview') or {}
    layout = overview.get('layout') or 'tree'
    if lod is None:
        lod = 'preview' if layout == 'tree' else 'detail'
    if lod not in LEVEL:
        raise ValueError('lod must be preview or detail')
    if layout == 'linear' and lod != 'detail':
        raise ValueError('linear boards only support lod=detail')
    level = LEVEL[lod]
    nodes = []
    for item in overview.get('nodes') or []:
        nid = item.get('id')
        if not nid:
            raise ValueError('board node needs an id')
        role = item.get('role') or 'local'
        payload = _node_data(item, level, lod)
        nodes.append({
            'id': nid,
            'type': NODE_TYPE.get(role, 'pcg-local'),
            'data': payload,
        })
    edges = []
    for item in overview.get('edges') or []:
        src = item.get('from')
        dst = item.get('to')
        kind = item.get('kind') or 'contains'
        if not src or not dst:
            raise ValueError('board edge needs from and to')
        eid = '%s__%s__%s' % (src, kind, dst)
        edges.append({
            'id': eid,
            'source': src,
            'target': dst,
            'type': EDGE_TYPE.get(kind, 'polyline'),
            'data': {
                'kind': kind,
                'tone': item.get('tone'),
                'cost': dict(item.get('cost') or {}),
                'dashed': kind in ('rollback', 'contains', 'produces'),
            },
        })
    return {
        'schema': SCHEMA,
        'source': BOARD_SCHEMA,
        'entry': board.get('entry'),
        'kind': board.get('kind'),
        'layout': layout,
        'lod': lod,
        'g6': {'nodes': nodes, 'edges': edges},
        'graph': {
            'layout': {
                'type': 'dagre',
                'rankdir': 'LR' if layout == 'linear' else 'TB',
            },
            'edge': {'type': 'polyline', 'router': {'type': 'orth'}},
            'behaviors': (
                ['level-of-detail', 'zoom-canvas', 'drag-canvas']
                if layout == 'tree'
                else ['zoom-canvas', 'drag-canvas']
            ),
            'autoFit': 'view',
        },
        'catalog': board.get('catalog') or {'artifacts': []},
        'host_actions': board.get('host_actions') or {},
        'color_catalog': board.get('color_catalog'),
    }


def _node_data(item, level, lod):
    data = {
        'name': item.get('label') or item.get('id'),
        'label': item.get('label') or item.get('id'),
        'role': item.get('role'),
        'function': item.get('function'),
        'entry': item.get('entry'),
        'optional': bool(item.get('optional')),
        'tone': item.get('tone'),
        'flags': list(item.get('flags') or []),
        'cost': dict(item.get('cost') or {}),
        'rollback_to': item.get('rollback_to'),
        'level': level,
        'lod': lod,
    }
    if item.get('role') == 'artifact':
        data.update({
            'output_id': item.get('output_id'),
            'kind': item.get('kind'),
            'retain': item.get('retain'),
            'semantics': list(item.get('semantics') or []),
            'path': item.get('path'),
            'href': item.get('href'),
            'status': item.get('status'),
            'findable': bool(item.get('findable')),
        })
    return data
