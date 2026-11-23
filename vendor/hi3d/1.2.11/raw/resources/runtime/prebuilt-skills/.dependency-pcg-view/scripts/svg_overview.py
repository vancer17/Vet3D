"""SVG org-chart of overview subjects. Color is tone, not a second stage list."""
from __future__ import annotations

from html import escape

NODE_W = 168
NODE_H = 56
GAP_X = 28
GAP_Y = 72
OX = 24
OY = 24


def layout_overview(view):
    if view.get('schema') not in ('pcg.view.v1', 'pcg.board.v1'):
        raise ValueError('layout requires pcg.view.v1 or pcg.board.v1')
    overview = view.get('overview') or {}
    if view.get('schema') == 'pcg.board.v1' and overview.get('layout') == 'linear':
        return _layout_linear(overview)
    nodes = list(overview.get('nodes') or [])
    if not nodes:
        return {'nodes': {}, 'width': 320, 'height': 80, 'children': {}, 'rollback': []}
    children = {item['id']: [] for item in nodes}
    by_id = {}
    for item in nodes:
        by_id[item['id']] = item
        parent = item.get('parent')
        if parent:
            children.setdefault(parent, []).append(item['id'])
            children.setdefault(item['id'], [])
    root = overview.get('root')
    if root not in by_id:
        raise ValueError('overview root is missing')
    widths = {}

    def subtree_width(node_id):
        kids = children.get(node_id) or []
        if not kids:
            widths[node_id] = NODE_W
            return NODE_W
        total = sum(subtree_width(kid) for kid in kids) + GAP_X * (len(kids) - 1)
        widths[node_id] = max(NODE_W, total)
        return widths[node_id]

    subtree_width(root)
    placed = {}

    def place(node_id, left, depth):
        kids = children.get(node_id) or []
        width = widths[node_id]
        x = left + (width - NODE_W) / 2
        y = OY + depth * (NODE_H + GAP_Y)
        placed[node_id] = {'x': x, 'y': y, 'w': NODE_W, 'h': NODE_H}
        cursor = left
        for kid in kids:
            place(kid, cursor, depth + 1)
            cursor += widths[kid] + GAP_X

    place(root, OX, 0)
    width = OX
    height = OY
    for box in placed.values():
        width = max(width, box['x'] + box['w'] + OX)
        height = max(height, box['y'] + box['h'] + OY)
    return {'nodes': placed, 'children': children, 'width': width, 'height': height, 'rollback': []}


def _layout_linear(overview):
    nodes = list(overview.get('nodes') or [])
    if not nodes:
        return {'nodes': {}, 'width': 320, 'height': 80, 'children': {}, 'rollback': []}
    by_id = {item['id']: item for item in nodes}
    children = {item['id']: [] for item in nodes}
    for item in nodes:
        parent = item.get('parent')
        if parent:
            children.setdefault(parent, []).append(item['id'])
            children.setdefault(item['id'], [])
    root = overview.get('root')
    if root not in by_id:
        raise ValueError('overview root is missing')
    stages = [root]
    cur = root
    while True:
        nxt = [kid for kid in (children.get(cur) or []) if by_id.get(kid, {}).get('role') != 'artifact']
        if not nxt:
            break
        stages.append(nxt[0])
        cur = nxt[0]
    placed = {}
    for index, nid in enumerate(stages):
        placed[nid] = {
            'x': OX + index * (NODE_W + GAP_X),
            'y': OY,
            'w': NODE_W,
            'h': NODE_H,
        }
    for parent_id in stages:
        arts = [kid for kid in (children.get(parent_id) or []) if by_id.get(kid, {}).get('role') == 'artifact']
        for offset, nid in enumerate(arts):
            parent = placed[parent_id]
            placed[nid] = {
                'x': parent['x'] + offset * 12,
                'y': OY + NODE_H + GAP_Y,
                'w': NODE_W,
                'h': NODE_H,
            }
    rollback = [
        (edge.get('from'), edge.get('to'))
        for edge in overview.get('edges') or []
        if edge.get('kind') == 'rollback'
    ]
    width = OX
    height = OY
    for box in placed.values():
        width = max(width, box['x'] + box['w'] + OX)
        height = max(height, box['y'] + box['h'] + OY + 28)
    return {'nodes': placed, 'children': children, 'width': width, 'height': height, 'rollback': rollback}


