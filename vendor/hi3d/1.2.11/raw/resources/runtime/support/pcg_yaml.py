"""Minimal YAML subset for pcg/routes.yaml and architecture.yaml. Standard library only."""
from __future__ import annotations

import json
import re


def dump(data):
    return _dump(data, 0).rstrip() + '\n'


def load(text):
    lines = []
    for raw in text.splitlines():
        stripped = raw.split('#', 1)[0].rstrip()
        if stripped.strip():
            lines.append(stripped)
    anchors = {}
    values, index = _parse_block(lines, 0, 0, anchors)
    if index != len(lines):
        raise ValueError('YAML trailing content at line ' + str(index + 1))
    if not isinstance(values, dict):
        raise ValueError('YAML root must be a mapping')
    return values


def _parse_block(lines, index, indent, anchors):
    mapping = {}
    sequence = []
    mode = None
    last_key = None
    last_anchor = None
    while index < len(lines):
        line = lines[index]
        current = len(line) - len(line.lstrip(' '))
        if current < indent:
            break
        if current > indent:
            raise ValueError('YAML indent error: ' + line.strip())
        body = line[indent:]
        if body.startswith('- ') or body == '-':
            if mode == 'map':
                seq, index = _parse_sequence(lines, index, indent, anchors)
                if last_key is None:
                    raise ValueError('YAML mixed mapping and sequence')
                mapping[last_key] = seq
                if last_anchor:
                    anchors[last_anchor] = seq
                    last_anchor = None
                continue
            mode = 'list'
            item, index = _parse_list_item(lines, index, indent, anchors)
            sequence.append(item)
            continue
        if mode == 'list':
            raise ValueError('YAML mixed sequence and mapping')
        mode = 'map'
        key, rest = _split_key(body)
        rest = rest.strip()
        last_anchor = None
        if rest.startswith('&') and ' ' not in rest:
            last_anchor = rest[1:]
            rest = ''
        elif rest.startswith('&') and ' ' in rest:
            last_anchor, rest = rest[1:].split(' ', 1)
        value, index = _parse_entry(lines, index, indent + 2, rest, anchors)
        if isinstance(value, str) and value.startswith('*'):
            value = anchors[value[1:]]
        mapping[key] = value
        last_key = key
        if last_anchor and value not in (None, {}, []):
            anchors[last_anchor] = value
    if mode == 'list':
        return sequence, index
    return mapping, index


def _parse_sequence(lines, index, indent, anchors):
    sequence = []
    while index < len(lines):
        line = lines[index]
        current = len(line) - len(line.lstrip(' '))
        if current != indent:
            break
        body = line[indent:]
        if not (body.startswith('- ') or body == '-'):
            break
        item, index = _parse_list_item(lines, index, indent, anchors)
        sequence.append(item)
    return sequence, index


def _parse_list_item(lines, index, indent, anchors):
    body = lines[index][indent:]
    item_text = '' if body == '-' else body[2:].strip()
    index += 1
    if item_text == '':
        value, index = _parse_block(lines, index, indent + 2, anchors)
        return value, index
    if ':' in item_text:
        key, rest = _split_key(item_text)
        item = {}
        if rest.strip():
            item[key] = _parse_scalar(rest.strip(), anchors)
            nested, index = _parse_block(lines, index, indent + 2, anchors)
            if nested == {}:
                pass
            elif not isinstance(nested, dict):
                raise ValueError('YAML list item expected mapping')
            else:
                item.update(nested)
        else:
            item[key], index = _parse_block(lines, index, indent + 2, anchors)
        return item, index
    return _parse_scalar(item_text, anchors), index


def _parse_entry(lines, index, child_indent, rest, anchors):
    rest = rest.strip()
    index += 1
    if rest == '' or rest == '|':
        if index < len(lines):
            nxt_line = lines[index]
            nxt = len(nxt_line) - len(nxt_line.lstrip(' '))
            if nxt >= child_indent and nxt_line.strip() == '[]':
                return [], index + 1
            if nxt >= child_indent and nxt_line.strip() == '{}':
                return {}, index + 1
            if nxt >= child_indent:
                return _parse_block(lines, index, child_indent, anchors)
        return ({} if rest == '' else ''), index
    return _parse_scalar(rest, anchors), index


def _parse_scalar(text, anchors=None):
    anchors = anchors or {}
    if text.startswith('*'):
        return anchors[text[1:]]
    if text.startswith('&') and ' ' not in text:
        return None
    if text in ('null', '~', ''):
        return None
    if text == 'true':
        return True
    if text == 'false':
        return False
    if re.fullmatch(r'-?\d+', text):
        return int(text)
    if text.startswith('[') and text.endswith(']'):
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip(), anchors) for part in inner.split(',')]
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        return json.loads('"' + text[1:-1].replace('\\', '\\\\').replace('"', '\\"') + '"') if text[0] == "'" else json.loads(text)
    return text


def _dump(value, indent):
    pad = '  ' * indent
    if isinstance(value, dict):
        if not value:
            return pad + '{}\n'
        chunks = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                if not item:
                    chunks.append(pad + str(key) + ': ' + ('[]' if isinstance(item, list) else '{}') + '\n')
                else:
                    chunks.append(pad + str(key) + ':\n' + _dump(item, indent + 1))
            else:
                chunks.append(pad + str(key) + ': ' + _scalar(item) + '\n')
        return ''.join(chunks)
    if isinstance(value, list):
        if not value:
            return pad + '[]\n'
        chunks = []
        for item in value:
            if isinstance(item, dict):
                first = True
                for key, child in item.items():
                    prefix = (pad + '- ') if first else (pad + '  ')
                    first = False
                    if isinstance(child, (dict, list)):
                        if not child:
                            chunks.append(prefix + str(key) + ': ' + ('[]' if isinstance(child, list) else '{}') + '\n')
                        else:
                            chunks.append(prefix + str(key) + ':\n' + _dump(child, indent + 2))
                    else:
                        chunks.append(prefix + str(key) + ': ' + _scalar(child) + '\n')
            elif isinstance(item, list):
                chunks.append(pad + '-\n' + _dump(item, indent + 1))
            else:
                chunks.append(pad + '- ' + _scalar(item) + '\n')
        return ''.join(chunks)
    return pad + _scalar(value) + '\n'


def _scalar(value):
    if value is None:
        return 'null'
    if value is True:
        return 'true'
    if value is False:
        return 'false'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    text = str(value)
    if re.fullmatch(r'[-A-Za-z0-9_./]+', text):
        return text
    return json.dumps(text, ensure_ascii=False)


def _split_key(body):
    if ':' not in body:
        raise ValueError('YAML mapping line needs a colon: ' + body)
    key, rest = body.split(':', 1)
    key = key.strip()
    if not key:
        raise ValueError('YAML empty key')
    return key, rest
