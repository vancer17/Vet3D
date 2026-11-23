"""SVG board of billable checkpoints only."""
from __future__ import annotations

from html import escape

WIDTH = 200
HEIGHT = 64
GAP = 48
OX = 24
OY = 24


def layout_board(view):
    if view.get('schema') != 'pcg.view.v1':
        raise ValueError('layout requires pcg.view.v1')
    nodes = {}
    for index, item in enumerate(view.get('board') or []):
        nodes[item['id']] = {'x': OX + index * (WIDTH + GAP), 'y': OY, 'w': WIDTH, 'h': HEIGHT}
    width = OX
    height = OY + HEIGHT + OY
    for box in nodes.values():
        width = max(width, box['x'] + box['w'] + OX)
        height = max(height, box['y'] + box['h'] + OY)
    if not nodes:
        width, height = 320, 80
    return {'nodes': nodes, 'width': width, 'height': height}


def svg_board(view):
    placed = layout_board(view)
    boxes = placed['nodes']
    items = list(view.get('board') or [])
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %s %s" width="%s" height="%s">'
        % (placed['width'], placed['height'], placed['width'], placed['height']),
        '<rect width="100%" height="100%" fill="#0e100f"/>',
    ]
    for left, right in zip(items, items[1:]):
        a, b = boxes[left['id']], boxes[right['id']]
        parts.append(
            '<path d="M %s %s C %s %s, %s %s, %s %s" fill="none" stroke="#5a635c" stroke-width="1.5"/>'
            % (a['x'] + a['w'], a['y'] + a['h'] / 2, a['x'] + a['w'] + 28, a['y'] + a['h'] / 2,
               b['x'] - 28, b['y'] + b['h'] / 2, b['x'], b['y'] + b['h'] / 2)
        )
    for item in items:
        box = boxes[item['id']]
        parts.append(
            '<g data-id="%s" data-billable="1">'
            '<rect x="%s" y="%s" width="%s" height="%s" rx="8" fill="#1a241c" stroke="#5ee06a" stroke-width="1.4"/>'
            '<text x="%s" y="%s" fill="#d5ddd6" font-size="12" font-family="ui-sans-serif,system-ui">%s</text>'
            '<text x="%s" y="%s" fill="#8b958d" font-size="10" font-family="ui-sans-serif,system-ui">%s</text>'
            '</g>'
            % (
                escape(item['id']), box['x'], box['y'], box['w'], box['h'],
                box['x'] + 12, box['y'] + 26, escape(item['say']),
                box['x'] + 12, box['y'] + 46, escape('+'.join(item['billable'])),
            )
        )
    if not items:
        parts.append('<text x="24" y="44" fill="#8b958d" font-size="12" font-family="ui-sans-serif,system-ui">本路线无计费提交</text>')
    parts.append('</svg>')
    return ''.join(parts)
