"""Web-aligned Hi3D option catalog. Membership gems; credits do not unlock them."""
from __future__ import annotations

IDENTITIES = ('standard', 'member')
SURFACES = ('agent', 'web')
KINDS = ('text-to-image', 'model', 'relief', 'split', 'multicolor')
GEM = 'diamond'

# Web C-end 2026-09-21: gem = membership. Credits do not unlock gems.
_FREE_IMAGE_MODELS = frozenset({'seedream-v4.5'})
_MEMBER_IMAGE_MODELS = frozenset({'nano-banana-2', 'nano-banana-pro', 'gpt-image-2'})
_FREE_SPLIT_PARTS = frozenset({'a'})
_FREE_SPLIT_TEMPLATES = frozenset({1, '1'})


def project_web_options(kind, identity='standard', selected=None, surface='agent'):
    """Return option groups for the existing PCG option popup.

    Diamond marks stay on membership options. surface=agent (default) keeps those
    options selectable for standard identity. surface=web matches the C-end:
    standard users see gems but cannot select them. Credits never unlock.
    """
    if kind not in KINDS:
        raise ValueError('unsupported Hi3D option kind')
    if identity not in IDENTITIES:
        raise ValueError('identity must be standard or member')
    if surface not in SURFACES:
        raise ValueError('surface must be agent or web')
    wanted = dict(selected or {})
    if kind == 'text-to-image':
        groups = _image_groups(identity, wanted, surface)
        title = '图像生成'
    elif kind == 'model':
        groups = _model_groups(identity, wanted, surface)
        title = '3D 生成'
    elif kind == 'relief':
        groups = _relief_groups(identity, wanted, surface)
        title = '3D 浮雕'
    elif kind == 'split':
        groups = _split_groups(identity, wanted, surface)
        title = '拆件打印'
    else:
        groups = _license_only_groups(identity, wanted, surface)
        title = '多色打印'
    clamped = any(group.get('clamped') for group in groups)
    locked = []
    selectable = []
    gems = []
    for group in groups:
        for option in group['options']:
            key = group['id'] + ':' + str(option['id'])
            if option.get('member') or option.get('badge') == GEM:
                gems.append(key)
            if option['enabled']:
                selectable.append(key)
            else:
                locked.append(key)
    projected = {
        'kind': kind,
        'identity': identity,
        'surface': surface,
        'title': title,
        'prompt': '请选择您要使用的 Hi3D 生成参数',
        'gem_means': 'membership',
        'credits_unlock': False,
        'clamped': clamped,
        'groups': groups,
        'gem_ids': gems,
        'locked_ids': locked,
        'selectable_ids': selectable,
    }
    return projected


def reject_gated_request(kind, identity, *, parameters=None, images=(), image_count=None,
                         model_name=None, edit_task_type=None, overrides=(), surface='agent'):
    """Raise if a standard identity tries to set a gem-gated field on the web surface."""
    if identity is None:
        return
    if identity not in IDENTITIES:
        raise ValueError('identity must be standard or member')
    if surface not in SURFACES:
        raise ValueError('surface must be agent or web')
    if identity == 'member' or surface == 'agent':
        return
    if kind not in KINDS and kind not in ('image-edit', 'text-to-image'):
        raise ValueError('unsupported Hi3D option kind')
    params = dict(parameters or {})
    other = params.get('otherParam') if isinstance(params.get('otherParam'), dict) else params
    names = set()
    override_map = {}
    if isinstance(overrides, (list, tuple)):
        for item in overrides:
            if isinstance(item, str) and '=' in item:
                key, value = item.split('=', 1)
                names.add(key)
                override_map[key] = value
            elif isinstance(item, dict):
                names.update(item)
                override_map.update(item)
    image_n = image_count if image_count is not None else len(list(images or ()))
    mapped_kind = 'text-to-image' if kind in ('text-to-image', 'image-edit') else kind

    def _fail(field):
        raise ValueError(
            'Membership-gated option cannot be changed via API for standard identity: ' + field
        )

    if mapped_kind == 'text-to-image':
        model = model_name or params.get('modelName') or params.get('imageModel') or other.get('modelName')
        alias = _image_model_id(model)
        if alias in _MEMBER_IMAGE_MODELS:
            _fail('imageModel')
        count = params.get('imageCount', other.get('imageCount'))
        if count is None:
            count = image_n
        try:
            if int(count) > 1:
                _fail('imageCount')
        except (TypeError, ValueError):
            pass
        if _truthy(params.get('multiview') or other.get('multiview') or names & {'multiview', 'multiView'}):
            _fail('multiview')
        return
    if mapped_kind == 'model':
        if _truthy(params.get('pbr') or other.get('pbr')) or 'pbr' in names:
            _fail('advanced')
        if _truthy(params.get('face') or other.get('face')) or 'face' in names:
            _fail('advanced')
        if _multiview_images(images) or _truthy(params.get('multiViewInfo') or other.get('multiViewInfo')):
            _fail('multiview')
        license_id = params.get('license') or other.get('license') or override_map.get('license')
        if str(license_id).lower() in {'private', 'priv'}:
            _fail('license')
        return
    if mapped_kind == 'split':
        part = override_map.get('part') or params.get('part') or other.get('part')
        template = _split_template(params, other)
        if part and str(part) not in _FREE_SPLIT_PARTS:
            _fail('split_template')
        if template is not None and template not in _FREE_SPLIT_TEMPLATES and str(template) not in _FREE_SPLIT_PARTS:
            _fail('split_template')
        return
    license_id = params.get('license') or other.get('license') or override_map.get('license')
    if str(license_id).lower() in {'private', 'priv'}:
        _fail('license')


