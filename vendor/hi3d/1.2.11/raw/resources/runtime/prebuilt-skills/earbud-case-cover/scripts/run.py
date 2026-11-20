"""Rebuild a source-reviewed Hi3D product with explicit paths and config."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

from pathlib import Path
import sys
from stage_cli import cli_arguments, StageFinished, _finish_stage
from config_runtime import load_config, resolve_file_request
from process_run import run_checked, child_environment
from thin_source import thinning_parameters, thin_prepared_source

from product_cli import product_parser

def run(c, *, env):
    """Independently callable run operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    return run_checked(c, env=env)

def build_parser():
    return product_parser(__doc__)

def execute(a):
    """Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate."""
    s = Path(__file__).resolve().parent
    inputs, roots = resolve_file_request({'input': a.input, 'config': a.config},
        {'output': a.output, 'work_dir': a.work_dir}, package_root=s.parent)
    a.input, cfg = inputs['input'], inputs['config']
    a.output, a.work_dir = roots['output'], roots['work_dir']
    conf = load_config(cfg, required=('height_mm',))
    thinning = thinning_parameters(conf)
    if not float(conf['height_mm']) > 0:
        raise ValueError('height_mm must be positive')
    a.output.mkdir(parents=True, exist_ok=True)
    a.work_dir.mkdir(parents=True, exist_ok=True)
    env = child_environment(inherit=('PATH', 'TMPDIR', 'SYSTEMROOT', 'PYTHONPATH'), overrides={
        'PYTHONDONTWRITEBYTECODE': '1', 'ASTRA_SKIP_VIDEO': '1',
        'ASTRA_SKIP_SOURCE_VIEWS': '1' if a.skip_source_views else '0',
        'ASTRA_SKIP_STILLS': '1' if a.skip_stills else '0'})
    bl = [a.blender, '-b', '-t', '2', '--python-exit-code', '1', '--python']
    prepared = a.work_dir / 'prepared'
    run(bl + [str(s / 'prepare_source.py'), '--', str(a.input), str(prepared), str(conf['height_mm'])], env=env)
    from fit_source import fit_prepared_source
    fitted = a.work_dir / 'fitted'
    fit_prepared_source(prepared, fitted, conf)
    prepared = fitted
    if thinning is not None:
        thinned = a.work_dir / 'thinned'
        thin_prepared_source(prepared, thinned, conf)
        prepared = thinned
    run([sys.executable, str(s / 'build_solids.py'), str(prepared), str(a.output), str(cfg)], env=env)
    if a.stage == 'full':
        run(bl + [str(s / 'build_scene.py'), '--', '06', str(prepared), str(a.output), str(a.work_dir)], env=env)
    for variant in sorted(a.output.iterdir()):
        if not (variant / 'construction.json').exists():
            continue
        run([sys.executable, str(s / 'validate_stl.py'), str(variant / 'print'), '--json', str(variant / 'stl-validation.json')], env=env)
        if a.stage == 'full':
            if not a.no_video:
                run([sys.executable, str(s / 'render_video_chunks.py'), '--case', str(variant), '--work', str(a.work_dir / variant.name), '--blender', a.blender, '--spec', str(s.parent / 'assets' / 'render-spec.json')], env=env)
                run([sys.executable, str(s / 'encode_review.py'), str(variant), str(a.work_dir / variant.name), str(a.work_dir / variant.name)], env=env)
            if not a.skip_stills:
                run(bl + [str(s / 'lifestyle.py'), '--', '06', str(variant)], env=env)
            run(bl + [str(s / 'review_native.py'), '--', str(variant)], env=env)
            run(bl + [str(s / 'review_installation.py'), '--', str(variant)], env=env)
    if a.stage == 'full':
        run(bl + [str(s / 'fresh_review.py'), '--', '06', str(a.output)], env=env)
        run(bl + [str(s / 'native_dependencies.py'), '--', str(a.output)], env=env)
        run([sys.executable, str(s / 'glb_bounds.py'), str(a.output)], env=env)
    print('Generated:', a.output)

def main(argv=None):
    try:
        return execute(build_parser().parse_args(cli_arguments(argv)))
    except StageFinished as done:
        return done
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
