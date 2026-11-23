"""Source-bound local facial registration; consumes an existing analysis directory."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from scipy.spatial import cKDTree
from process_run import run_budgeted
from timing import stage


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def summarize(vertices, target, landmarks, fit_indices):
    """Diagnostic distances, never an anatomical acceptance predicate (Blender coordinates)."""
    def stats(values):
        values = np.asarray(values)
        if not len(values):
            raise ValueError('Empty diagnostic region')
        return dict(count=len(values), rms=float(np.sqrt(np.mean(values**2))),
                    p95=float(np.percentile(values, 95)), maximum=float(values.max()))
    tree = cKDTree(target)
    extent = float(np.ptp(target, axis=0).max())
    if not np.isfinite(extent) or extent <= 0:
        raise ValueError('Invalid target extent')
    groups = {}
    for group in sorted({x['group'] for x in landmarks}):
        rows = [x for x in landmarks if x['group'] == group]
        groups[group] = stats(np.linalg.norm(vertices[[x['vertex_index'] for x in rows]]-
                                            np.array([x['target'] for x in rows]), axis=1))
    # Fixed Taro nasal anchors. This diagnostic bounds observed points only;
    # it neither creates an editable ROI nor measures invisible nostril anatomy.
    root, tip, bottom, left, right = vertices[[15849, 17088, 2917, 7193, 18576]]
    anchors = np.array([root, tip, bottom, left, right])
    lo, hi = anchors.min(0), anchors.max(0)
    pad = np.maximum((hi-lo)*.25, extent*.005)
    ids = np.asarray(fit_indices, dtype=int)
    nasal = ids[np.all((vertices[ids] >= lo-pad) & (vertices[ids] <= hi+pad), axis=1)]
    nose = stats(tree.query(vertices[nasal])[0])
    nose['p95_fraction_of_target_extent'] = nose['p95']/extent
    return dict(landmark_groups=groups, nose_observed_surface=nose,
                visible_target_extent=extent, units='source model coordinate units',
                scope='Nearest sampled skin distances; not nostril anatomy or seam certification')


def report(config):
    out = Path(config['output'])
    fit = dict(np.load(out/'fit/brush_fit.npz', allow_pickle=False))
    settings = json.loads((out/'fit/observed_face_settings.json').read_text())
    target = np.load(out/'target.npz', allow_pickle=False)
    geometry = json.loads((out/'geometry.json').read_text())
    result = summarize(fit['vertices'], target['vertices'], settings['landmarks'], settings['fit_indices'])
    anchors = fit['vertices'][[15849,17088,2917,7193,18576]]
    padding = (anchors.max(0)-anchors.min(0))*.3
    inside = np.all((fit['vertices'] >= anchors.min(0)-padding) &
                    (fit['vertices'] <= anchors.max(0)+padding),axis=1)
    q=fit['quads'];tri=np.concatenate([q[:,[0,1,2]],q[:,[0,2,3]]])
    pairs=np.asarray(geometry['new_pairs'],dtype=int).reshape(-1,2)
    touched=pairs[np.any(inside[tri[pairs]],axis=(1,2))]
    result['new_crossings_touching_nose_box']=len(touched)
    result['nose_box_scope']='Anchor bounds expanded 30%; new crossings only, not complete seam or baseline contact certification'
    result.update(source_sha256=digest(config['source']),
                  donor_sha256=digest(out/'registered_glb_coordinates.npz'),
                  full_template_geometry=geometry,
                  status='fitted_pending_local_visual_review',
                  nose_repair_approved=False)
    (out/'face_fit_report.json').write_text(json.dumps(result, indent=2))
    return result


def run(config_path, blender, max_wall_seconds=180, review_fit=False):
    config_path = Path(config_path).resolve()
    config = json.loads(config_path.read_text())
    out = Path(config['output']).resolve()
    scripts = Path(__file__).resolve().parent
    for name in (['registered.glb', 'registered_glb_coordinates.npz', 'face_fit_report.json'] + ([] if review_fit else ['fit'])):
        if (out/name).exists():
            raise FileExistsError('Existing registration; use a new attempt directory')
    required = ['front.png','camera.json','surface_raw.npz','visibility.npz',
                'service_binding.json','service/invocation.json']
    for name in required:
        if not (out/name).is_file():
            raise FileNotFoundError(out/name)
    source_hash = digest(config['source'])
    records = out/'face-fit-timings.jsonl'
    def call(name, command):
        with stage(records, name, task_id=str(out)):
            run_budgeted(command, out/(name+'.log'), max_wall_seconds=max_wall_seconds,
                         heartbeat_path=out/(name+'-heartbeat.json'))
    def python(name, arg):
        return [sys.executable,str(scripts/name),str(arg)]
    def blend(name, *args):
        return [blender,'--background','--factory-startup','--python-exit-code','1',
                '--python',str(scripts/name),'--',*map(str,args)]
    if review_fit:
        fit = np.load(out/'fit/brush_fit.npz', allow_pickle=False)
        previous = json.loads((out/'fit/brush_report.json').read_text())
        if str(fit['source_sha256']) != source_hash or previous['target_sha256'] != digest(out/'target.npz') or previous['template_sha256'] != digest(scripts.parent/'assets/taro/template.npz'):
            raise ValueError('Existing fit source/target/template mismatch')
    else:
        call('prepare',python('prepare_sapiens_settings.py',config_path))
        call('project',blend('project_sapiens2_landmarks.py',out/'project.json'))
        call('fit',python('fit_visible_face.py',out/'registration.json'))
    call('geometry',blend('check_geometry.py',out/'fit/brush_fit.npz',out/'geometry.json'))
    export_config = dict(config,export_fit=str(out/'fit/brush_fit.npz'))
    (out/'export-config.json').write_text(json.dumps(export_config,indent=2))
    call('export',python('export_sapiens_registration.py',out/'export-config.json'))
    if digest(config['source']) != source_hash:
        raise ValueError('Source model changed during fitting')
    with stage(records,'local_metrics',task_id=str(out)):
        return report(config)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('config',type=Path)
    p.add_argument('--blender',required=True)
    p.add_argument('--max-wall-seconds',type=float,default=180)
    p.add_argument('--review-fit',action='store_true',help='Explicitly check/export an existing source-bound fit; no refitting')
    a=p.parse_args()
    result=run(a.config,a.blender,a.max_wall_seconds,a.review_fit)
    print(json.dumps({k:v for k,v in result.items() if k!='full_template_geometry'},indent=2))


if __name__=='__main__':
    main()
