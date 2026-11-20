"""Synchronous mesh API through the desktop proxy; never reads account cookies."""
import argparse
import hashlib
import json
import mimetypes
import re
import shutil
import sys
import tempfile
import urllib.parse
import uuid
import zipfile
from pathlib import Path

# Shared transport/storage is materialized by package.json in this tool directory.
from hi3d_client import ApiError, Client
from hi3d_artifacts import fetch, validate_glb
from hi3d_storage import digest, load, save, workspace_path, public_record, private_result_path, save_private_result, load_private_result


def integer(minimum, maximum=None):
    return lambda v: type(v) is int and v >= minimum and (maximum is None or v <= maximum)


BOOL = lambda v: type(v) is bool
CHOICE = lambda *values: lambda v: isinstance(v, str) and v in values
SCHEMA = {
    'remove-background': {},
    'unwrap-uv': {'texture_size': integer(1), 'need_repair': BOOL},
    'convert-3mf': {'threemf_mode': CHOICE('auto', 'standard', 'orca'), 'threemf_target_size_mm': integer(0)},
    'watertight': {'watertight_resolution': lambda v: integer(1, 4096)(v) and v & (v - 1) == 0,
                   'target_face_num': integer(-1), 'is_fillhole': BOOL},
    'retopology': {'face': integer(1), 'face_type': CHOICE('triangles', 'quads'), 'topology_method': CHOICE('standard', 'feature')},
    'mesh-lod': {'target_face_num_list': lambda v: isinstance(v, list) and bool(v)
                and all(integer(1)(n) for n in v) and all(a > b for a, b in zip(v, v[1:]))},
    'auto-rig': {'use_skeleton': BOOL, 'use_transfer': BOOL, 'num_beams': integer(1, 20)},
    'pose': {'detect_persons': BOOL}, 'seg': {}, 'normal': {},
    'pointmap': {'pointmap_smooth': BOOL}, 'matting': {},
    'extract-centerline': {},
    'check-printability': {'require_single_body': BOOL, 'require_watertight': BOOL},
}
IMAGES = {'remove-background', 'pose', 'seg', 'normal', 'pointmap', 'matting'}


def validate(capability, params, file):
    if capability not in SCHEMA or not isinstance(params, dict):
        raise ValueError('Unknown capability or invalid params object')
    for name, value in params.items():
        if name not in SCHEMA[capability] or not SCHEMA[capability][name](value):
            raise ValueError('Invalid public parameter: ' + name)
    file = workspace_path(file, must_exist=True)
    formats, maximum = ({'.png', '.jpg', '.jpeg', '.webp'}, 40) if capability in IMAGES else (
        ({'.obj', '.fbx', '.glb'}, 256) if capability == 'auto-rig' else ({'.glb'}, 200))
    if not file.is_file() or file.suffix.lower() not in formats or not 0 < file.stat().st_size <= maximum * 1024**2:
        raise ValueError('Invalid input format or size for ' + capability)
    with file.open('rb') as stream:
        header = stream.read(12)
    suffix = file.suffix.lower()
    if suffix == '.glb':
        validate_glb(file)
    elif suffix == '.png' and not header.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('Invalid PNG header')
    elif suffix in {'.jpg', '.jpeg'} and not header.startswith(b'\xff\xd8\xff'):
        raise ValueError('Invalid JPEG header')
    elif suffix == '.webp' and not (header[:4] == b'RIFF' and header[8:12] == b'WEBP'):
        raise ValueError('Invalid WebP header')
    return file


def multipart(request, file, expected_hash=None):
    boundary = 'mdf-' + uuid.uuid4().hex
    body = tempfile.TemporaryFile()
    body.write(('--' + boundary + '\r\nContent-Disposition: form-data; name="request"\r\n'
                'Content-Type: application/json\r\n\r\n').encode())
    body.write(json.dumps(request, allow_nan=False).encode())
    suffix = file.suffix.lower()
    mime = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp'}.get(suffix) or mimetypes.guess_type('input' + suffix)[0] or 'application/octet-stream'
    body.write((f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="input{suffix}"\r\n'
                f'Content-Type: {mime}\r\n\r\n').encode())
    try:
        hashed = hashlib.sha256()
        with file.open('rb') as source:
            for block in iter(lambda: source.read(1024**2), b''):
                hashed.update(block)
                body.write(block)
        if expected_hash is not None and hashed.hexdigest() != expected_hash:
            raise ValueError('Input changed between planning and upload')
    except BaseException:
        body.close()
        raise
    body.write(f'\r\n--{boundary}--\r\n'.encode())
    length = body.tell()
    body.seek(0)
    return body, 'multipart/form-data; boundary=' + boundary, length


