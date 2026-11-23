"""Validate a request or run a local Blender attachment candidate; no cloud calls."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import uuid

PACKAGE = Path(__file__).resolve().parents[1]
# Blender --python does not add the script's directory to sys.path.
sys.path.insert(0, str(PACKAGE/'scripts'))
from stage_events import record_stage
from checkpoints import digest


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def prepare(args):
    from geometry import number, validate
    source = Path(args.input).expanduser().resolve(strict=True)
    specification = Path(args.spec).expanduser().resolve(strict=True)
    output = Path(args.out).expanduser().resolve()
    if source.suffix.lower() not in ('.blend', '.glb', '.gltf', '.obj', '.stl'):
        raise ValueError('Unsupported source format')
    if output.exists() or output == PACKAGE or PACKAGE in output.parents:
        raise ValueError('Output must be a NEW task directory outside the skill package')
    unit = number(args.input_unit_mm, 'input_unit_mm', 0, True)
    spec = validate(json.loads(specification.read_text(encoding='utf-8')))
    return source, output, unit, spec


def execute(args):
    source, output, unit, spec = prepare(args)
    if args.check:
        return {'execution_status': 'preflight_only', 'source': str(source),
                'input_unit_mm': unit, 'specification': spec, 'writes': False}
    import bpy
    if not bpy.app.background:
        raise RuntimeError('Run in a separate Blender --background process; active UI scenes are not supported')
    from blender_ops import load_body, weld_exact, topology, apply_interface, connector_check, save_exports
    from audit import local_crossings
    output.mkdir(parents=True, exist_ok=False)
    identity = dict(task_id=args.task_id, attempt_id=uuid.uuid4().hex,
                    previous_attempt_id=args.previous_attempt_id)
    start = time.monotonic(); started_at = datetime.now(timezone.utc).isoformat()
    records = []
    report = dict(**identity, execution_status='running', quality_status='not_tested',
                  source=str(source), source_sha256=digest(source), input_unit_mm=unit,
                  spec=spec, checks={})
    write_json(output/'request.json', report)

    def event(record):
        with (output/'timings.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(dict(identity, **record), ensure_ascii=False, allow_nan=False)+'\n')

    def stage(name):
        return record_stage(name, event, records, missing_reason='End not yet observed', timing_method=None)

    try:
        with stage('load_working_copy'):
            body=load_body(source, args.target, unit)
            weld_exact(body.data)
            before=topology(body.data); report['checks']['source_topology']=before
            if before['non_manifold_edges'] or before['inconsistent_winding_edges'] or before['signed_volume_mm3'] <= 0 or not before['finite_coordinates']:
                raise ValueError('Source needs an explicit closed, outward-oriented working mesh before Boolean processing')
        with stage('model_interface'):
            operand, connector=apply_interface(body, spec)
        with stage('structural_diagnostics'):
            after=topology(body.data); report['checks']['result_topology']=after
            report['checks']['connector']=connector_check(body, connector)
            report['checks']['local_crossings']=local_crossings(body, operand, spec.get('audit_padding_mm', 1))
            delta=after['signed_volume_mm3']-before['signed_volume_mm3']
            effect_ok=delta < -1e-6 if spec['mode']=='tunnel' else delta > 1e-6 and after['components'] <= before['components']
            report['checks']['boolean_effect']={'volume_delta_mm3':delta, 'status':'observed' if effect_ok else 'fail'}
            known_failure=after['non_manifold_edges'] or after['inconsistent_winding_edges'] or after['signed_volume_mm3']<=0 or not after['finite_coordinates'] or not effect_ok
            known_failure |= any(report['checks'][k]['status']=='fail' for k in ('connector','local_crossings'))
            report['quality_status']='fail' if known_failure else 'not_tested'
        with stage('save_exports'):
            save_exports(body, connector, output, spec)
        report['artifacts']={name:{'sha256':digest(output/name), 'bytes':(output/name).stat().st_size}
                             for name in ('assembly.blend','assembly.glb','body_mm.stl')}
        report['execution_status']='completed'
        report['remaining_checks']=['site/centre-of-mass selection','two usable ports or lug root continuity',
                                    'local wall/bridge sampling','adjacent-face folding if suspected',
                                    'full assembly and insertion','fresh import and visual review','physical testing if required']
    except BaseException as exc:
        report['execution_status']='interrupted' if isinstance(exc,(KeyboardInterrupt,SystemExit)) else 'failed'
        report['error_type']=type(exc).__name__
        raise
    finally:
        observed = {record['stage'] for record in records}
        for name in ('load_working_copy', 'model_interface', 'structural_diagnostics', 'save_exports'):
            if name not in observed:
                record=dict(stage=name, status='skipped', started_at=None, ended_at=None,
                            elapsed_seconds=None, missing_reason='Earlier stage did not complete')
                event(record); records.append(record)
        write_json(output/'report.json',report)
        write_json(output/'timing_summary.json',dict(identity, started_at=started_at,
                   ended_at=datetime.now(timezone.utc).isoformat(), elapsed_seconds=time.monotonic()-start,
                   status=report['execution_status'], stages=records,
                   scope='This CLI attempt after preflight; interval, not sum. Excludes research, input analysis, external generation, rendering and human visual review.'))
    return report


def main(argv=None):
    argsv=list(sys.argv[1:] if argv is None else argv)
    if '--' in argsv: argsv=argsv[argsv.index('--')+1:]
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--describe',action='store_true')
    parser.add_argument('--input'); parser.add_argument('--target'); parser.add_argument('--spec')
    parser.add_argument('--input-unit-mm',type=float); parser.add_argument('--out')
    parser.add_argument('--task-id',default='keychain'); parser.add_argument('--previous-attempt-id')
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args(argsv)
    if args.describe:
        print(json.dumps({'skill':'keychain','modes':['tunnel','lug'],
                          'unit':'Explicit mm per imported world-coordinate unit',
                          'geometry_contract':'references/runtime.md',
                          'candidate_outputs':['assembly.blend','assembly.glb','body_mm.stl','report.json','timings.jsonl'],
                          'quality':'CLI produces a candidate, never a manufacturing approval'},ensure_ascii=False,indent=2))
        return 0
    for name in ('input','spec','input_unit_mm','out'):
        if getattr(args,name) is None: parser.error('--'+name.replace('_','-')+' is required')
    try:
        report=execute(args)
    except Exception as exc:
        print(type(exc).__name__+': '+str(exc),file=sys.stderr)
        return 1
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 2 if report.get('quality_status')=='fail' else 0


if __name__=='__main__':
    raise SystemExit(main())
