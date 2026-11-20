"""Local-only twisty-fidget entrypoint. Creates a new output directory per invocation."""
import argparse
from checkpoints import digest
import json
import math
import time
import uuid
from pathlib import Path
from timing import stage, utc_now, append_event


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def resolve_input(parent, value):
    path = Path(value).expanduser()
    path = path if path.is_absolute() else parent/path
    path = path.resolve()
    if not path.is_file():
        raise ValueError(f'missing input: {path}')
    return path


def load_assembly(manifest_path):
    from geometry import load_mesh, require_solid
    manifest_path = Path(manifest_path).resolve()
    manifest = read_json(manifest_path)
    if manifest['schema'] != 'twisty.assembly.v1' or manifest['unit'] != 'mm' or manifest['axis'] != 'Z' or manifest.get('origin_xy_mm') != [0, 0]:
        raise ValueError('unsupported assembly schema or coordinate convention')
    meshes = []
    for row in manifest['parts']:
        path = resolve_input(manifest_path.parent, row['file'])
        if digest(path) != row['sha256']:
            raise ValueError('part changed since assembly export; rebuild the manifest')
        mesh = load_mesh(path)
        require_solid(mesh)
        meshes.append(mesh)
    if len(meshes) != manifest['count'] or [r['part'] for r in manifest['parts']] != list(range(1, len(meshes)+1)):
        raise ValueError('ordered part numbers/count do not match the manifest')
    if manifest.get('assembled_stl'):
        row = manifest['assembled_stl']
        if digest(resolve_input(manifest_path.parent, row['file'])) != row['sha256']:
            raise ValueError('assembled print STL changed since export')
    return manifest, meshes


def export_parts(parts, out):
    from geometry import load_mesh, require_solid
    import trimesh
    (out/'parts').mkdir()
    rows, reloaded = [], []
    for i, part in enumerate(parts):
        file = f'parts/petal_{i+1:03d}.stl'
        part.export(out/file)
        mesh = load_mesh(out/file)
        metric = require_solid(mesh)
        reloaded.append(mesh)
        rows.append({'part': i+1, 'file': file, 'sha256': digest(out/file), 'metrics': metric})
    trimesh.util.concatenate(reloaded).export(out/'assembled_mm.stl')
    return rows, reloaded


def add_stops(args, out, timed):
    from stops import apply_stops, measure_stop_contacts
    from retention import require_stops
    with timed('stop_preflight'):
        manifest, meshes = load_assembly(args.assembly)
        spec = read_json(args.spec)
        if spec['assembly_method'] != 'print_in_place':
            raise ValueError('closed integral stops require print_in_place; removable-stop assembly is not implemented')
        if manifest.get('axial_stops'):
            raise ValueError('assembly already has stops; restart from its retained unstopped input')
        require_stops(dict(manifest, axial_stops=spec))
        step, k = float(spec['step_mm']), manifest['k_deg_per_mm']
    with timed('stop_geometry'):
        parts, attachments = apply_stops(meshes, spec['interfaces'], k, step)
    with timed('export_stl'):
        rows, reloaded = export_parts(parts, out)
        result = dict(manifest, parts=rows, axial_stops=spec,
                      assembled_stl={'file': 'assembled_mm.stl', 'sha256': digest(out/'assembled_mm.stl')},
                      prior_assembly_sha256=digest(args.assembly), stop_spec_sha256=digest(args.spec))
        write_json(out/'assembly.json', result)
    with timed('stop_contacts'):
        contacts = measure_stop_contacts(reloaded, spec['interfaces'], k,
                                        args.contact_probe_mm, args.overlap_tolerance_mm3)
        report = {'assembly_sha256': digest(out/'assembly.json'), 'attachments': attachments,
                  'contact_probe_mm': args.contact_probe_mm, 'overlap_tolerance_mm3': args.overlap_tolerance_mm3,
                  'contacts': contacts, 'all_passed': all(r['passed'] for r in contacts),
                  'scope': 'Named screw-path end barriers only; run normal-motion validation and review wall thickness, capture and printing separately.'}
        write_json(out/'stop_contacts.json', report)
        if not report['all_passed']:
            raise ValueError('stop endpoint check failed; see stop_contacts.json')