def _image_model_id(name):
    if not name:
        return None
    text = str(name).strip().lower().replace(' ', '-').replace('_', '-')
    aliases = {
        'nano-banana-pro': 'nano-banana-pro',
        'nano-banana-2': 'nano-banana-2',
        'gpt-image-2': 'gpt-image-2',
        'seedream-v4.5': 'seedream-v4.5',
        'seedream-v4-5': 'seedream-v4.5',
    }
    return aliases.get(text)


def _truthy(value):
    return value not in (None, False, 0, '0', 'false', 'off', '')


def _multiview_images(images):
    return len(list(images or ())) > 1


def _split_template(params, other):
    async_raw = other.get('asyncInputParam') or params.get('asyncInputParam')
    if isinstance(async_raw, str) and async_raw.strip().startswith('{'):
        import json
        try:
            async_raw = json.loads(async_raw)
        except ValueError:
            return None
    if isinstance(async_raw, dict):
        return async_raw.get('template')
    return other.get('template') or params.get('template')


def _pick(options, wanted, default_id, identity, surface):
    requested = wanted
    chosen = None
    clamped = False
    lock_on_web = surface == 'web'
    for option in options:
        member = bool(option.get('member'))
        web_locked = member and identity == 'standard'
        option['badge'] = GEM if member else option.get('badge')
        option['web_locked'] = web_locked
        option['enabled'] = (not web_locked) if lock_on_web else True
        option['selected'] = False
        if str(option['id']) == str(requested):
            if option['enabled']:
                chosen = option
            else:
                clamped = True
    if chosen is None:
        for option in options:
            if option['id'] == default_id and option['enabled']:
                chosen = option
                break
    if chosen is None:
        chosen = next(option for option in options if option['enabled'])
        clamped = True
    chosen['selected'] = True
    return options, clamped


def _group(gid, label, widget, options, wanted, default_id, identity, surface):
    items, clamped = _pick(options, wanted.get(gid), default_id, identity, surface)
    return {
        'id': gid,
        'label': label,
        'widget': widget,
        'clamped': clamped,
        'options': items,
    }


def _image_groups(identity, wanted, surface):
    models = [
        {'id': 'gpt-image-2', 'label': 'GPT Image 2', 'member': True, 'badge_text': '推荐'},
        {'id': 'nano-banana-pro', 'label': 'Nano-Banana-Pro', 'member': True},
        {'id': 'nano-banana-2', 'label': 'Nano-Banana 2', 'member': True},
        {'id': 'seedream-v4.5', 'label': 'Seedream V4.5', 'member': False},
    ]
    ratios = [
        {'id': item, 'label': item, 'member': False}
        for item in ('1:1', '16:9', '9:16', '4:3', '3:4')
    ]
    views = [
        {'id': 'off', 'label': '关', 'member': False},
        {'id': 'on', 'label': '多视图', 'member': True},
    ]
    return [
        _group('model', '模型', 'dropdown', models, wanted, 'gpt-image-2', identity, surface),
        _group('aspect_ratio', '尺寸', 'chips', ratios, wanted, '1:1', identity, surface),
        _group('multiview', '多视图', 'toggle', views, wanted, 'off', identity, surface),
    ]


