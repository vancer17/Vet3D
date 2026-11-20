"""Package-external agent session document. Never write this file into a skill pack."""
from __future__ import annotations

SCHEMA = 'pcg.session.v1'
STATUSES = {'running', 'waiting_choice', 'completed', 'failed', 'interrupted'}
STREAM_STATUSES = {'idle', 'in_flight', 'incomplete', 'settled'}
SIGNED_MARKERS = ('X-Amz-Signature', 'X-Amz-Credential', 'Signature=')
HI3D_IDENTITIES = {'standard', 'member'}
HI3D_SURFACES = {'agent', 'web'}
HI3D_KINDS = {'text-to-image', 'model', 'relief', 'split', 'multicolor', 'image-edit'}
HI3D_STAGES = {'parameters', 'billing', 'route'}
HI3D_GRANT_SCOPES = {'once', 'conversation'}
HI3D_IRREVERSIBLE = 'hi3d.submit'


def new_session(entry, *, task_id, route='main', checkpoint=None):
    """Return an empty session mapping for a package-external task directory."""
    if not entry or not task_id:
        raise ValueError('entry and task_id are required')
    return {
        'schema': SCHEMA,
        'task_id': task_id,
        'entry': entry,
        'route': route,
        'checkpoint': checkpoint,
        'status': 'running',
        'choices': [],
        'artifacts': [],
        'refs': [],
        'service_jobs': [],
        'timing_log': None,
        'popup_reasons': [],
        'injected': [],
        'stream': _empty_stream(),
        'confirmations': [],
    }


def append_artifact(session, *, path, task=None, output=None, href=None, digest=None, tool=None, at=None):
    """Append an add/sync trace onto a session artifact slot. Never deletes history.

    `digest` is an optional content hash string (not an auth token). `href` is a
    task-relative path or stable link; signed or credential URLs are rejected.
    """
    validate_session(session)
    if not isinstance(path, str) or not path:
        raise ValueError('artifact path is required')
    if (task is None) != (output is None):
        raise ValueError('artifact task and output must be set together')
    if task is not None and (not isinstance(task, str) or not isinstance(output, str) or not task or not output):
        raise ValueError('artifact task and output must be strings')
    if href is not None:
        _reject_secret_href(href)
    if digest is not None and not isinstance(digest, str):
        raise ValueError('artifact digest must be a hex digest string')
    event = {
        'op': 'add',
        'path': path,
        'href': href,
        'digest': digest,
        'tool': tool,
        'at': at,
    }
    items = session['artifacts']
    index = _slot_index(items, task=task, output=output, path=path)
    if index is None:
        items.append({
            'path': path,
            'href': href,
            'hash': digest,
            'task': task,
            'output': output,
            'tool': tool,
            'purged': False,
            'traces': [event],
        })
        return validate_session(session)
    current = items[index]
    event['op'] = 'sync'
    traces = list(current.get('traces') or [])
    traces.append(event)
    current['path'] = path
    current['href'] = href if href is not None else current.get('href')
    current['purged'] = False
    if digest is not None:
        current['hash'] = digest
    if tool is not None:
        current['tool'] = tool
    current['traces'] = traces
    if task is not None:
        current['task'] = task
        current['output'] = output
    return validate_session(session)


def apply_tool_result(session, result):
    """Copy short tool-result artifacts onto the session board slots."""
    if not isinstance(result, dict):
        raise ValueError('tool result must be a mapping')
    for item in result.get('artifacts') or []:
        if isinstance(item, str):
            append_artifact(session, path=item)
            continue
        if not isinstance(item, dict) or not item.get('path'):
            raise ValueError('artifact needs a path')
        append_artifact(
            session,
            path=item['path'],
            task=item.get('task'),
            output=item.get('output'),
            href=item.get('href'),
            digest=item.get('hash') or item.get('digest'),
            tool=item.get('tool'),
            at=item.get('at'),
        )
    return session


def mark_purged(session, *, task=None, output=None, path=None, at=None):
    """Record a cache purge. Last path stays in traces so the board can still find it."""
    validate_session(session)
    index = _slot_index(session['artifacts'], task=task, output=output, path=path or '')
    if index is None:
        raise ValueError('artifact slot is unknown')
    current = session['artifacts'][index]
    traces = list(current.get('traces') or [])
    traces.append({
        'op': 'purge',
        'path': current.get('path') or path,
        'href': current.get('href'),
        'digest': current.get('hash'),
        'tool': None,
        'at': at,
    })
    current['traces'] = traces
    current['purged'] = True
    return validate_session(session)