def svg_overview(view):
    overview = view.get('overview') or {}
    by_id = {item['id']: item for item in overview.get('nodes') or []}
    placed = layout_overview(view)
    boxes = placed['nodes']
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" class="%s" viewBox="0 0 %s %s" width="%s" height="%s">'
        % (
            'tree-glyphs' if view.get('schema') == 'pcg.board.v1' and (overview.get('layout') or 'tree') != 'linear' else 'board-svg',
            placed['width'],
            placed['height'] + (28 if view.get('schema') == 'pcg.board.v1' and (overview.get('layout') or 'tree') != 'linear' else 0),
            placed['width'],
            placed['height'] + (28 if view.get('schema') == 'pcg.board.v1' and (overview.get('layout') or 'tree') != 'linear' else 0),
        ),
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    layout = (overview.get('layout') or '')
    if layout == 'linear':
        for edge in overview.get('edges') or []:
            src = boxes.get(edge.get('from'))
            dst = boxes.get(edge.get('to'))
            if not src or not dst:
                continue
            kind = edge.get('kind')
            if kind == 'rollback':
                continue
            x1 = src['x'] + src['w']
            y1 = src['y'] + src['h'] / 2
            x2 = dst['x']
            y2 = dst['y'] + dst['h'] / 2
            if kind == 'produces':
                x1 = src['x'] + src['w'] / 2
                y1 = src['y'] + src['h']
                x2 = dst['x'] + dst['w'] / 2
                y2 = dst['y']
            parts.append(
                '<path d="M %s %s L %s %s" fill="none" stroke="#d5d0c8" stroke-width="1.4"/>'
                % (x1, y1, x2, y2)
            )
            label = _edge_label(view, edge.get('from'), edge.get('to'))
            if label:
                parts.append(
                    '<text x="%s" y="%s" fill="#6b6460" font-size="10" text-anchor="middle" font-family="ui-sans-serif,system-ui">%s</text>'
                    % ((x1 + x2) / 2, (y1 + y2) / 2, escape(label))
                )
    else:
        for parent_id, kids in (placed.get('children') or {}).items():
            if not kids or parent_id not in boxes:
                continue
            parent = boxes[parent_id]
            px = parent['x'] + parent['w'] / 2
            py = parent['y'] + parent['h']
            mid_y = py + GAP_Y / 2
            xs = [boxes[kid]['x'] + boxes[kid]['w'] / 2 for kid in kids if kid in boxes]
            if not xs:
                continue
            parts.append(
                '<path d="M %s %s L %s %s" fill="none" stroke="#d5d0c8" stroke-width="1.4"/>'
                % (px, py, px, mid_y)
            )
            parts.append(
                '<path d="M %s %s L %s %s" fill="none" stroke="#d5d0c8" stroke-width="1.4"/>'
                % (min(xs), mid_y, max(xs), mid_y)
            )
            for kid in kids:
                if kid not in boxes:
                    continue
                cx = boxes[kid]['x'] + boxes[kid]['w'] / 2
                cy = boxes[kid]['y']
                stroke, width, dash = _edge_stroke(view, parent_id, kid)
                extra = ' stroke-dasharray="%s"' % dash if dash else ''
                parts.append(
                    '<path d="M %s %s L %s %s" fill="none" stroke="%s" stroke-width="%s"%s/>'
                    % (cx, mid_y, cx, cy, stroke, width, extra)
                )
                label = _edge_label(view, parent_id, kid)
                if label:
                    parts.append(
                        '<text class="board-detail" x="%s" y="%s" fill="#6b6460" font-size="10" text-anchor="middle" font-family="ui-sans-serif,system-ui">%s</text>'
                        % (cx, (mid_y + cy) / 2, escape(label))
                    )
    for src, dst in placed.get('rollback') or []:
        if src not in boxes or dst not in boxes:
            continue
        a = boxes[src]
        b = boxes[dst]
        x1 = a['x'] + a['w'] / 2
        x2 = b['x'] + b['w'] / 2
        y = a['y'] - 10
        parts.append(
            '<path d="M %s %s C %s %s %s %s %s %s" fill="none" stroke="#6b6460" stroke-width="1.2" stroke-dasharray="4 3"/>'
            % (x1, a['y'], x1, y, x2, y, x2, b['y'])
        )
        parts.append(
            '<text class="board-detail" x="%s" y="%s" fill="#6b6460" font-size="10" text-anchor="middle" font-family="ui-sans-serif,system-ui">回退</text>'
            % ((x1 + x2) / 2, y - 2)
        )
    tree = view.get('schema') == 'pcg.board.v1' and layout != 'linear'
    for item in overview.get('nodes') or []:
        box = boxes[item['id']]
        fill = item.get('color') or ((view.get('color_catalog') or {}).get('by_tone') or {}).get(
            item.get('tone'), '#9A8F7A')
        subtitle = item.get('function') or item.get('role') or ''
        if item.get('role') == 'artifact':
            name = str(item.get('path') or '待产物').rsplit('/', 1)[-1]
            subtitle = name
        elif item.get('role') == 'subagent' and item.get('entry'):
            subtitle = 'subagent · ' + str(item['entry'])
        elif item.get('flags'):
            subtitle = '+'.join(item['flags'])
        opacity = '0.55' if item.get('optional') else '1'
        glyph = _role_glyph(item.get('role'), box, fill) if tree else (
            '<rect x="%s" y="%s" width="%s" height="%s" rx="6" fill="%s"/>'
            % (box['x'], box['y'], box['w'], box['h'], fill)
        )
        if tree:
            tx = box['x'] + box['w'] / 2
            ty1 = box['y'] + box['h'] + 14
            ty2 = ty1 + 12
            texts = (
                '<text class="board-detail" x="%s" y="%s" fill="#3d3a36" font-size="11" text-anchor="middle" font-family="ui-sans-serif,system-ui">%s</text>'
                '<text class="board-detail" x="%s" y="%s" fill="#6b6460" font-size="10" text-anchor="middle" font-family="ui-sans-serif,system-ui">%s</text>'
                % (
                    tx, ty1, escape(_trim(item.get('label') or item['id'])),
                    tx, ty2, escape(_trim(subtitle, 22)),
                )
            )
        else:
            texts = (
                '<text x="%s" y="%s" fill="#ffffff" font-size="12" font-family="ui-sans-serif,system-ui">%s</text>'
                '<text x="%s" y="%s" fill="#f3f6f4" font-size="10" font-family="ui-sans-serif,system-ui">%s</text>'
                % (
                    box['x'] + 10, box['y'] + 24, escape(_trim(item.get('label') or item['id'])),
                    box['x'] + 10, box['y'] + 42, escape(_trim(subtitle, 22)),
                )
            )
        parts.append(
            '<g data-id="%s" data-tone="%s" data-color="%s" data-role="%s" data-rail="%s" opacity="%s">'
            '%s%s</g>'
            % (
                escape(item['id']),
                escape(str(item.get('tone') or '')),
                escape(str(fill)),
                escape(str(item.get('role') or '')),
                escape(','.join(item.get('rail_ids') or [])),
                opacity,
                glyph,
                texts,
            )
        )
    if not by_id:
        parts.append(
            '<text x="24" y="44" fill="#8b958d" font-size="12" font-family="ui-sans-serif,system-ui">无 overview 主体</text>'
        )
    parts.append('</svg>')
    return ''.join(parts)


