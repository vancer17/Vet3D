"""Render decision overview (--routes) or execution architecture board (--architecture)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from architecture_ir import compose_board, locate_board, select_purge
from html_view import html_document
from view_ir import compose_view


def render_view(routes, session=None, *, format='json'):
    view = compose_view(routes, session=session)
    if format == 'html':
        return html_document(view)
    if format == 'svg':
        from svg_overview import svg_layers
        return svg_layers(view)
    if format == 'json':
        return json.dumps(view, ensure_ascii=False, indent=2) + '\n'
    if format == 'g6':
        raise ValueError('g6 format is only for --architecture boards')
    raise ValueError('format must be json|html|svg|g6')


def render_board(architecture, session=None, *, format='json', task_root=None, lod=None):
    view = compose_board(architecture, session=session)
    if task_root is not None:
        view = locate_board(view, task_root)
    if format == 'html':
        return html_document(view)
    if format == 'svg':
        from svg_overview import svg_layers
        return svg_layers(view)
    if format == 'g6':
        from g6_graph import board_to_g6
        return json.dumps(board_to_g6(view, lod=lod), ensure_ascii=False, indent=2) + '\n'
    if format == 'json':
        return json.dumps(view, ensure_ascii=False, indent=2) + '\n'
    raise ValueError('format must be json|html|svg|g6')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--routes', type=Path)
    parser.add_argument('--architecture', type=Path)
    parser.add_argument('--session', type=Path)
    parser.add_argument('--task-root', type=Path)
    parser.add_argument('--semantics', action='append', default=[])
    parser.add_argument('--list-purge', action='store_true')
    parser.add_argument('--format', choices=('json', 'html', 'svg', 'g6'), default='html')
    parser.add_argument(
        '--lod',
        choices=('preview', 'detail'),
        help='g6 only: tree preview maps to G6 overview; detail to detailed',
    )
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.architecture and args.routes:
            raise ValueError('use --architecture or --routes, not both')
        if args.architecture:
            architecture = json.loads(args.architecture.read_text())
            session = json.loads(args.session.read_text()) if args.session else None
            if args.list_purge:
                tags = []
                for group in args.semantics:
                    tags.extend(part.strip() for part in group.split(',') if part.strip())
                text = json.dumps(select_purge(architecture, session, semantics=tags), ensure_ascii=False, indent=2) + '\n'
            else:
                text = render_board(
                    architecture, session, format=args.format,
                    task_root=args.task_root, lod=args.lod,
                )
        elif args.routes:
            routes = json.loads(args.routes.read_text())
            session = json.loads(args.session.read_text()) if args.session else None
            text = render_view(routes, session, format=args.format)
        else:
            raise ValueError('provide --architecture or --routes')
    except (ValueError, TypeError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text)
    print(json.dumps({'output': str(args.output), 'format': args.format}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