def purge_under_root(session, targets, *, task_root):
    """Delete selected cache files under task_root, then mark slots purged.

    Targets come from architecture_ir.select_purge. keep slots must not appear.
    Last known path remains in traces. Directories are not removed.
    """
    from pathlib import Path
    root = Path(task_root).resolve()
    if not isinstance(targets, list):
        raise ValueError('purge targets must be a list')
    removed = []
    for item in targets:
        if not isinstance(item, dict) or not item.get('path'):
            raise ValueError('purge target needs a path')
        if item.get('retain') == 'keep':
            raise ValueError('keep artifacts cannot be purged')
        candidate = Path(item['path'])
        located = root / item['path'] if not candidate.is_absolute() else candidate.resolve()
        if root not in located.parents and located != root:
            raise ValueError('purge path escapes task_root: ' + item['path'])
        if located.is_file():
            located.unlink()
            removed.append(str(located))
        mark_purged(
            session,
            task=item.get('task'),
            output=item.get('output'),
            path=None if item.get('task') else item.get('path'),
        )
    return removed


def validate_session(document):
    if not isinstance(document, dict) or document.get('schema') != SCHEMA:
        raise ValueError('session schema must be ' + SCHEMA)
    for key in ('task_id', 'entry', 'route', 'status'):
        if not isinstance(document.get(key), str) or not document[key]:
            raise ValueError('session missing ' + key)
    if document['status'] not in STATUSES:
        raise ValueError('invalid session status')
    if document.get('checkpoint') is not None and not isinstance(document['checkpoint'], str):
        raise ValueError('checkpoint must be a string or null')
    for field in ('choices', 'artifacts', 'service_jobs'):
        if not isinstance(document.get(field), list):
            raise ValueError(field + ' must be a list')
    refs = document.get('refs')
    if refs is None:
        document['refs'] = []
    elif not isinstance(refs, list):
        raise ValueError('refs must be a list')
    reasons = document.get('popup_reasons')
    if reasons is None:
        document['popup_reasons'] = []
    elif not isinstance(reasons, list):
        raise ValueError('popup_reasons must be a list')
    for item in document['popup_reasons']:
        _validate_popup_reason(item)
    injected = document.get('injected')
    if injected is None:
        document['injected'] = []
    elif not isinstance(injected, list):
        raise ValueError('injected must be a list')
    for item in document['injected']:
        _validate_injected_path(item)
    stream = document.get('stream')
    if stream is None:
        document['stream'] = _empty_stream()
    else:
        _validate_stream(stream)
    _validate_hi3d_options(document)
    _validate_waiting_context(document)
    _validate_confirmations(document)
    for artifact in document['artifacts']:
        _validate_artifact(artifact)
    for item in document['refs']:
        _validate_ref(item)
    return document


def _validate_hi3d_options(document):
    options = document.get('hi3d_options')
    if options is None:
        return
    if not isinstance(options, dict):
        raise ValueError('hi3d_options must be a mapping')
    identity = options.get('identity', 'standard')
    surface = options.get('surface', 'agent')
    kind = options.get('kind')
    stage = options.get('stage')
    if identity not in HI3D_IDENTITIES:
        raise ValueError('hi3d_options.identity must be standard or member')
    if surface not in HI3D_SURFACES:
        raise ValueError('hi3d_options.surface must be agent or web')
    if kind is not None and kind not in HI3D_KINDS:
        raise ValueError('hi3d_options.kind is unsupported')
    if stage is not None and stage not in HI3D_STAGES:
        raise ValueError('hi3d_options.stage must be parameters, billing or route')
    selected = options.get('selected')
    if selected is not None and not isinstance(selected, dict):
        raise ValueError('hi3d_options.selected must be a mapping')
    by_kind = options.get('selected_by_kind')
    if by_kind is None:
        return
    if not isinstance(by_kind, dict):
        raise ValueError('hi3d_options.selected_by_kind must be a mapping')
    for key, value in by_kind.items():
        if key not in HI3D_KINDS:
            raise ValueError('hi3d_options.selected_by_kind has unsupported kind')
        if not isinstance(value, dict):
            raise ValueError('selected_by_kind values must be mappings')


