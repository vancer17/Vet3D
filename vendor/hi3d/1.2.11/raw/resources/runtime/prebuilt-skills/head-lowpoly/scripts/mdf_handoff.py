"""Offline handoff to Runtime mdf_api. Never reads credentials or sends requests."""
import hashlib
import json
from pathlib import Path
import zipfile


class WaitingForRetopology(RuntimeError):
    pass


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def request_plan(config):
    root = Path(config['output']).resolve()
    return {'action': 'invoke', 'capability': 'retopology',
            'file': str(root / 'working_surface.glb'),
            'params': {'face': config['remesh_face_goal'], 'face_type': 'quads',
                       'topology_method': 'standard'},
            'jobPath': str(Path(config.get('retopology_job', root / 'mdf-retopology.json')).resolve()),
            'outputDir': str(root / 'mdf-retopology')}


def resolve_result(config):
    """Require the successful Runtime record and its unchanged downloaded OBJ ZIP."""
    plan = request_plan(config)
    job = Path(plan['jobPath'])
    if not job.is_file():
        raise WaitingForRetopology('Run the saved retopology-request.json through Runtime mdf_api; then resume this config')
    record = json.loads(job.read_text(encoding='utf-8'))
    fingerprint = hashlib.sha256(json.dumps({
        'capability': plan['capability'], 'params': plan['params'],
        'fileHash': digest(plan['file']), 'output': plan['outputDir']}, sort_keys=True).encode()).hexdigest()
    if record.get('fingerprint') != fingerprint or record.get('outputDir') != plan['outputDir']:
        raise ValueError('Retopology record does not match the working GLB, parameters or output; preserve the old job')
    if record.get('request', {}).get('capability') != 'retopology' or record.get('request', {}).get('params') != plan['params']:
        raise ValueError('Unexpected retopology request in saved record')
    response = record.get('response') or {}
    if record.get('status') != 'SUCCEEDED' or record.get('httpStatus') != 200 or type(response.get('code')) is not int or response['code'] != 0 or response.get('status') != 'SUCCEEDED':
        raise WaitingForRetopology('Retopology is not SUCCEEDED; retain job/requestId, do not resubmit UNKNOWN or poll MDF')
    artifact = record.get('downloads', {}).get('model_obj')
    if not artifact:
        raise WaitingForRetopology('Use Runtime mdf_api download with the original job/outputDir, then resume')
    path = Path(artifact['path']).resolve()
    if not path.is_relative_to(Path(plan['outputDir'])) or path.suffix.lower() != '.zip':
        raise ValueError('Unexpected retopology artifact path')
    if not path.is_file() or digest(path) != artifact.get('sha256'):
        raise ValueError('Downloaded retopology OBJ ZIP is missing or changed; preserve the original record')
    return path


def unpack_geometry(archive, target):
    """Read one bounded OBJ member without extracting paths or external materials."""
    with zipfile.ZipFile(archive) as package:
        objects = [e for e in package.infolist() if not e.is_dir() and e.filename.lower().endswith('.obj')]
        if len(objects) != 1:
            raise ValueError('Retopology ZIP must contain exactly one OBJ')
        entry = objects[0]
        if not 0 < entry.file_size <= 512 * 1024**2:
            raise ValueError('Retopology OBJ exceeds size limit or is empty')
        with package.open(entry) as source, Path(target).open('wb') as output:
            total = 0
            for line in source:
                total += len(line)
                if total > 512 * 1024**2:
                    raise ValueError('Retopology OBJ exceeds size limit')
                words = line.split(None, 1)
                if words and words[0] in {b'v', b'vt', b'vn', b'f', b'o', b'g', b's'}:
                    output.write(line)
    return Path(target)


def prepare_handoff(config):
    root = Path(config['output']).resolve()
    plan = request_plan(config)
    if Path(plan['jobPath']) == Path(plan['file']) or Path(plan['jobPath']).is_relative_to(Path(plan['outputDir'])):
        raise ValueError('Retopology job must be separate from input and downloaded artifacts')
    (root / 'retopology-request.json').write_text(json.dumps({
        'tool': 'mdf_api', 'arguments': plan,
        'input_sha256': digest(plan['file']),
        'instructions': 'First dryRun=true, then execute the same plan through Runtime. Resume this local config after download. Never run a network client from shell.'
    }, indent=2) + '\n', encoding='utf-8')
    return resolve_result(config)