def inspect_input(args, out, timed):
    from geometry import load_mesh, metrics, section_loops
    with timed('reference_inspection'):
        mesh = load_mesh(args.input, args.scale_to_mm)
        parts = sorted(mesh.split(only_watertight=False), key=lambda m: abs(m.volume), reverse=True)
        rows = []
        for i, part in enumerate(parts):
            filename = f'part_{i+1:03d}.ply'
            part.export(out/filename)
            rows.append({'part': i+1, 'file': filename, 'metrics': metrics(part),
                         'sections': section_loops(part, args.sections or [])})
        result = {'input_sha256': digest(args.input), 'scale_to_mm': args.scale_to_mm,
                  'metrics': metrics(mesh), 'parts': rows,
                  'scope': 'Connected components and Z sections; axis, interlock and pitch require interpretation.'}
        write_json(out/'inspection.json', result)


def build(args, out, timed):
    from geometry import load_mesh, require_solid, adapt_profile, helical_parts
    from motion import offsets
    with timed('preflight'):
        job_path = Path(args.job).resolve()
        job = read_json(job_path)
        mesh_path = resolve_input(job_path.parent, job['mesh'])
        profile_path = resolve_input(job_path.parent, job['profile'])
        count = job['count']
        offsets(count, 0, 'staircase')
        k, step = float(job['k_deg_per_mm']), float(job['step_mm'])
        if not math.isfinite(k) or k == 0 or not math.isfinite(step) or step <= 0 or abs(k)*step >= 180:
            raise ValueError('finite nonzero k, positive step and less than 180 degrees per sweep step required')
        mesh = load_mesh(mesh_path, float(job['scale_to_mm']))
        original = require_solid(mesh)
        profile = read_json(profile_path)
    with timed('profile_adaptation'):
        points, clearance = adapt_profile(profile['points_xy_mm'], profile['source_count'], count,
            float(job['radial_scale']), float(job['inset_mm']), float(job['profile_sample_mm']))
        write_json(out/'profile.json', {'source_count': count, 'points_xy_mm': points.tolist(),
                                      'same_z_profile_gap_mm': clearance})
    with timed('helical_partition'):
        parts = helical_parts(mesh, points, count, k, step)
    with timed('export_stl'):
        rows, _ = export_parts(parts, out)
        write_json(out/'assembly.json', {'schema': 'twisty.assembly.v1', 'unit': 'mm',
            'axis': 'Z', 'origin_xy_mm': [0, 0], 'count': count, 'k_deg_per_mm': k,
            'source_metrics': original, 'source_sha256': digest(mesh_path),
            'source_profile_sha256': digest(profile_path), 'configuration': job,
            'assembled_stl': {'file': 'assembled_mm.stl', 'sha256': digest(out/'assembled_mm.stl')},
            'same_z_profile_gap_mm': clearance, 'parts': rows})


