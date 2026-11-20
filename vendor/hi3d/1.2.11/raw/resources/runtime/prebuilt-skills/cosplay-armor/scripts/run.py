"""Replay independently localized forearm or shin armor using explicit Hi3D body and art inputs."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

from pathlib import Path
import argparse, json, subprocess, os, sys, hashlib, shutil, time, re
import importlib.util
from stage_cli import cli_arguments, StageFinished, _finish_stage
from path_safety import validate_write_roots

def sha(file):
    """Independently callable sha operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    return hashlib.sha256(file.read_bytes()).hexdigest()

def run(name, cmd, *, a, commands, env):
    """Independently callable run operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    log = a.work / (name + '.log')
    print('RUN', name, flush=True)
    start = time.monotonic()
    with log.open('w') as f:
        ret = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, env=env)
    commands.append({'phase': name, 'exit_code': ret.returncode, 'seconds': round(time.monotonic() - start, 3), 'log': log.name})
    (a.out / 'run-phases.json').write_text(json.dumps(commands, indent=2))
    if ret.returncode:
        raise RuntimeError(f'{name} failed; inspect {log}')

def build_parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--arm-glb', '--body-glb', dest='arm_glb', type=Path, required=True)
    for flag in ['armor-glb', 'out', 'work']:
        p.add_argument('--' + flag, type=Path, required=True)
    p.add_argument('--body-region', choices=['forearm', 'shin'], default='forearm')
    p.add_argument('--armor-center-mode', choices=['fitted', 'fixed'], default='fitted')
    p.add_argument('--armor-center-x-mm', type=float, default=0)
    p.add_argument('--armor-center-y-mm', type=float, default=0)
    p.add_argument('--body-yaw-deg', type=float, default=0)
    p.add_argument('--armor-yaw-deg', type=float, default=0)
    p.add_argument('--blender', required=True)
    p.add_argument('--arm-length-mm', '--body-length-mm', dest='arm_length_mm', type=float, required=True)
    p.add_argument('--forearm-start-mm', '--fit-start-mm', dest='forearm_start_mm', type=float, required=True)
    p.add_argument('--forearm-end-mm', '--fit-end-mm', dest='forearm_end_mm', type=float, required=True)
    for flag, value in [('transverse-scale', 1), ('inner-clearance-mm', 5), ('pad-thickness-mm', 8), ('strap-skin-offset-mm', 1.4)]:
        p.add_argument('--' + flag, type=float, default=value)
    p.add_argument('--variant-name', default='standard')
    p.add_argument('--skip-source-renders', action='store_true')
    p.add_argument('--skip-renders', action='store_true')
    return p

def execute(a):
    """Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate."""
    scripts = Path(__file__).resolve().parent
    if a.body_region == 'shin' and any((getattr(a, k) is None for k in ['arm_length_mm', 'forearm_start_mm', 'forearm_end_mm'])):
        raise ValueError('Shin requires independently inspected body length and explicit fit-start/end; forearm defaults cannot be reused')
    for key in ['arm_glb', 'armor_glb', 'out', 'work']:
        setattr(a, key, getattr(a, key).resolve())
    validate_write_roots({'out': a.out, 'work': a.work}, package_root=scripts.parent, protected_inputs=[a.arm_glb, a.armor_glb])
    if not a.arm_glb.is_file() or not a.armor_glb.is_file():
        raise ValueError('Both local source GLBs must exist')
    if not re.fullmatch('[a-z0-9][a-z0-9-]*', a.variant_name):
        raise ValueError('variant-name uses lowercase letters, digits and hyphens')
    if not 15 < a.forearm_start_mm < a.forearm_end_mm < a.arm_length_mm - 20:
        raise ValueError('Fit range plus sampling margins must lie inside body length')
    if min(a.transverse_scale, a.inner_clearance_mm, a.pad_thickness_mm, a.strap_skin_offset_mm) <= 0:
        raise ValueError('Scale and clearances must be positive')
    missing = [m for m in ['numpy', 'scipy', 'manifold3d'] if importlib.util.find_spec(m) is None]
    if missing:
        raise ValueError('Install Python dependencies before running geometry phases: ' + ', '.join(missing))
    a.out.mkdir(parents=True, exist_ok=True)
    a.work.mkdir(parents=True, exist_ok=True)
    config = {k: v for k, v in vars(a).items() if k not in ['arm_glb', 'armor_glb', 'blender']}
    config.update(out=str(a.out), work=str(a.work), armor_profile_height_mm=230, source_renders=not a.skip_source_renders)
    conf_path = a.work / 'config.json'
    conf_path.write_text(json.dumps(config, indent=2))
    shutil.copy2(conf_path, a.out / 'parameters.json')
    env = {key: os.environ[key] for key in ('PATH', 'TMPDIR', 'SYSTEMROOT', 'PYTHONPATH') if key in os.environ}

    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PYTHONPATH'] = str(scripts) + os.pathsep + env.get('PYTHONPATH', '')
    provenance = []
    for label, file in [('arm', a.arm_glb), ('armor', a.armor_glb)]:
        d = a.out / 'source' / label
        d.mkdir(parents=True, exist_ok=True)
        target = d / 'api-result.glb'
        if target != file:
            shutil.copy2(file, target)
        provenance.append({'source': label, 'input_name': file.name, 'sha256': sha(file), 'delivered_original': str(target.relative_to(a.out)), 'origin': 'Caller-supplied local geometry; this offline entry cannot authenticate its upstream origin and makes no API calls.'})
    (a.out / 'source-provenance.json').write_text(json.dumps(provenance, indent=2))
    commands = []
    bl = [a.blender, '-b', '-t', '2', '--python-exit-code', '1', '--python']
    for label, file, height in [('arm', a.arm_glb, a.arm_length_mm), ('armor', a.armor_glb, 230)]:
        cmd = bl + [str(scripts / 'inspect_source.py'), '--', str(file), str(a.work / (label + '-inspection')), str(height), '--yaw-deg', str(a.body_yaw_deg if label == 'arm' else a.armor_yaw_deg)]
        if a.skip_source_renders:
            cmd += ['--skip-render']
        run('inspect-' + label, cmd, a=a, commands=commands, env=env)
    for phase, file in [('profiles', 'sample_profiles.py'), ('build', 'build_armor.py'), ('finalize', 'finalize.py')]:
        run(phase, bl + [str(scripts / file), '--', '--config', str(conf_path)], a=a, commands=commands, env=env)
    run('validate-stl', [sys.executable, str(scripts / 'validate_stl.py'), str(a.out / a.variant_name / 'print'), '--json', str(a.out / 'stl-validation.json')], a=a, commands=commands, env=env)
    run('fresh-import', bl + [str(scripts / 'validate_assets.py'), '--', str(a.out / a.variant_name)], a=a, commands=commands, env=env)
    run('attachment-check', bl + [str(scripts / 'validate_attachments.py'), '--', str(a.out / a.variant_name / 'scene.blend'), str(a.out / a.variant_name / 'attachment-check.json')], a=a, commands=commands, env=env)
    for source in ['arm', 'armor']:
        shutil.copy2(a.work / (source + '-inspection/source-inspection.json'), a.out / (source + '-source-inspection.json'))
    shutil.copy2(a.work / 'fit-profile-summary.json', a.out / 'fit-profile-summary.json')
    files = [f for f in sorted(a.out.rglob('*')) if f.is_file() and f.suffix in ['.glb', '.stl', '.blend']]
    report = {'entry': 'run.py', 'status': 'completed', 'phases': commands, 'parameters': config, 'source_provenance': provenance, 'files': [{'file': str(f.relative_to(a.out)), 'bytes': f.stat().st_size, 'sha256': sha(f)} for f in files], 'scope': 'Actual high-resolution geometry, STL/native and preview GLB. Render skipping explicit. No physical fit, slicer or body calibration claim.'}
    (a.out / 'run-validation.json').write_text(json.dumps(report, indent=2))
    print('COMPLETE', a.out, flush=True)

def main(argv=None):
    try:
        return execute(build_parser().parse_args(cli_arguments(argv)))
    except StageFinished as done:
        return done
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