def _validate_waiting_context(document):
    context = document.get('waiting_context')
    if context is None:
        return
    if not isinstance(context, dict):
        raise ValueError('waiting_context must be a mapping')
    stage = context.get('stage')
    if stage is not None and stage not in HI3D_STAGES:
        raise ValueError('waiting_context.stage must be parameters, billing or route')
    reason = context.get('reason')
    if reason is not None and not isinstance(reason, str):
        raise ValueError('waiting_context.reason must be a string')
    checkpoint = context.get('checkpoint')
    if checkpoint is not None and not isinstance(checkpoint, str):
        raise ValueError('waiting_context.checkpoint must be a string')


def _validate_confirmations(document):
    items = document.get('confirmations')
    if items is None:
        document['confirmations'] = []
        return
    if not isinstance(items, list):
        raise ValueError('confirmations must be a list')
    for item in items:
        if not isinstance(item, dict):
            raise ValueError('confirmation must be a mapping')
        scope = item.get('scope')
        if scope not in HI3D_GRANT_SCOPES:
            raise ValueError('confirmation.scope must be once or conversation')
        flags = item.get('irreversible') or [HI3D_IRREVERSIBLE]
        if not isinstance(flags, list) or HI3D_IRREVERSIBLE not in flags:
            raise ValueError('confirmation.irreversible must include hi3d.submit')
        for flag in flags:
            if not isinstance(flag, str) or not flag:
                raise ValueError('confirmation.irreversible items must be strings')
        if item.get('consumed') not in (None, True, False):
            raise ValueError('confirmation.consumed must be a boolean')
        if item.get('revoked') not in (None, True, False):
            raise ValueError('confirmation.revoked must be a boolean')
        if item.get('at') is not None and not isinstance(item['at'], str):
            raise ValueError('confirmation.at must be a string or null')


def hi3d_waiting_stage(session):
    """Return parameters/billing/route or None."""
    validate_session(session)
    context = session.get('waiting_context') or {}
    if context.get('stage') in HI3D_STAGES:
        return context['stage']
    options = session.get('hi3d_options') or {}
    if options.get('stage') in HI3D_STAGES:
        return options['stage']
    return None


def hi3d_selected_for(session, kind):
    validate_session(session)
    options = session.get('hi3d_options') or {}
    by_kind = options.get('selected_by_kind') or {}
    if kind in by_kind:
        return dict(by_kind[kind])
    if options.get('kind') == kind and isinstance(options.get('selected'), dict):
        return dict(options['selected'])
    return {}


def hi3d_conversation_granted(session):
    """True when this conversation already allowed all further Hi3D billing submits."""
    validate_session(session)
    for item in session.get('confirmations') or []:
        if item.get('scope') != 'conversation':
            continue
        if item.get('revoked'):
            continue
        flags = item.get('irreversible') or [HI3D_IRREVERSIBLE]
        if HI3D_IRREVERSIBLE in flags:
            return True
    return False


def hi3d_once_available(session):
    validate_session(session)
    for item in session.get('confirmations') or []:
        if item.get('scope') != 'once':
            continue
        if item.get('revoked') or item.get('consumed'):
            continue
        flags = item.get('irreversible') or [HI3D_IRREVERSIBLE]
        if HI3D_IRREVERSIBLE in flags:
            return True
    return False


def begin_hi3d_waiting(session, *, checkpoint, kind, stage, reason='billable'):
    """Park the session on the Hi3D parameter or billing popup. Does not submit."""
    validate_session(session)
    if stage not in ('parameters', 'billing'):
        raise ValueError('Hi3D waiting stage must be parameters or billing')
    if kind not in HI3D_KINDS:
        raise ValueError('hi3d_options.kind is unsupported')
    if not isinstance(checkpoint, str) or not checkpoint:
        raise ValueError('checkpoint is required')
    session['status'] = 'waiting_choice'
    session['checkpoint'] = checkpoint
    session['waiting_context'] = {'reason': reason, 'checkpoint': checkpoint, 'stage': stage}
    options = dict(session.get('hi3d_options') or {})
    options['kind'] = kind
    options['stage'] = stage
    session['hi3d_options'] = options
    return validate_session(session)


def record_hi3d_selected(session, *, kind, selected):
    """Store popup ids for one kind after the parameter panel. Stay on waiting_choice."""
    validate_session(session)
    if kind not in HI3D_KINDS:
        raise ValueError('hi3d_options.kind is unsupported')
    if not isinstance(selected, dict):
        raise ValueError('selected must be a mapping')
    options = dict(session.get('hi3d_options') or {})
    by_kind = dict(options.get('selected_by_kind') or {})
    by_kind[kind] = dict(selected)
    options['kind'] = kind
    options['selected'] = dict(selected)
    options['selected_by_kind'] = by_kind
    options['stage'] = 'billing'
    session['hi3d_options'] = options
    context = dict(session.get('waiting_context') or {})
    context['stage'] = 'billing'
    context['reason'] = context.get('reason') or 'billable'
    if session.get('checkpoint'):
        context['checkpoint'] = session['checkpoint']
    session['waiting_context'] = context
    session['status'] = 'waiting_choice'
    return validate_session(session)