def validate(args, out, timed):
    from geometry import measure_states
    from motion import offsets, adjacent_overlap, stop_travel_limits
    from retention import require_stops
    with timed('export_reimport'):
        manifest_path = Path(args.assembly).resolve()
        manifest, meshes = load_assembly(manifest_path)
        positions = offsets(len(meshes), args.travel_mm, args.mode)
        if args.samples < 2:
            raise ValueError('samples must include closed and open states')
        intervals = read_json(args.intervals)['intervals_mm'] if args.intervals else None
        if intervals is not None:
            adjacent_overlap(intervals, positions)
        connection = None
        if not args.study_only:
            connection = require_stops(manifest)
            if intervals is None or read_json(args.intervals).get('assembly_sha256') != digest(manifest_path):
                raise ValueError('default validation requires measured intervals bound to this final assembly; use --study-only for diagnosis')
            if args.samples < 3:
                raise ValueError('retention motion requires closed, intermediate and open samples')
    with timed('full_mesh_collisions'):
        states = measure_states(meshes, positions, manifest['k_deg_per_mm'],
            [i/(args.samples-1) for i in range(args.samples)], args.overlap_tolerance_mm3)
    engagement = None
    if intervals is not None:
        with timed('rail_overlap'):
            engagement = adjacent_overlap(intervals, positions)
    ranges = stop_travel_limits(positions, manifest.get('axial_stops', {}).get('interfaces', []))
    result = {'stop_travel_limits': ranges, 'schema': 'twisty.validation.v1', 'assembly_sha256': digest(manifest_path),
        'purpose': 'study_only' if args.study_only else 'retention_motion', 'connection': connection,
        'part_sha256': [r['sha256'] for r in manifest['parts']], 'mode': args.mode,
        'travel_mm': args.travel_mm, 'offsets_mm': positions,
        'overlap_tolerance_mm3': args.overlap_tolerance_mm3, 'states': states,
        'pair_check_total': sum(s['pair_checks'] for s in states),
        'sampled_collision_free': all(not s['collisions'] for s in states),
        'rail_overlap': engagement, 'rail_interval_source': None if intervals is None else
            {'sha256': digest(args.intervals), 'status': 'caller-measured intervals; capture not verified by this script'},
        'scope': 'Sampled geometry only; no force, friction, synchronization or axial retention certification.'}
    write_json(out/'validation.json', result)
    if any(not row['within_limits'] for row in ranges):
        raise ValueError('requested motion crosses a stop limit; see validation.json')
    if not result['sampled_collision_free']:
        raise ValueError('sampled solid collision detected; see validation.json')
    if engagement is not None and any(r['overlap_mm'] <= 0 for r in engagement):
        raise ValueError('neighboring rail intervals disengage; see validation.json')


def accept(args, out, timed):
    from retention import check_evidence
    result = {'schema': 'twisty.acceptance.v1', 'passed': False}
    try:
        with timed('acceptance_inputs'):
            manifest, _ = load_assembly(args.assembly)
            if not manifest.get('assembled_stl'):
                raise ValueError('acceptance requires the assembled print STL bound in the manifest')
            assembly_hash = digest(args.assembly)
            bundle_path = Path(args.evidence).resolve()
            bundle = read_json(bundle_path)
            result.update(assembly_sha256=assembly_hash, evidence_sha256=digest(bundle_path))
            verified = []
            def verify_file(ref):
                path = resolve_input(bundle_path.parent, ref['file'])
                if path.stat().st_size == 0 or digest(path) != ref['sha256']:
                    raise ValueError(f'empty or changed evidence file: {path}')
                verified.append(dict(ref))
                return path
            def read_artifact(ref):
                return read_json(verify_file(ref))
        with timed('retention_acceptance'):
            result.update(check_evidence(manifest, assembly_hash, bundle, read_artifact, verify_file))
            result.update(passed=True, verified_files=verified)
    except (ValueError, KeyError, TypeError, OSError, IndexError, OverflowError) as exc:
        result['failure'] = f'{type(exc).__name__}: {exc}'
        raise ValueError('retention acceptance failed; see acceptance.json') from exc
    finally:
        write_json(out/'acceptance.json', result)


