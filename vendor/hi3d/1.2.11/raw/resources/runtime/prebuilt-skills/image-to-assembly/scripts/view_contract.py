"""Define Hi3D API camera slots independently of website labels and part names."""

import hashlib
import json
from email.parser import BytesParser
from email.policy import default
from pathlib import Path

CONVENTION = 'hi3d-front-neg-y-z-up-v1'
API_ORDER = ('front', 'back', 'left', 'right')
CAMERA_DIRECTIONS = {
    'front': (0, -1, 0), 'back': (0, 1, 0),
    'left': (-1, 0, 0), 'right': (1, 0, 0),
}
SCREEN_FRONT = {
    'front': 'toward_camera', 'back': 'away_from_camera',
    'left': 'screen_right', 'right': 'screen_left',
}
WEBSITE_TO_API = {'Front': 'front', 'Rear': 'back', 'Left': 'right', 'Right': 'left'}


def load_views(path: Path):
    """Validate reviewed directions and return files in API bitmap order.

    Args:
        path: Manifest whose image paths are relative to its own directory.

    Returns:
        Ordered local paths, bitmap, and a non-secret audit dictionary.

    Raises:
        ValueError: A direction, review, image digest, or slot is inconsistent.
    """
    data = json.loads(path.read_text())
    if data.get('convention') != CONVENTION:
        raise ValueError('Unknown view convention; map the source frame explicitly')
    views = data.get('views', {})
    if not isinstance(views, dict) or not 2 <= len(views) <= 4 or 'front' not in views or set(views) - set(API_ORDER):
        raise ValueError('Use two to four API slots including front; one image uses the independent hi3d-api --image entry')
    paths, audit = [], []
    for slot in API_ORDER:
        if slot not in views:
            continue
        entry = views[slot]
        if entry.get('direction_reviewed') is not True or not entry.get('direction_evidence', '').strip():
            raise ValueError('Missing actual direction review: ' + slot)
        if entry.get('camera_position_direction') != list(CAMERA_DIRECTIONS[slot]) or entry.get('camera_up') != [0, 0, 1]:
            raise ValueError('Camera direction or up axis disagrees with API slot: ' + slot)
        observed = entry.get('observed_front_direction')
        symmetric = data.get('rotation_symmetric') is True and observed == 'not_observable'
        if observed != SCREEN_FRONT[slot] and not symmetric:
            raise ValueError('Front landmark points the wrong way for API slot: ' + slot)
        image = (path.parent / entry['path']).resolve()
        raw = image.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if image.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp'} or not 0 < len(raw) <= 20 * 1024 * 1024:
            raise ValueError('Unsupported image format or size: ' + slot)
        if digest != entry.get('sha256'):
            raise ValueError('Image changed after direction review: ' + slot)
        paths.append(image)
        audit.append({'api_slot': slot, 'path': str(image), 'sha256': digest,
                      'bytes': len(raw), 'camera_position_direction': list(CAMERA_DIRECTIONS[slot]),
                      'camera_up': [0, 0, 1], 'observed_front_direction': observed,
                      'direction_evidence': entry['direction_evidence']})
    bits = ''.join('1' if s in views else '0' for s in API_ORDER)
    return paths, bits, {'convention': CONVENTION, 'manifest_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                        'views': audit, 'limit': 'Validates declared directions and unchanged bytes; visual review must inspect the actual images'}


def audit_multipart(body, content_type, fields, view_audit):
    """Verify the exact outgoing multipart image bytes against the reviewed manifest."""
    message = BytesParser(policy=default).parsebytes(
        ('Content-Type: ' + content_type + '\r\nMIME-Version: 1.0\r\n\r\n').encode() + body)
    files, actual_fields = [], {}
    for item in message.iter_parts():
        name = item.get_param('name', header='content-disposition')
        raw = item.get_payload(decode=True)
        if item.get_filename():
            files.append({'field': name, 'filename': item.get_filename(), 'bytes': len(raw),
                          'sha256': hashlib.sha256(raw).hexdigest()})
        else:
            if name in actual_fields:
                raise ValueError('Duplicate outgoing parameter')
            actual_fields[name] = raw.decode()
    if actual_fields != {k: str(v) for k, v in fields.items()} or len(files) != len(view_audit['views']):
        raise ValueError('Outgoing multipart fields or image count changed')
    for actual, reviewed in zip(files, view_audit['views']):
        if actual['field'] != 'multi_images' or actual['sha256'] != reviewed['sha256'] or actual['bytes'] != reviewed['bytes']:
            raise ValueError('Outgoing image bytes/order disagree with reviewed directions')
        actual['api_slot'] = reviewed['api_slot']
    return {'body_sha256': hashlib.sha256(body).hexdigest(), 'body_bytes': len(body),
            'files': files, 'verified': True}
