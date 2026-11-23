"""Short tool result returned into the agent loop. Logs stay in the task directory."""
from __future__ import annotations

SCHEMA = 'pcg.tool_result.v1'
STATUSES = {'ok', 'failed', 'skipped'}


def tool_result(*, status, summary, artifacts=None, next_checkpoint=None, irreversible=(), error=None):
    if status not in STATUSES:
        raise ValueError('tool result status must be ok|failed|skipped')
    if not isinstance(summary, str) or not summary or len(summary) > 240:
        raise ValueError('summary must be 1-240 characters')
    payload = {
        'schema': SCHEMA,
        'status': status,
        'summary': summary,
        'artifacts': list(artifacts or []),
        'next_checkpoint': next_checkpoint,
        'irreversible': list(irreversible),
    }
    if error is not None:
        if not isinstance(error, str):
            raise ValueError('error must be a short string')
        payload['error'] = error
    return validate_tool_result(payload)


def validate_tool_result(document):
    if not isinstance(document, dict) or document.get('schema') != SCHEMA:
        raise ValueError('tool result schema must be ' + SCHEMA)
    if document.get('status') not in STATUSES:
        raise ValueError('invalid tool result status')
    if not isinstance(document.get('summary'), str) or not document['summary']:
        raise ValueError('tool result summary is required')
    if not isinstance(document.get('artifacts'), list):
        raise ValueError('artifacts must be a list of paths or slot mappings')
    for item in document['artifacts']:
        if isinstance(item, str):
            if not item:
                raise ValueError('artifact paths must be strings')
            continue
        if not isinstance(item, dict) or not isinstance(item.get('path'), str) or not item['path']:
            raise ValueError('artifact mapping needs a path')
        if (item.get('task') is None) != (item.get('output') is None):
            raise ValueError('artifact task and output must be set together')
        href = item.get('href')
        if href is not None and (not isinstance(href, str) or not href):
            raise ValueError('artifact href must be a non-empty string')
    if document.get('next_checkpoint') is not None and not isinstance(document['next_checkpoint'], str):
        raise ValueError('next_checkpoint must be a string')
    flags = document.get('irreversible') or []
    if not isinstance(flags, list):
        raise ValueError('irreversible must be a list')
    return document