def measure_capture_command(args, out, timed):
    from capture import measure_capture
    with timed('capture_preflight'):
        manifest, meshes = load_assembly(args.assembly)
        spec = read_json(args.spec)
    with timed('final_mesh_capture_sections'):
        report = measure_capture(meshes, manifest, spec, digest(args.assembly))
        report['spec_sha256'] = digest(args.spec)
        write_json(out/'capture.json', report)
        if not report['all_passed']:
            raise ValueError('numeric capture failed; see capture.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    inspection = sub.add_parser('inspect', help='Extract components and Z sections; no mechanism guessing')
    inspection.add_argument('--input', required=True)
    inspection.add_argument('--scale-to-mm', type=float, required=True)
    inspection.add_argument('--sections', type=float, nargs='*')
    builder = sub.add_parser('build', help='Partition an already prepared closed target with a reviewed profile')
    builder.add_argument('--job', required=True)
    validator = sub.add_parser('validate', help='Default: complete stop ring and bound intervals, then sampled motion checks')
    validator.add_argument('--assembly', required=True)
    validator.add_argument('--travel-mm', type=float, required=True)
    validator.add_argument('--mode', choices=['staircase', 'wave'], required=True)
    validator.add_argument('--samples', type=int, required=True)
    validator.add_argument('--overlap-tolerance-mm3', type=float, required=True)
    validator.add_argument('--intervals', help='Assembly-bound measured intervals_mm, one [lo,hi] per petal')
    validator.add_argument('--study-only', action='store_true', help='Explicit diagnostic scope; cannot qualify for final acceptance')
    stopper = sub.add_parser('add-stops', help='Add reviewed integral tongues and closed-ended helical pockets')
    stopper.add_argument('--assembly', required=True)
    stopper.add_argument('--spec', required=True)
    stopper.add_argument('--contact-probe-mm', type=float, required=True)
    stopper.add_argument('--overlap-tolerance-mm3', type=float, required=True)
    acceptance = sub.add_parser('accept', help='Mandatory final whole-ring and hash-bound evidence acceptance')
    acceptance.add_argument('--assembly', required=True)
    acceptance.add_argument('--evidence', required=True)
    capture = sub.add_parser('measure-capture', help='Measure both shoulders, play and walls on every final-mesh interface')
    capture.add_argument('--assembly', required=True)
    capture.add_argument('--spec', required=True)
    for command in [inspection, builder, validator, stopper, acceptance, capture]:
        command.add_argument('--out', required=True, help='New directory outside the skill package')
        command.add_argument('--task-id', required=True)
        command.add_argument('--previous-attempt-id')
    args = parser.parse_args()
    out = Path(args.out).expanduser().resolve()
    package = Path(__file__).resolve().parents[1]
    if out == package or package in out.parents:
        parser.error('runtime output must be outside the skill package')
    out.mkdir(parents=True, exist_ok=False)
    attempt = uuid.uuid4().hex
    started, clock = utc_now(), time.monotonic()
    entered = set()
    planned = {'inspect': ['reference_inspection'],
               'build': ['preflight', 'profile_adaptation', 'helical_partition', 'export_stl'],
               'validate': ['export_reimport', 'full_mesh_collisions', 'rail_overlap'],
               'accept': ['acceptance_inputs', 'retention_acceptance'],
               'measure-capture': ['capture_preflight', 'final_mesh_capture_sections'],
               'add-stops': ['stop_preflight', 'stop_geometry', 'export_stl', 'stop_contacts']}[args.action]
    def timed(name):
        entered.add(name)
        return stage(out/'timings.jsonl', args.task_id, attempt, name, args.previous_attempt_id)
    status, error = 'completed', None
    try:
        {'inspect': inspect_input, 'build': build, 'validate': validate, 'add-stops': add_stops,
         'accept': accept, 'measure-capture': measure_capture_command}[args.action](args, out, timed)
    except BaseException as exc:
        status = 'interrupted' if isinstance(exc, (KeyboardInterrupt, SystemExit)) else 'failed'
        error = type(exc).__name__
        raise
    finally:
        for name in planned:
            if name not in entered:
                append_event(out/'timings.jsonl', {'task_id': args.task_id, 'attempt_id': attempt,
                    'previous_attempt_id': args.previous_attempt_id, 'stage': name, 'status': 'skipped',
                    'started_at': None, 'ended_at': None, 'elapsed_seconds': None,
                    'reason': 'no measured rail intervals supplied' if status == 'completed' else
                              'prior stage failed or was interrupted'})
        write_json(out/'timing_summary.json', {'task_id': args.task_id, 'attempt_id': attempt,
            'previous_attempt_id': args.previous_attempt_id, 'status': status, 'error_type': error,
            'started_at': started, 'ended_at': utc_now(), 'elapsed_seconds': time.monotonic()-clock,
            'scope': args.action+' command only; not complete business or visual-review duration'})
    print(out)


if __name__ == '__main__':
    main()