def svg_layers(view):
    """Overview tree only; cost is on edges and zoomed members."""
    return svg_overview(view)


def _role_glyph(role, box, fill):
    cx = box['x'] + box['w'] / 2
    cy = box['y'] + box['h'] / 2
    if role == 'artifact':
        return '<rect x="%s" y="%s" width="20" height="20" fill="%s"/>' % (cx - 10, cy - 10, fill)
    if role == 'subagent':
        return (
            '<polygon points="%s,%s %s,%s %s,%s %s,%s" fill="%s"/>'
            % (cx, cy - 18, cx + 18, cy, cx, cy + 18, cx - 18, cy, fill)
        )
    if role == 'local':
        return '<circle cx="%s" cy="%s" r="16" fill="%s"/>' % (cx, cy, fill)
    return '<rect x="%s" y="%s" width="52" height="32" rx="10" fill="%s"/>' % (cx - 26, cy - 16, fill)


def _edge_stroke(view, src, dst):
    kind = ''
    for edge in (view.get('overview') or {}).get('edges') or []:
        if edge.get('from') == src and edge.get('to') == dst:
            kind = edge.get('kind') or ''
            break
    if kind == 'spawn':
        return '#2AA8A4', '2', ''
    if kind == 'produces':
        return '#c4bfb6', '1.2', '3 3'
    return '#d5d0c8', '1.4', ''


def _edge_label(view, src, dst):
    for edge in (view.get('overview') or {}).get('edges') or []:
        if edge.get('from') == src and edge.get('to') == dst:
            cost = edge.get('cost') or {}
            parts = []
            if cost.get('hi3d_submit_count'):
                parts.append('Hi3D×%s' % cost['hi3d_submit_count'])
            if cost.get('mdf_invoke_count'):
                parts.append('MDF×%s' % cost['mdf_invoke_count'])
            if parts:
                return ' '.join(parts)
            if edge.get('kind') == 'spawn':
                return 'spawn'
            if edge.get('kind') == 'rollback':
                return '回退'
            if edge.get('kind') == 'advance':
                return '前进'
            if edge.get('kind') == 'produces' and not parts:
                return '产物'
            return ''
    return ''


def _trim(text, limit=18):
    text = str(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1] + '…'
