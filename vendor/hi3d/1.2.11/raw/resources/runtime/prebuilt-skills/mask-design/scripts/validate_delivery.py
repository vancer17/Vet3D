#!/usr/bin/env python3
"""Validate local manifest integrity, not geometry, decoding or browser behavior."""
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

ROLES = {'image', 'description', 'model'}


def manifest_errors(data):
    """Pure schema checks; return errors for malformed JSON shapes."""
    if not isinstance(data, dict):
        return ['Manifest must be an object']
    errors = []
    video_requested = data.get('video_requested', False)
    if type(video_requested) is not bool:
        errors.append('video_requested must be a boolean')
    required_roles = ROLES | ({'video'} if video_requested is True else set())
    for key in ('project', 'version', 'design_stage', 'source_sha256', 'entrypoint'):
        if not isinstance(data.get(key), str) or not data[key].strip():
            errors.append('Missing/invalid '+key)
    if not re.fullmatch(r'[a-f0-9]{64}', str(data.get('source_sha256', ''))):
        errors.append('Invalid source_sha256')
    files = data.get('files')
    if not isinstance(files, list):
        return errors+['files must be an array']
    seen, roles = set(), set()
    for row in files:
        if not isinstance(row, dict):
            errors.append('File entry must be an object')
            continue
        rel, role = row.get('path'), row.get('role')
        if not isinstance(rel, str) or not rel:
            errors.append('File path must be nonempty text')
        elif rel in seen:
            errors.append('Duplicate file: '+rel)
        else:
            seen.add(rel)
        if not isinstance(role, str):
            errors.append('File role must be text')
        else:
            roles.add(role)
        if type(row.get('bytes')) is not int or row['bytes'] <= 0:
            errors.append('Invalid byte count: '+str(rel))
        if not re.fullmatch(r'[a-f0-9]{64}', str(row.get('sha256', ''))):
            errors.append('Invalid SHA-256: '+str(rel))
        if role in ('image', 'model', 'video') and row.get('source_sha256') != data.get('source_sha256'):
            errors.append('Wrong source version: '+str(rel))
    if required_roles-roles:
        errors.append('Missing required roles: '+', '.join(sorted(required_roles-roles)))
    return errors


def delivery_path(root, relative):
    """Resolve inside root, including symlinks; ValueError on escape/missing file."""
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError('Expected a relative file path')
    root = Path(root).resolve()
    path = (root/relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError('File is outside delivery root: '+relative)
    if not path.is_file():
        raise ValueError('Missing file: '+relative)
    return path


def inspect_file(path):
    """Stream a local file with bounded memory; close handles on failure."""
    digest, size = hashlib.sha256(), 0
    with path.open('rb') as stream:
        head = stream.read(16)
        digest.update(head)
        size += len(head)
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
            size += len(chunk)
    return size, digest.hexdigest(), head


def file_errors(row, size, digest, head):
    """Pure comparison of observations with a schema-checked file entry."""
    rel = row['path']
    errors = []
    if size != row['bytes'] or not size:
        errors.append('Byte count mismatch: '+rel)
    if digest != row['sha256']:
        errors.append('SHA-256 mismatch: '+rel)
    suffix = Path(rel).suffix.lower()
    if suffix == '.glb' and (len(head)<12 or head[:4]!=b'glTF' or struct.unpack('<II', head[4:12])!=(2, size)):
        errors.append('Invalid GLB header: '+rel)
    if suffix == '.mp4' and (len(head)<12 or head[4:8]!=b'ftyp'):
        errors.append('Invalid MP4 header: '+rel)
    return errors


def validate(manifest_path, root):
    """Read manifest/files and return report; no mutation or media decoding."""
    data = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    errors, rows = manifest_errors(data), []
    root = Path(root).resolve()
    if not errors:
        try:
            delivery_path(root, data['entrypoint'])
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
        for row in data['files']:
            try:
                size, digest, head = inspect_file(delivery_path(root, row['path']))
                errors.extend(file_errors(row, size, digest, head))
                rows.append({'path':row['path'], 'role':row['role'], 'bytes':size, 'sha256':digest})
            except (OSError, ValueError) as exc:
                errors.append(str(exc))
    return {'status':'failed' if errors else 'passed', 'checked_files':len(rows), 'errors':errors,
            'scope':'Manifest/file integrity only; geometry, decoding, browser playback and access not tested', 'files':rows}


def save_report(path, report):
    """Write a new report, refusing to overwrite input or previous output."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--root', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    try:
        result = validate(args.manifest, args.root or args.manifest.parent)
    except (OSError, ValueError, TypeError) as error:
        result = {'status':'failed', 'errors':[str(error)]}
    if args.report:
        try:
            save_report(args.report, result)
        except OSError as error:
            parser.error(str(error))
    print(json.dumps({k:v for k,v in result.items() if k!='files'}, ensure_ascii=False))
    return 0 if result['status']=='passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