def lods(data):
    result = []
    mapping = data.get('mesh_lod_glbs')
    if not isinstance(mapping, dict) or not mapping:
        raise ValueError('Missing LOD field mapping')
    for target, field in mapping.items():
        if not re.fullmatch(r'[1-9][0-9]*', target) or not isinstance(field, str):
            raise ValueError('Invalid LOD field pointer')
        asset = data.get('files', {}).get(field, {})
        key = asset.get('key') or data.get(field)
        if not isinstance(key, str) or not key.lower().endswith('.glb'):
            raise ValueError('Missing or invalid LOD GLB')
        result.append({'targetFaces': int(target), 'field': field, 'key': key, 'url': asset.get('url'),
                       'actualFaces': (data.get('mesh_lod_metadata', {}).get(target) or {}).get('actual_faces')})
    return sorted(result, key=lambda item: item['targetFaces'], reverse=True)


def download(job, record, output, downloader=fetch):
    if record.get('status') != 'SUCCEEDED':
        return summary(job, record)
    context = {key: record[key] for key in ('environment', 'owner_id')}
    # Legacy raw responses are sanitized as soon as they are resumed.
    if not record.get('privateResult'):
        save_private_result(job, context, record['response'])
        record['response'] = public_record(record['response'])
        record['privateResult'] = True
        save(job, record)
    data = load_private_result(job, context).get('data') or {}
    assets = data.get('files', {})
    if not isinstance(assets, dict):
        raise ValueError('Invalid output files map; preserve original record')
    output.mkdir(parents=True, exist_ok=True)
    downloaded = record.setdefault('downloads', {})
    issues = []
    capability = record['request']['capability']
    if capability == 'mesh-lod':
        try:
            record['lods'] = public_record(lods(data))
            expected = record['request']['params'].get('target_face_num_list', [2000000, 500000, 200000])
            if [item['targetFaces'] for item in record['lods']] != expected:
                issues.append('LOD targets do not match the request; retain original response')
        except (ValueError, TypeError, AttributeError):
            issues.append('Invalid LOD result; retain original response')
    if not assets and capability not in {'extract-centerline', 'check-printability'}:
        issues.append('No downloadable file descriptors; retain result keys and contact the service')
    for field, asset in assets.items():
        if not isinstance(asset, dict) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', field):
            issues.append('Invalid file descriptor'); continue
        url = asset.get('url')
        suffix = Path(urllib.parse.urlsplit(url or asset.get('key', '')).path).suffix.lower()
        allowed_zip = capability == 'retopology' and field == 'model_obj' and suffix == '.zip'
        if (suffix not in {'.glb', '.3mf', '.png', '.jpg', '.jpeg', '.webp', '.npz'} and not allowed_zip) or not url:
            issues.append(field + ': download unavailable; retain key'); continue
        target = workspace_path(output / ('hi3d-' + field + suffix))
        previous = downloaded.get(field)
        if previous:
            if previous['path'] != str(target) or not target.is_file() or digest(target) != previous['sha256']:
                issues.append(field + ': saved artifact changed or missing')
            continue
        try:
            downloader(url, target)
            if suffix == '.glb':
                validate_glb(target)
            if allowed_zip and not zipfile.is_zipfile(target):
                raise ValueError('Invalid OBJ ZIP')
            downloaded[field] = {'path': str(target), 'sha256': digest(target)}
            save(job, record)
        except Exception:
            issues.append(field + ': download failed; use download with the same record')
    record['downloadIssues'] = issues
    save(job, record)
    return summary(job, record)