MODEL_VERSION_TIERS = (
    {'id': 'v3.0', 'slogan': '极致细节', 'types': (
        {'id': 'quality', 'caption': '高质 | 品质增强（推荐）'},
        {'id': 'master', 'caption': '大师 | 极致细节'},
    )},
    {'id': 'v2.1', 'slogan': '极速生成', 'types': (
        {'id': 'fast', 'caption': '极速 | 最快出稿（推荐）'},
        {'id': 'quality', 'caption': '高质 | 品质增强'},
    )},
    {'id': 'v2.0', 'slogan': '均衡全能', 'types': (
        {'id': '1536', 'caption': '均衡'},
        {'id': '1536pro', 'caption': '高质'},
    )},
)
_GENERATION_CAPTIONS = (
    ('both', '几何+风格化贴图（推荐）'),
    ('mesh', '几何'),
    ('texture', '仅贴纹理（需已有 GLB）'),
)
# Standalone texturing is a v3.0 capability; v2.0/v2.1 tiers reject request_type=2.
_TEXTURE_UNSUPPORTED_VERSIONS = ('v2.0', 'v2.1')
_GENERATION_ERROR = 'generation_type must be mesh, both or texture'


def model_option_description(tier, model_type):
    """Short web-aligned caption after the submit id."""
    slogan = tier.get('slogan')
    prefix = '%s %s' % (tier['id'], slogan) if slogan else tier['id']
    return '%s · %s' % (prefix, model_type['caption'])


def _model_groups(identity, wanted, surface):
    types = []
    for version in MODEL_VERSION_TIERS:
        for item in version['types']:
            types.append({
                'id': version['id'] + ':' + item['id'],
                'label': version['id'] + ':' + item['id'],
                'description': model_option_description(version, item),
                'member': False,
                'type_id': item['id'],
            })
    gen = [
        {'id': key, 'label': caption, 'description': caption, 'member': False}
        for key, caption in _GENERATION_CAPTIONS
    ]
    return [
        _group('model_type', '模型', 'chips', types, wanted, 'v3.0:quality', identity, surface),
        _group('generation_type', '生成类型', 'chips', gen, wanted, 'both', identity, surface),
    ]


def _relief_groups(identity, wanted, surface):
    rmbg = [
        {'id': 'on', 'label': '去除背景', 'member': False},
        {'id': 'off', 'label': '保留背景', 'member': False},
    ]
    return [
        _group('rmbg', '去除背景', 'toggle', rmbg, wanted, 'on', identity, surface),
        _group('license', '许可', 'chips', _license_options(), wanted, 'cc_by', identity, surface),
    ]


def _split_groups(identity, wanted, surface):
    scenes = [
        {'id': 'character', 'label': '角色', 'member': False},
        {'id': 'general', 'label': '通用', 'member': False},
    ]
    templates = [
        {'id': 'a', 'label': '6 个部件', 'member': False},
        {'id': 'b', 'label': '5 个部件', 'member': True},
        {'id': 'c', 'label': '4 个部件', 'member': True},
        {'id': 'd', 'label': '4 个部件', 'member': True},
        {'id': 'e', 'label': '3 个部件', 'member': True},
        {'id': 'f', 'label': '2 个部件', 'member': True},
    ]
    return [
        _group('scene', '类型', 'tabs', scenes, wanted, 'character', identity, surface),
        _group('template', '角色拆分模板', 'templates', templates, wanted, 'a', identity, surface),
        _group('license', '许可', 'chips', _license_options(), wanted, 'cc_by', identity, surface),
    ]


def _license_only_groups(identity, wanted, surface):
    return [_group('license', '许可', 'chips', _license_options(), wanted, 'cc_by', identity, surface)]