def grant_hi3d(session, *, scope, at=None):
    """Record once or conversation consent. Conversation covers later Hi3D submits."""
    validate_session(session)
    if scope not in HI3D_GRANT_SCOPES:
        raise ValueError('confirmation.scope must be once or conversation')
    if scope == 'conversation' and hi3d_conversation_granted(session):
        session['status'] = 'running'
        session['waiting_context'] = None
        options = dict(session.get('hi3d_options') or {})
        options.pop('stage', None)
        session['hi3d_options'] = options
        return validate_session(session)
    session.setdefault('confirmations', []).append({
        'scope': scope,
        'irreversible': [HI3D_IRREVERSIBLE],
        'consumed': False,
        'revoked': False,
        'at': at,
    })
    session['status'] = 'running'
    session['waiting_context'] = None
    options = dict(session.get('hi3d_options') or {})
    options.pop('stage', None)
    session['hi3d_options'] = options
    return validate_session(session)


def consume_hi3d_once(session):
    """Mark an unused once-grant as spent after a real submit. Conversation grants stay."""
    validate_session(session)
    for item in session.get('confirmations') or []:
        if item.get('scope') != 'once' or item.get('revoked') or item.get('consumed'):
            continue
        flags = item.get('irreversible') or [HI3D_IRREVERSIBLE]
        if HI3D_IRREVERSIBLE not in flags:
            continue
        item['consumed'] = True
        return validate_session(session)
    return session


def revoke_hi3d_grants(session):
    """User cancel before submit. Keep selected parameters; do not POST."""
    validate_session(session)
    for item in session.get('confirmations') or []:
        if item.get('consumed'):
            continue
        item['revoked'] = True
    session['status'] = 'waiting_choice'
    options = dict(session.get('hi3d_options') or {})
    options['stage'] = 'parameters'
    session['hi3d_options'] = options
    context = dict(session.get('waiting_context') or {})
    context['stage'] = 'parameters'
    context['reason'] = context.get('reason') or 'billable'
    session['waiting_context'] = context
    return validate_session(session)


def hi3d_submit_ready(session, *, kind=None):
    """Whether a networked Hi3D submit is allowed from session grants alone."""
    validate_session(session)
    if hi3d_conversation_granted(session) or hi3d_once_available(session):
        return True
    return False


def _validate_artifact(artifact):
    if not isinstance(artifact, dict) or not artifact.get('path'):
        raise ValueError('artifact needs a path')
    if artifact.get('hash') is not None and not isinstance(artifact['hash'], str):
        raise ValueError('artifact.hash must be a hex digest string')
    href = artifact.get('href')
    if href is not None:
        _reject_secret_href(href)
    task = artifact.get('task')
    output = artifact.get('output')
    if (task is None) != (output is None):
        raise ValueError('artifact task and output must be set together')
    traces = artifact.get('traces') or []
    if traces and not isinstance(traces, list):
        raise ValueError('artifact traces must be a list')
    for event in traces:
        if not isinstance(event, dict) or event.get('op') not in ('add', 'sync', 'purge'):
            raise ValueError('trace op must be add, sync or purge')
        if not isinstance(event.get('path'), str) or not event['path']:
            raise ValueError('trace needs a path')
        if event.get('href') is not None:
            _reject_secret_href(event['href'])


def asked_popup_reasons(session, checkpoint):
    """Return reason ids already shown at this checkpoint."""
    validate_session(session)
    found = []
    for item in session.get('popup_reasons') or []:
        if item.get('checkpoint') == checkpoint:
            found.append(item['reason'])
    return found


def mark_popup_reason(session, *, reason, checkpoint, at=None):
    """Record that this checkpoint already showed `reason`. Duplicate pairs are ignored."""
    validate_session(session)
    if not isinstance(reason, str) or not reason:
        raise ValueError('popup reason is required')
    if not isinstance(checkpoint, str) or not checkpoint:
        raise ValueError('popup checkpoint is required')
    for item in session['popup_reasons']:
        if item.get('reason') == reason and item.get('checkpoint') == checkpoint:
            return session
    session['popup_reasons'].append({'reason': reason, 'checkpoint': checkpoint, 'at': at})
    return validate_session(session)