def summary(job, record):
    response = record.get('response', {})
    return public_record({'status': record['status'], 'jobPath': str(job),
        'requestId': response.get('requestId'), 'response': response,
        'files': {key: item['path'] for key, item in record.get('downloads', {}).items()},
        'lods': record.get('lods'), 'downloadIssues': record.get('downloadIssues', []),
        'message': 'Use download for saved results; never resubmit UNKNOWN/interrupted records.'})


def execute(args, client_factory=Client, downloader=fetch):
    job, output = workspace_path(args.job), workspace_path(args.out)
    if args.action == 'download':
        record = load(job)
        client = client_factory()
        client.check_job(record)
        if str(output) != record['outputDir']:
            raise ValueError('Use the original outputDir')
        return download(job, record, output, downloader)
    params = json.loads(args.params)
    if params is None:
        params = {}
    file = validate(args.capability, params, args.file)
    if job == file or job == output or job.is_relative_to(output):
        raise ValueError('Job record must be separate from input and output directory')
    request = {'capability': args.capability, 'params': params}
    for name, value in (('sessionId', args.session_id), ('turnId', args.turn_id)):
        if value:
            if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', value):
                raise ValueError('Invalid correlation ID')
            request[name] = value
    file_hash = digest(file)
    fingerprint = hashlib.sha256(json.dumps({'capability': args.capability, 'params': params,
        'fileHash': file_hash, 'output': str(output)}, sort_keys=True).encode()).hexdigest()
    if args.dry_run:
        return {'dryRun': True, 'request': request, 'file': str(file), 'jobPath': str(job),
                'timeoutSeconds': 7500 if args.capability == 'mesh-lod' else 2100}
    client = client_factory()
    client.auth()
    if job.exists():
        record = load(job)
        client.check_job(record)
        if record.get('fingerprint') != fingerprint:
            raise ValueError('Existing record belongs to another request; do not overwrite')
        return download(job, record, output, downloader)
    private_result_path(job, client.context)  # Fail before reserving/submitting if the host cache is unavailable.
    record = dict(client.context, fingerprint=fingerprint, request=request, outputDir=str(output), status='UNKNOWN')
    # Exclusive durable reservation before any POST. A crash at any later point cannot auto-resubmit.
    save(job, record, exclusive=True)
    try:
        body, content_type, length = multipart(request, file, file_hash)
        with body:
            status, response = client.send('/mesh/invoke', 'POST', body, content_type, length,
                                           7500 if args.capability == 'mesh-lod' else 2100)
        record['httpStatus'] = status
        record['response'] = public_record(response)
        save_private_result(job, client.context, response)
        record['privateResult'] = True
        record['status'] = ('SUCCEEDED' if status == 200 and type(response.get('code')) is int
                            and response['code'] == 0 and response.get('status') == 'SUCCEEDED' else
                            response.get('status') if response.get('status') in {'FAILED', 'REJECTED', 'UNKNOWN'} else 'UNKNOWN')
        save(job, record)
    except Exception:
        record['status'] = 'UNKNOWN'
        save(job, record)
        return summary(job, record)
    return download(job, record, output, downloader)


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('action', choices=['invoke', 'download'])
    result.add_argument('--capability', choices=sorted(SCHEMA))
    result.add_argument('--file')
    result.add_argument('--params', default='{}')
    result.add_argument('--job', required=True)
    result.add_argument('--out', required=True)
    result.add_argument('--session-id')
    result.add_argument('--turn-id')
    result.add_argument('--dry-run', action='store_true')
    return result


if __name__ == '__main__':
    try:
        result = execute(parser().parse_args())
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(0 if result.get('dryRun') or result.get('status') == 'SUCCEEDED' else 2)
    except ApiError as error:
        print(json.dumps({'error': str(error), 'code': error.code}))
        sys.exit(2)
    except Exception as error:
        # Do not expose transport exception URLs, headers or credentials.
        print(json.dumps({'error': str(error) if isinstance(error, (ValueError, FileExistsError)) else 'Mesh operation failed; retain the original record', 'type': type(error).__name__}))
        sys.exit(2)
