"""Validate request fields before the algorithm runs."""
from __future__ import annotations

from pathlib import Path


def field_errors(plan, values, files=None):
    files = files or {}
    errors = {}
    for field in plan.get('fields') or []:
        ident = field['id']
        if field['type'] == 'file':
            upload = files.get(ident)
            if field.get('required') and not upload:
                errors[ident] = field['label'] + '为必填文件'
                continue
            if not upload:
                continue
            name = upload.get('name') or ''
            data = upload.get('data') or b''
            suffixes = field.get('suffixes') or []
            if suffixes and Path(name).suffix.lower() not in [s.lower() for s in suffixes]:
                errors[ident] = field['label'] + '文件类型不受理'
            max_bytes = int(plan['limits']['maxBytes'])
            if len(data) > max_bytes:
                errors[ident] = field['label'] + '超过大小限制'
            continue
        raw = values.get(ident)
        if field.get('required') and (raw is None or raw == ''):
            errors[ident] = field['label'] + '为必填'
            continue
        if raw is None or raw == '':
            continue
        if field['type'] == 'number':
            if isinstance(raw, bool) or type(raw) not in (int, float):
                try:
                    float(raw)
                except (TypeError, ValueError):
                    errors[ident] = field['label'] + '须为数字'
        elif field['type'] == 'boolean':
            if raw not in (True, False, 'true', 'false'):
                errors[ident] = field['label'] + '须为是或否'
        elif field['type'] == 'string' and not isinstance(raw, str):
            errors[ident] = field['label'] + '须为文本'
    return errors


def normalize_values(plan, values):
    out = {}
    for field in plan.get('fields') or []:
        if field['type'] == 'file':
            continue
        raw = values.get(field['id'])
        if raw is None or raw == '':
            continue
        if field['type'] == 'number':
            out[field['id']] = raw if type(raw) in (int, float) and not isinstance(raw, bool) else float(raw)
        elif field['type'] == 'boolean':
            out[field['id']] = raw is True or raw == 'true'
        else:
            out[field['id']] = str(raw)
    return out
