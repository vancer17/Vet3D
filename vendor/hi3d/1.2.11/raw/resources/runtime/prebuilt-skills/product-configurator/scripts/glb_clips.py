"""Merge explicitly simultaneous GLB clips, preserving authored sample times."""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import tempfile


def read_glb(data):
    """Validate the container and return JSON plus untouched trailing chunks."""
    if len(data) < 20 or struct.unpack_from('<4sII', data) != (b'glTF', 2, len(data)):
        raise ValueError('Expected complete GLB 2.0')
    cursor, chunks = 12, []
    while cursor < len(data):
        if cursor + 8 > len(data):
            raise ValueError('Truncated chunk header')
        size, kind = struct.unpack_from('<I4s', data, cursor)
        end = cursor + 8 + size
        if size % 4 or end > len(data):
            raise ValueError('Truncated or unaligned GLB chunk')
        chunks.append((kind, data[cursor+8:end]))
        cursor = end
    if not chunks or chunks[0][0] != b'JSON' or any(k == b'JSON' for k, _ in chunks[1:]):
        raise ValueError('Expected one JSON first chunk')
    doc = json.loads(chunks[0][1])
    if not isinstance(doc, dict):
        raise ValueError('GLB JSON must be an object')
    return doc, chunks[1:]


def _index(value, items, label):
    if type(value) is not int or not 0 <= value < len(items):
        raise ValueError('Invalid ' + label + ' index')
    return items[value]


def _times(doc, chunks, index):
    """Read embedded, non-sparse float SCALAR times; reject unsupported storage."""
    accessor = _index(index, doc.get('accessors', []), 'time accessor')
    if accessor.get('componentType') != 5126 or accessor.get('type') != 'SCALAR' or 'sparse' in accessor:
        raise ValueError('Time accessor must be non-sparse float SCALAR')
    count = accessor.get('count')
    view = _index(accessor.get('bufferView'), doc.get('bufferViews', []), 'time bufferView')
    buffer = _index(view.get('buffer'), doc.get('buffers', []), 'time buffer')
    binaries = [p for kind, p in chunks if kind == b'BIN\x00']
    if view['buffer'] != 0 or 'uri' in buffer or len(binaries) != 1:
        raise ValueError('Time values must use the single embedded GLB buffer')
    offset, length = view.get('byteOffset', 0), view.get('byteLength')
    local, stride = accessor.get('byteOffset', 0), view.get('byteStride', 4)
    if (type(count) is not int or count < 1 or any(type(v) is not int for v in [offset,length,local,stride])
            or min(offset,local) < 0 or stride < 4 or stride % 4 or local + (count-1)*stride+4 > length
            or offset+length > min(len(binaries[0]), buffer.get('byteLength', 0))):
        raise ValueError('Invalid time accessor byte range')
    times = [struct.unpack_from('<f', binaries[0], offset+local+i*stride)[0] for i in range(count)]
    if any(not math.isfinite(t) or t < 0 for t in times) or any(b <= a for a,b in zip(times,times[1:])):
        raise ValueError('Animation times must be finite, nonnegative and strictly increasing')
    return times


