"""Create or revise a named Blender VSE timeline, save and reopen before rendering."""
import argparse,json
from pathlib import Path
import importlib
_job_api=importlib.import_module('hi3d-edit-job')
EditJob=_job_api.EditJob
local_file=_job_api.local_file
number=_job_api.number
dump=_job_api.dump
from check_media import positive_rate


def validate(spec):
    if spec.get('schemaVersion')!=1 or set(spec)-{'schemaVersion','source','width','height','fps','frames','strips','budgetSeconds','render'}:raise ValueError('invalid VSE schema')
    positive_rate(spec['fps'])
    for k in ('width','height','frames'):
        if type(spec[k]) is not int or spec[k]<=0:raise ValueError('positive dimensions/frame count required')
    ids=set()
    for s in spec['strips']:
        if set(s)-{'id','type','path','start','duration','channel','text','color','fontSize','opacity','volume','offset'}:raise ValueError('unknown strip fields')
        if s['type'] not in ('image','movie','sound','text','color') or not isinstance(s['id'],str) or not s['id'] or s['id'] in ids:raise ValueError('unique strip id and known type required')
        ids.add(s['id'])
        for k in ('start','duration','channel'):
            if type(s[k]) is not int or s[k]<1:raise ValueError('positive integer strip fields required')
        if s['start']+s['duration']-1>spec['frames']:raise ValueError('strip outside frame range')
        number(s.get('opacity',1),'opacity');number(s.get('volume',1),'volume')
        if s.get('opacity',1)>1:raise ValueError('opacity > 1')
        if type(s.get('offset',0)) is not int or s.get('offset',0)<0:raise ValueError('offset must be nonnegative frames')
    for i,a in enumerate(spec['strips']):
        for b in spec['strips'][i+1:]:
            if a['channel']==b['channel'] and max(a['start'],b['start'])<min(a['start']+a['duration'],b['start']+b['duration']):raise ValueError('overlapping strips on same channel')


def execute(spec_path,output,blender):
    path=Path(spec_path).resolve();spec=json.loads(path.read_text());validate(spec);inputs=[path]
    if spec.get('source'):spec['source']=str(local_file(spec['source'],path.parent));inputs.append(Path(spec['source']))
    for s in spec['strips']:
        if s['type'] in ('image','movie','sound'):
            s['path']=str(local_file(s['path'],path.parent));inputs.append(Path(s['path']))
    job=EditJob(output,spec,inputs,Path(__file__).resolve().parents[1],spec.get('budgetSeconds',180))
    if job.reused:return job.result
    with job:
        request=job.root/'hi3d-request.json';dump(request,spec)
        worker=Path(__file__).with_name('hi3d-vse-kernel.py')
        job.run([blender,'--background','--factory-startup','--disable-autoexec','--python-exit-code','1','--python',worker,'--',request,job.root],'vse')
        if spec.get('render',True):
            from PIL import Image
            frames=sorted((job.root/'frames').glob('*.png'))
            if len(frames)!=spec['frames']:raise ValueError('incomplete rendered sequence')
            for frame in frames:
                with Image.open(frame) as im:
                    im.load()
                    if im.size!=(spec['width'],spec['height']):raise ValueError('render dimensions changed')
        checks=json.loads((job.root/'hi3d-review.json').read_text())
        files=[job.root/'hi3d-project.blend',job.root/'hi3d-review.json',request]
        files+=list((job.root/'assets').glob('*')) if (job.root/'assets').exists() else []
        files+=list((job.root/'frames').glob('*.png')) if (job.root/'frames').exists() else []
        return job.finish(files,checks)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--spec',required=True);p.add_argument('--output',required=True);p.add_argument('--blender',required=True);a=p.parse_args();print(json.dumps(execute(a.spec,a.output,a.blender)))
