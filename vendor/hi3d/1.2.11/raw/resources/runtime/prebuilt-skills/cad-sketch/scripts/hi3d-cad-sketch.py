"""Build/edit dimension-constrained FreeCAD sketches and native solid features."""
import argparse,json,re
from pathlib import Path
import importlib
_job_api=importlib.import_module('hi3d-edit-job')
EditJob=_job_api.EditJob
local_file=_job_api.local_file
number=_job_api.number
dump=_job_api.dump


def validate(spec):
    if spec.get('schemaVersion')!=1 or spec.get('unit')!='mm' or set(spec)-{'schemaVersion','unit','source','body','operations','budgetSeconds'}:raise ValueError('schemaVersion=1 and unit=mm required')
    if not re.fullmatch('[A-Za-z][A-Za-z0-9_]*',spec.get('body','Body')):raise ValueError('invalid body id')
    if not isinstance(spec.get('operations'),list) or not spec['operations']:raise ValueError('operations required')
    ids=set()
    for op in spec['operations']:
        kind=op['op']
        allowed={'rectangle':{'id','width','height','x','y','z'},'circle':{'id','radius','x','y','z'},'pad':{'id','sketch','length'},'pocket':{'id','sketch','length'},'dimension':{'sketch','name','value'}}
        if kind not in allowed or set(op)-allowed[kind]-{'op'}:raise ValueError('unknown CAD operation/field')
        if 'id' in op:
            if not re.fullmatch('[A-Za-z][A-Za-z0-9_]*',op['id']) or op['id'] in ids:raise ValueError('duplicate/invalid id')
            ids.add(op['id'])
        for key in ('width','height','radius','length','value'):
            if key in op:number(op[key],key,0,True)
        for key in ('x','y','z'):
            if key in op:number(op[key],key,-1e6)
        for key in ({'rectangle':['width','height'],'circle':['radius'],'pad':['sketch','length'],'pocket':['sketch','length'],'dimension':['sketch','name','value']}[kind]):
            if key not in op:raise ValueError('missing '+key)


def execute(spec_path,output,freecad):
    path=Path(spec_path).resolve();spec=json.loads(path.read_text());validate(spec);inputs=[path]
    if spec.get('source'):spec['source']=str(local_file(spec['source'],path.parent));inputs.append(Path(spec['source']))
    job=EditJob(output,spec,inputs,Path(__file__).resolve().parents[1],spec.get('budgetSeconds',120))
    if job.reused:return job.result
    with job:
        request=job.root/'hi3d-request.json';dump(request,spec)
        kernel=Path(__file__).with_name('hi3d-freecad-kernel.py')
        # FreeCAD CLI consumes Python filenames; bootstrap contains only serialized paths to trusted code.
        boot=job.root/'hi3d-freecad-run.py'
        boot.write_text('import runpy\nrunpy.run_path('+repr(str(kernel))+',init_globals={"SPEC":'+repr(str(request))+',"OUT":'+repr(str(job.root))+'})\n')
        job.run([freecad,boot],'cad')
        review=json.loads((job.root/'hi3d-review.json').read_text())
        if not review.get('valid') or not review.get('reopened'):raise ValueError('CAD review failed')
        return job.finish([job.root/'hi3d-project.FCStd',job.root/'hi3d-solid.step',job.root/'hi3d-review.json',request],review)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--spec',required=True);p.add_argument('--output',required=True);p.add_argument('--freecad',required=True);a=p.parse_args();print(json.dumps(execute(a.spec,a.output,a.freecad)))
