"""Pure specification checks plus explicit JSON/path input adapters."""
import ast
import json
import math
from pathlib import Path
import re


def number(value, name, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be finite')
    if positive and value <= 0:
        raise ValueError(f'{name} must be positive')
    return float(value)


def vector(value, count, name, *, positive=False):
    if not isinstance(value, list) or len(value) != count:
        raise ValueError(f'{name} needs {count} numbers')
    return [number(v, name, positive=positive) for v in value]


def validate_spec(data):
    """Validate semantic relationships; no files, network, Blender or mutation."""
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        raise ValueError('schema_version must be 1')
    for name in ('task_id', 'builder'):
        if not isinstance(data.get(name), str) or not data[name].strip():
            raise ValueError(f'{name} is required')
    pans = data.get('pans')
    if not isinstance(pans, list) or not pans:
        raise ValueError('At least one explicit pan is required')
    ids, variants, colors = set(), set(), set()
    for p in pans:
        if not isinstance(p, dict):
            raise ValueError('Each pan must be an object')
        for key, seen in [('id', ids), ('variant_id', variants)]:
            val = p.get(key)
            if not isinstance(val, str) or not val or val in seen:
                raise ValueError(f'Each pan needs a unique {key}')
            seen.add(val)
        raw_color = p.get('color', '')
        color = raw_color.removeprefix('#').upper() if isinstance(raw_color, str) else ''
        if not re.fullmatch('[0-9A-F]{6}', color) or color in colors:
            raise ValueError('Pan colors must be valid, nonrepeated RGB hex values')
        colors.add(color)
        vector(p.get('center_mm'), 3, 'center_mm')
        size = vector(p.get('size_mm'), 3, 'size_mm', positive=True)
        radius = number(p.get('corner_mm'), 'corner_mm', positive=True)
        if radius >= min(size[:2]) / 2:
            raise ValueError('corner_mm must be smaller than the half-size')
        margin = number(p.get('margin_mm'), 'margin_mm', positive=True)
        if margin >= min(size[:2]) / 2:
            raise ValueError('Relief margin leaves no usable footprint')
        number(p.get('relief_height_mm'), 'relief_height_mm', positive=True)
        embed = number(p.get('embed_mm'), 'embed_mm', positive=True)
        if embed >= min(size[2], p['relief_height_mm']):
            raise ValueError('embed_mm must leave both cake and relief above their bases')
        axes = p.get('axes', [])
        if (not isinstance(axes, list) or not all(type(a) is int for a in axes)
                or sorted(axes) != [0, 1, 2] or type(p.get('depth_sign')) is not int
                or p['depth_sign'] not in (-1, 1)):
            raise ValueError('Declare source width/height/depth axes and depth_sign')
        for key in ('image', 'relief'):
            if not isinstance(p.get(key), str) or not p[key]:
                raise ValueError(f'Each pan needs its {key} source')
    hinge = data.get('hinge', {})
    vector(hinge.get('pivot_mm'), 3, 'hinge.pivot_mm')
    if hinge.get('axis') not in ('X', 'Y', 'Z') or hinge.get('sign') not in (-1, 1):
        raise ValueError('Declare the hinge axis and sign')
    limit = number(hinge.get('max_angle'), 'max_angle', positive=True)
    if limit > 180:
        raise ValueError('This hinge controller supports opening limits up to 180 degrees')
    keys = data.get('keyframes', [])
    if len(keys) < 3:
        raise ValueError('Keyframes must describe closed/open/closed motion')
    frames = []
    for frame, angle in keys:
        if isinstance(frame, bool) or not isinstance(frame, int) or frame < 1:
            raise ValueError('Keyframe must be a positive integer')
        if not 0 <= number(angle, 'angle') <= limit:
            raise ValueError('Angle exceeds the declared hinge range')
        frames.append(frame)
    if frames != sorted(set(frames)) or keys[0][1] != 0 or keys[-1][1] != 0:
        raise ValueError('Ordered distinct frames must begin and end closed')
    if max(k[1] for k in keys) != limit:
        raise ValueError('Animation must demonstrate maximum opening')
    frames_to_check = data.get('check_frames', [])
    if not frames_to_check or not all(type(f) is int and frames[0] <= f <= frames[-1] for f in frames_to_check):
        raise ValueError('Explicit check_frames must be inside the animation')
    vector(data.get('resolution'), 2, 'resolution', positive=True)
    if any(type(v) is not int for v in data['resolution']):
        raise ValueError('Resolution must contain integers')
    if type(data.get('samples')) is not int or data['samples'] <= 0:
        raise ValueError('samples must be a positive integer')
    number(data.get('exposure'), 'exposure')
    if not isinstance(data.get('shots'), list) or any(not isinstance(s, str) or not s for s in data['shots']):
        raise ValueError('shots must contain camera keys, or be empty')
    if len(set(data['shots'])) != len(data['shots']):
        raise ValueError('Duplicate shot keys')
    finish = data.get('powder_finish', {})
    if not isinstance(finish, dict) or set(finish) - {'grain_mm', 'bump_mm', 'metallic', 'roughness'}:
        raise ValueError('Unsupported powder_finish parameter')
    for key, value in finish.items():
        value = number(value, key, positive=key == 'grain_mm')
        if value < 0 or (key in ('metallic', 'roughness') and value > 1):
            raise ValueError(f'Invalid powder_finish.{key}')
    return data


def read_spec(path):
    """Resolve only declared paths relative to the config; never inspect credentials."""
    path = Path(path).resolve()
    data = validate_spec(json.loads(path.read_text(encoding='utf-8')))
    for owner, key in [(data, 'builder')] + [(p, k) for p in data['pans'] for k in ('image', 'relief')]:
        file = (path.parent / owner[key]).resolve()
        if not file.is_file() or file.stat().st_size == 0:
            raise ValueError(f'Missing or empty declared input: {key}')
        owner[key] = str(file)
    if Path(data['builder']).suffix != '.py':
        raise ValueError('builder must be a reviewed Python module')
    ast.parse(Path(data['builder']).read_text(encoding='utf-8'))
    if any(Path(p['relief']).suffix.lower() != '.stl' for p in data['pans']):
        raise ValueError('This adapter imports STL reliefs; convert other formats explicitly')
    if any(Path(p['image']).suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp') for p in data['pans']):
        raise ValueError('Unsupported source image format')
    return data