def pending_inject(session, load):
    """Return checkpoint load paths not yet injected this compact window."""
    validate_session(session)
    if not isinstance(load, list) or any(not isinstance(item, str) or not item for item in load):
        raise ValueError('load must be a list of paths')
    seen = set(session['injected'])
    return [item for item in load if item not in seen]


def mark_injected(session, paths):
    """Record package-relative files already placed in the model context. Duplicates ignored."""
    validate_session(session)
    if isinstance(paths, str):
        paths = [paths]
    if not isinstance(paths, list):
        raise ValueError('injected paths must be a list')
    known = set(session['injected'])
    for item in paths:
        _validate_injected_path(item)
        if item not in known:
            session['injected'].append(item)
            known.add(item)
    return validate_session(session)


def clear_injected(session):
    """Drop inject memo after token compact so the next turn may re-send a short delta."""
    validate_session(session)
    session['injected'] = []
    return validate_session(session)


def mark_stream(session, *, status, response_id=None, reason=None):
    """Record QueryEngine stream lifecycle. Incomplete is not a failed task."""
    validate_session(session)
    if status not in STREAM_STATUSES:
        raise ValueError('stream status must be idle|in_flight|incomplete|settled')
    if response_id is not None and (not isinstance(response_id, str) or not response_id):
        raise ValueError('stream response_id must be a non-empty string')
    if reason is not None and not isinstance(reason, str):
        raise ValueError('stream reason must be a string')
    current = dict(session.get('stream') or _empty_stream())
    current['status'] = status
    if response_id is not None:
        current['response_id'] = response_id
    if status == 'idle':
        current['response_id'] = None
        current['reason'] = None
    elif reason is not None:
        current['reason'] = reason
    if status == 'settled':
        current['reason'] = None
    session['stream'] = current
    if status == 'incomplete' and session['status'] == 'running':
        session['status'] = 'interrupted'
    return validate_session(session)


def _empty_stream():
    return {'status': 'idle', 'response_id': None, 'reason': None}


def _validate_stream(item):
    if not isinstance(item, dict):
        raise ValueError('stream must be a mapping')
    if item.get('status') not in STREAM_STATUSES:
        raise ValueError('stream status must be idle|in_flight|incomplete|settled')
    if item.get('response_id') is not None and not isinstance(item['response_id'], str):
        raise ValueError('stream response_id must be a string or null')
    if item.get('reason') is not None and not isinstance(item['reason'], str):
        raise ValueError('stream reason must be a string or null')


def _validate_injected_path(item):
    if not isinstance(item, str) or not item or item.startswith('/') or '..' in item.replace('\\', '/').split('/'):
        raise ValueError('injected path must be a package-relative file')
    _reject_secret_href(item)
    return item


def _validate_popup_reason(item):
    if not isinstance(item, dict):
        raise ValueError('popup_reasons item must be a mapping')
    if not isinstance(item.get('reason'), str) or not item['reason']:
        raise ValueError('popup reason is required')
    if not isinstance(item.get('checkpoint'), str) or not item['checkpoint']:
        raise ValueError('popup checkpoint is required')
    if item.get('at') is not None and not isinstance(item['at'], str):
        raise ValueError('popup at must be a string or null')


def _validate_ref(item):
    if not isinstance(item, dict):
        raise ValueError('ref must be a mapping')
    name = item.get('name')
    path = item.get('path')
    if not isinstance(name, str) or not name:
        raise ValueError('ref name is required')
    if not isinstance(path, str) or not path:
        raise ValueError('ref path is required')
    _reject_secret_href(path)
    if item.get('label') is not None and not isinstance(item['label'], str):
        raise ValueError('ref label must be a string')
    if (item.get('task') is None) != (item.get('output') is None):
        raise ValueError('ref task and output must be set together')


def _slot_index(items, *, task, output, path):
    if task is not None:
        for index, item in enumerate(items):
            if item.get('task') == task and item.get('output') == output:
                return index
        return None
    for index, item in enumerate(items):
        if not item.get('task') and item.get('path') == path:
            return index
    return None


def _reject_secret_href(href):
    if not isinstance(href, str) or not href:
        raise ValueError('href must be a non-empty string')
    lowered = href.lower()
    if lowered.startswith('javascript:'):
        raise ValueError('href must not be a script URL')
    if any(marker.lower() in lowered for marker in SIGNED_MARKERS):
        raise ValueError('href must not be a signed URL or credential')
    return href