# Display/settings ids → create-task fields. Image ids remain optional aliases.
_MODEL_API = {
    ('v3.0', 'quality'): ('hi3dv3.0', '2048quality'),
    ('v3.0', 'master'): ('hi3dv3.0', '2048master'),
    ('v2.1', 'fast'): ('hitem3dv2.1', '1536fast'),
    ('v2.1', 'quality'): ('hitem3dv2.1', '1536pro'),
    ('v2.0', '1536'): ('hitem3dv2.0', '1536'),
    ('v2.0', '1536pro'): ('hitem3dv2.0', '1536pro'),
}
_GENERATION_API = {'mesh': '1', 'both': '3', 'texture': '2'}
_GENERATION_NATIVE = {'mesh': 'mesh', 'both': 'both', 'texture': 'texture'}
_DISPLAY_KEYS = {
    'text-to-image': {'model', 'aspect_ratio'},
    'image-edit': {'model', 'aspect_ratio'},
    'model': {'model_type', 'generation_type'},
    'relief': {'rmbg'},
    'split': {'scene', 'template'},
}
_IMAGE_NATIVE = {
    'gpt-image-2': 'GPT Image 2',
    'nano-banana-pro': 'Nano-Banana-Pro',
    'nano-banana-2': 'Nano-Banana 2',
    'seedream-v4.5': 'Seedream v4.5',
}
_MODEL_NATIVE = {
    # UI tier names differ from the native modelType values.
    ('v3.0', 'quality'): (('version', 'v3.0'), ('modelType', 'standard'), ('voxelResolution', '2048')),
    ('v3.0', 'master'): (('version', 'v3.0'), ('modelType', 'quality'), ('voxelResolution', '2048')),
    ('v2.1', 'fast'): (('version', 'v2.1'), ('modelType', 'fast')),
    ('v2.1', 'quality'): (('version', 'v2.1'), ('modelType', 'quality')),
    ('v2.0', '1536'): (('version', 'v2.0'), ('modelType', 'balanced'), ('voxelResolution', '1536')),
    ('v2.0', '1536pro'): (('version', 'v2.0'), ('modelType', 'quality'), ('voxelResolution', '1536')),
}
_SPLIT_TEMPLATE_NATIVE = {'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5, 'f': 6}


def display_overrides(kind, overrides):
    """Rewrite popup ids into public API --set pairs. Unknown API keys stay unchanged."""
    if kind not in _DISPLAY_KEYS:
        return list(overrides or [])
    kept = []
    chosen = {}
    for item in overrides or []:
        if not isinstance(item, str) or '=' not in item:
            kept.append(item)
            continue
        key, value = item.split('=', 1)
        if key in _DISPLAY_KEYS[kind]:
            chosen[key] = value
        else:
            kept.append(item)
    if not chosen:
        return kept
    if kind in ('text-to-image', 'image-edit'):
        kept.extend(_image_display(chosen))
    elif kind == 'model':
        kept.extend(_model_display(chosen))
    elif kind == 'relief':
        if chosen['rmbg'] not in ('on', 'off'):
            raise ValueError('rmbg must be on or off')
        kept.append('rmbg=' + ('1' if chosen['rmbg'] == 'on' else '0'))
    else:
        if 'scene' in chosen:
            if chosen['scene'] not in ('character', 'general'):
                raise ValueError('scene must be character or general')
            kept.append('model=' + chosen['scene'])
        if 'template' in chosen:
            if chosen['template'] not in {item['id'] for item in (
                {'id': 'a'}, {'id': 'b'}, {'id': 'c'}, {'id': 'd'}, {'id': 'e'}, {'id': 'f'}
            )}:
                raise ValueError('template must be a-f')
            kept.append('part=' + chosen['template'])
    return kept


def _image_display(chosen):
    """Image display ids are Runtime-only; keep native names for defensive reuse."""
    out = []
    if 'model' in chosen:
        model = _IMAGE_NATIVE.get(chosen['model'])
        if not model:
            raise ValueError('model must be a supported image model id')
        out.append('modelName=' + model)
    if 'aspect_ratio' in chosen:
        ratio = chosen['aspect_ratio']
        if ratio not in ('1:1', '16:9', '9:16', '4:3', '3:4'):
            raise ValueError('aspect_ratio must be 1:1, 16:9, 9:16, 4:3 or 3:4')
        out.append('aspectRatio=' + ratio)
    if 'image_count' in chosen:
        count = chosen['image_count']
        if str(count) not in ('1', '2', '3', '4'):
            raise ValueError('image_count must be 1, 2, 3 or 4')
        out.append('imageCount=' + str(count))
    return out


def _model_display(chosen):
    model_type = chosen.get('model_type')
    out = []
    if model_type:
        if ':' not in model_type:
            raise ValueError('model_type must be version:type, for example v3.0:quality')
        prefix, type_id = model_type.split(':', 1)
        pair = _MODEL_API.get((prefix, type_id))
        if not pair:
            raise ValueError('unknown model_type: ' + model_type)
        out.append('model=' + pair[0])
        out.append('resolution=' + pair[1])
    if 'generation_type' in chosen:
        request_type = _GENERATION_API.get(chosen['generation_type'])
        if not request_type:
            raise ValueError(_GENERATION_ERROR)
        out.append('request_type=' + request_type)
    return out


def native_display_overrides(kind, overrides):
    """Rewrite popup ids into Runtime native --set pairs."""
    if kind not in _DISPLAY_KEYS:
        return list(overrides or [])
    kept = []
    chosen = {}
    for item in overrides or []:
        if not isinstance(item, str) or '=' not in item:
            kept.append(item)
            continue
        key, value = item.split('=', 1)
        if key in _DISPLAY_KEYS[kind]:
            chosen[key] = value
        else:
            kept.append(item)
    if not chosen:
        return kept
    if kind in ('text-to-image', 'image-edit'):
        kept.extend(_image_display(chosen))
    elif kind == 'model':
        kept.extend(_model_native(chosen))
    elif kind == 'relief':
        if chosen['rmbg'] not in ('on', 'off'):
            raise ValueError('rmbg must be on or off')
        kept.append('rmbg=' + ('1' if chosen['rmbg'] == 'on' else '0'))
    else:
        if 'scene' in chosen and chosen['scene'] not in ('character', 'general'):
            raise ValueError('scene must be character or general')
        if 'template' in chosen:
            template = _SPLIT_TEMPLATE_NATIVE.get(chosen['template'])
            if template is None:
                raise ValueError('template must be a-f')
            kept.append('asyncInputParam={"template":%s}' % template)
    return kept


def _model_native(chosen):
    model_type = chosen.get('model_type')
    out = []
    if model_type:
        if ':' not in model_type:
            raise ValueError('model_type must be version:type, for example v3.0:quality')
        prefix, type_id = model_type.split(':', 1)
        pair = _MODEL_NATIVE.get((prefix, type_id))
        if not pair:
            raise ValueError('unknown model_type: ' + model_type)
        out.extend(key + '=' + value for key, value in pair)
    if 'generation_type' in chosen:
        generation = _GENERATION_NATIVE.get(chosen['generation_type'])
        if not generation:
            raise ValueError(_GENERATION_ERROR)
        if generation == 'texture':
            # Runtime routes standalone texturing by scene, not only by generationType.
            out.append('scene=texture')
        out.append('generationType=' + generation)
    return out


def validate_generation_selection(selected, has_mesh=None):
    """Reject texture-only selections that the service cannot fulfil.

    has_mesh=None means the caller cannot tell yet (for example the mesh may
    arrive inside a native --request); build_plan still enforces it later.
    """
    picked = selected or {}
    if picked.get('generation_type') != 'texture':
        return
    model_type = str(picked.get('model_type') or '')
    if model_type.split(':', 1)[0] in _TEXTURE_UNSUPPORTED_VERSIONS:
        raise ValueError('generation_type=texture requires a v3.0 model_type; v2.0/v2.1 do not support standalone texturing')
    if has_mesh is False:
        raise ValueError('generation_type=texture requires an existing GLB via --mesh or --mesh-url')


def popup_selected(kind, overrides):
    """Extract popup ids from --set pairs."""
    keys = _DISPLAY_KEYS.get(kind) or set()
    chosen = {}
    for item in overrides or []:
        if not isinstance(item, str) or '=' not in item:
            continue
        key, value = item.split('=', 1)
        if key in keys:
            chosen[key] = value
    return chosen


def selected_complete(kind, selected):
    """Return whether every required parameter-panel id has a selected value."""
    if kind in ('text-to-image', 'image-edit'):
        return True
    needed = _DISPLAY_KEYS.get(kind)
    if not needed:
        return True
    selected = selected or {}
    return needed <= set(selected)


def project_parameter_interaction(kind, selected=None):
    """Return a valid host user_interaction preference panel for missing display ids."""
    if kind in ('text-to-image', 'image-edit'):
        return None
    picked = dict(selected or {})
    questions = []
    if kind == 'model':
        if 'model_type' not in picked:
            questions.append({
                'id': 'model_type',
                'question': '选择 3D 模型',
                'options': [
                    {
                        'label': tier['id'] + ':' + model_type['id'],
                        'description': model_option_description(tier, model_type),
                    }
                    for tier in MODEL_VERSION_TIERS
                    for model_type in tier['types']
                ],
                'defaultAnswer': 'v3.0:quality',
            })
        if 'generation_type' not in picked:
            questions.append({
                'id': 'generation_type',
                'question': '选择生成内容',
                'options': [
                    {'label': key, 'description': caption}
                    for key, caption in _GENERATION_CAPTIONS
                ],
                'defaultAnswer': 'both',
            })
    elif kind == 'relief' and 'rmbg' not in picked:
        questions.append({
            'id': 'rmbg',
            'question': '是否去除图片背景',
            'options': [
                {'label': 'on', 'description': '去除背景'},
                {'label': 'off', 'description': '保留背景'},
            ],
            'defaultAnswer': 'on',
        })
    elif kind == 'split':
        if 'scene' not in picked:
            questions.append({
                'id': 'scene',
                'question': '选择拆件类型',
                'options': [
                    {'label': 'character', 'description': '角色'},
                    {'label': 'general', 'description': '通用'},
                ],
                'defaultAnswer': 'character',
            })
        if 'template' not in picked:
            questions.append({
                'id': 'template',
                'question': '选择拆件模板',
                'options': [
                    {'label': item['id'], 'description': item['label']}
                    for item in _split_groups('standard', {}, 'agent')[1]['options']
                ],
                'defaultAnswer': 'a',
            })
    if not questions:
        return None
    return {
        'kind': 'preference',
        'title': 'Hi3D 生成参数',
        'message': '请选择本次生成参数；60 秒未选择时使用面板中的推荐参数。',
        'questions': questions,
        'timeoutSeconds': 60,
    }


def submit_choice_gate(
    kind,
    *,
    overrides=(),
    selected=None,
    has_mesh=None,
):
    """Decide whether parameter selection is complete. Never POSTs."""
    mapped_kind = 'model' if kind not in KINDS and kind not in ('image-edit',) else kind
    if kind in ('text-to-image', 'image-edit'):
        mapped_kind = 'text-to-image'
    picked = dict(selected or {})
    picked.update(popup_selected(kind, overrides))
    if kind == 'model':
        validate_generation_selection(picked, has_mesh)
    complete = selected_complete(kind, picked)
    if complete:
        return {'result': 'ready', 'kind': kind, 'selected': picked}
    if not complete:
        interaction = project_parameter_interaction(kind, picked)
        return {
            'result': 'waiting_choice',
            'stage': 'parameters',
            'kind': kind,
            'selected': picked,
            'web_options': project_web_options(mapped_kind, selected=picked),
            'user_interaction': interaction,
        }


def load_session_selection(path, kind):
    """Read persisted parameter selections from a task-directory session JSON."""
    if not path:
        return {}
    from pathlib import Path
    import json
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('session must be a JSON object')
    options = data.get('hi3d_options') if isinstance(data.get('hi3d_options'), dict) else {}
    by_kind = options.get('selected_by_kind') if isinstance(options.get('selected_by_kind'), dict) else {}
    selected = dict(by_kind[kind]) if isinstance(by_kind.get(kind), dict) else {}
    if not selected and options.get('kind') == kind and isinstance(options.get('selected'), dict):
        selected = dict(options['selected'])
    return selected


def gate_parameter_overrides(kind, *, overrides=(), session=None, native=False, has_mesh=None):
    """Return (gate, rewritten --set). Caller POSTs only when parameters are ready.

    has_mesh lets the gate reject a texture-only choice before any upload when
    the caller already knows no GLB was given; None skips that check.
    """
    selected = load_session_selection(session, kind)
    rewritten = native_display_overrides(kind, overrides) if native else display_overrides(kind, overrides)
    gate = submit_choice_gate(
        kind,
        overrides=overrides,
        selected=selected,
        has_mesh=has_mesh,
    )
    return gate, rewritten


def _license_options():
    return [
        {'id': 'cc_by', 'label': 'CC BY 4.0', 'member': False},
        {'id': 'private', 'label': '私有', 'member': True},
    ]