def merge_bytes(data, *, clips, name, timeline='preserve', allowed_paths=None):
    """Pure transform. clips is explicit indices or the explicit string 'all'."""
    original, chunks = read_glb(data)
    animations = original.get('animations', [])
    indices = list(range(len(animations))) if clips == 'all' else list(clips)
    if not indices or len(set(indices)) != len(indices) or not name:
        raise ValueError('Select nonempty unique simultaneous clips and a name')
    if timeline not in ('preserve', 'shared_accessor'):
        raise ValueError('Unknown timeline policy')
    samplers, channels, targets, time_indices, ranges = [], [], set(), set(), {}
    for i in indices:
        animation = _index(i, animations, 'clip')
        if not animation.get('samplers') or not animation.get('channels'):
            raise ValueError('Empty animation')
        offset = len(samplers)
        for sampler in animation['samplers']:
            _index(sampler.get('output'), original.get('accessors', []), 'output accessor')
            index = sampler.get('input')
            times = _times(original, chunks, index)
            if sampler.get('interpolation', 'LINEAR') not in ('LINEAR', 'STEP', 'CUBICSPLINE'):
                raise ValueError('Unsupported sampler interpolation')
            time_indices.add(index); ranges[str(index)] = [times[0], times[-1], len(times)]
            samplers.append(copy.deepcopy(sampler))
        for source in animation['channels']:
            _index(source.get('sampler'), animation['samplers'], 'channel sampler')
            target = source.get('target', {})
            _index(target.get('node'), original.get('nodes', []), 'target node')
            path = target.get('path')
            if path not in ('translation', 'rotation', 'scale', 'weights') or (allowed_paths is not None and path not in allowed_paths):
                raise ValueError('Unsupported animation target path')
            pair = (target['node'], path)
            if pair in targets:
                raise ValueError('Conflicting simultaneous node/property channels')
            targets.add(pair)
            channel = copy.deepcopy(source); channel['sampler'] += offset; channels.append(channel)
    if timeline == 'shared_accessor' and len(time_indices) != 1:
        raise ValueError('Clips must share one identical time accessor')
    doc = copy.deepcopy(original)
    merged = {'name': name, 'samplers': samplers, 'channels': channels}
    # Replace at first selected position; preserve unselected clips and their order.
    doc['animations'] = [merged if i == min(indices) else a for i,a in enumerate(doc['animations']) if i not in indices or i == min(indices)]
    raw = json.dumps(doc, ensure_ascii=False, separators=(',', ':')).encode(); raw += b' ' * (-len(raw) % 4)
    rest = b''.join(struct.pack('<I4s', len(p), k)+p for k,p in chunks)
    result = struct.pack('<4sII', b'glTF', 2, 20+len(raw)+len(rest)) + struct.pack('<I4s', len(raw), b'JSON') + raw + rest
    report = {'before_sha256': hashlib.sha256(data).hexdigest(), 'after_sha256': hashlib.sha256(result).hexdigest(),
              'before_clip_count': len(animations), 'after_clip_count': len(doc['animations']),
              'selected_clips': indices, 'channel_count': len(channels), 'timeline_policy': timeline,
              'time_accessor_ranges': ranges, 'shared_time_accessor': next(iter(time_indices)) if len(time_indices)==1 else None,
              'binary_chunks_unchanged': True, 'non_animation_json_unchanged': True, 'retimed': False}
    return result, report


def merge_file(source, output, *, clips, name, timeline='preserve', allowed_paths=None, overwrite=False, in_place=False):
    """Explicit file adapter. Validation precedes writes; replacement is atomic."""
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output and not in_place:
        raise ValueError('In-place edit requires in_place=True')
    if source != output and output.exists() and not overwrite:
        raise FileExistsError(output)
    result, report = merge_bytes(source.read_bytes(), clips=clips, name=name, timeline=timeline, allowed_paths=allowed_paths)
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.'+output.name+'.', dir=output.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(result)
        if source != output and not overwrite:
            os.link(temporary, output)  # exclusive even when another writer races
        else:
            os.replace(temporary, output)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--clips', type=int, nargs='+'); group.add_argument('--all-simultaneous', action='store_true')
    parser.add_argument('--name', required=True); parser.add_argument('--timeline', choices=['preserve','shared_accessor'], default='preserve')
    parser.add_argument('--weights-only', action='store_true'); parser.add_argument('--in-place', action='store_true')
    parser.add_argument('--overwrite', action='store_true'); parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if args.report and args.report.resolve() in (args.input.resolve(), args.output.resolve()):
        raise ValueError('Report must not overwrite input or output GLB')
    report = merge_file(args.input,args.output,clips='all' if args.all_simultaneous else args.clips,name=args.name,
                        timeline=args.timeline,allowed_paths=['weights'] if args.weights_only else None,
                        overwrite=args.overwrite,in_place=args.in_place)
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True); args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
