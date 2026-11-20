"""Create editable Grease Pencil drawings from explicit planar strokes and keyframes."""
import argparse,json
from pathlib import Path
import importlib
_job_api=importlib.import_module('hi3d-edit-job')
EditJob=_job_api.EditJob
number=_job_api.number
dump=_job_api.dump
local_file=_job_api.local_file

def validate(spec):
    if spec.get('schemaVersion')!=1 or set(spec)-{'schemaVersion','source','width','height','fps','frames','layers','budgetSeconds','render','viewWidth'}:raise ValueError('invalid stroke schema')
    for k in ('width','height','fps','frames'):
        if type(spec[k]) is not int or spec[k]<=0:raise ValueError('positive integer '+k)
    number(spec.get('viewWidth',10),'viewWidth',0,True)
    ids=set()
    if not spec.get('layers'):raise ValueError('layers required')
    for layer in spec['layers']:
        if set(layer)-{'id','color','drawings','keys'} or not isinstance(layer.get('id'),str) or not layer['id'] or layer['id'] in ids:raise ValueError('unique layers required')
        ids.add(layer['id']);frames=set()
        color=layer.get('color',[.1,.3,.9,1])
        if len(color)!=4 or any(type(c) not in (int,float) or not 0<=c<=1 for c in color):raise ValueError('RGBA 0..1 required')
        for drawing in layer['drawings']:
            f=drawing['frame']
            if type(f) is not int or not 1<=f<=spec['frames'] or f in frames:raise ValueError('unique drawing frames required')
            frames.add(f)
            for stroke in drawing['strokes']:
                if set(stroke)-{'points','radius','cyclic'} or len(stroke['points'])<2:raise ValueError('stroke needs >=2 points')
                number(stroke.get('radius',.03),'radius',0,True)
                for point in stroke['points']:
                    if len(point)!=2:raise ValueError('XY points required')
                    for n in point:number(n,'coordinate',-1e6)
        for key in layer.get('keys',[]):
            if set(key)-{'frame','x','y','rotation','scale'} or type(key['frame']) is not int or not 1<=key['frame']<=spec['frames']:raise ValueError('invalid transform key')
            for k in ('x','y','rotation'):number(key.get(k,0),k,-1e6)
            number(key.get('scale',1),'scale',0,True)

def execute(spec_path,output,blender):
    path=Path(spec_path).resolve();spec=json.loads(path.read_text());validate(spec);inputs=[path]
    if spec.get('source'):spec['source']=str(local_file(spec['source'],path.parent));inputs.append(Path(spec['source']))
    job=EditJob(output,spec,inputs,Path(__file__).resolve().parents[1],spec.get('budgetSeconds',180))
    if job.reused:return job.result
    with job:
        request=job.root/'hi3d-request.json';dump(request,spec)
        job.run([blender,'--background','--factory-startup','--disable-autoexec','--python-exit-code','1','--python',Path(__file__).with_name('hi3d-stroke-kernel.py'),'--',request,job.root],'draw')
        if spec.get('render',True):
            from PIL import Image
            frames=sorted((job.root/'frames').glob('*.png'))
            if len(frames)!=spec['frames']:raise ValueError('incomplete rendered sequence')
            for frame in frames:
                with Image.open(frame) as im:
                    im.load()
                    if im.size!=(spec['width'],spec['height']):raise ValueError('render dimensions changed')
        checks=json.loads((job.root/'hi3d-review.json').read_text())
        return job.finish([request,job.root/'hi3d-project.blend',job.root/'hi3d-review.json',*list((job.root/'frames').glob('*.png'))],checks)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--spec',required=True);p.add_argument('--output',required=True);p.add_argument('--blender',required=True);a=p.parse_args();print(json.dumps(execute(a.spec,a.output,a.blender)))
