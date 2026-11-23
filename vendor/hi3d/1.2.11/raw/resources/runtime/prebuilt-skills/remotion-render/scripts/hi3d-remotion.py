"""Render a parameterized local Remotion composition with explicit Node runtime."""
import argparse
import json
from pathlib import Path
import shutil
import importlib
_job_api=importlib.import_module('hi3d-edit-job')
EditJob=_job_api.EditJob
local_file=_job_api.local_file
number=_job_api.number
dump=_job_api.dump
from media_tools import find_ffmpeg,find_ffprobe
from check_media import check_video


def validate(spec):
    if spec.get('schemaVersion')!=1 or set(spec)-{'schemaVersion','width','height','fps','frames','background','layers','budgetSeconds'}:raise ValueError('invalid composition schema')
    for k in ('width','height','fps','frames'):
        if type(spec.get(k)) is not int or spec[k]<=0:raise ValueError('positive integer '+k+' required')
    if spec['width']%2 or spec['height']%2 or spec['width']>8192 or spec['height']>8192 or spec['fps']>120:raise ValueError('invalid render dimensions/fps')
    if not isinstance(spec.get('layers'),list):raise ValueError('layers required')
    ids=set()
    for layer in spec['layers']:
        if set(layer)-{'id','type','text','path','x','y','width','height','color','fontSize','start','duration','fromX','toX','fadeFrames'}:raise ValueError('unknown layer fields')
        if layer['id'] in ids or layer['type'] not in ('text','rect','image','audio'):raise ValueError('duplicate id or unsupported layer')
        ids.add(layer['id'])
        for k in ('start','duration','fadeFrames'):
            if type(layer.get(k,0)) is not int or layer.get(k,0)<0:raise ValueError('integer frame values required')
        if layer.get('duration',spec['frames'])<=0 or layer.get('start',0)+layer.get('duration',spec['frames'])>spec['frames']:raise ValueError('layer outside timeline')
        for k in ('x','y','fromX','toX'):
            number(layer.get(k,0),k,-100000)
        for k in ('width','height','fontSize'):
            if k in layer:number(layer[k],k,0,True)
        if layer['type']=='text' and not isinstance(layer.get('text'),str):raise ValueError('text required')
    return spec


def execute(spec_path,output,runtime,node='node',browser=None,ffmpeg=None,ffprobe=None):
    path=Path(spec_path).resolve();spec=validate(json.loads(path.read_text()));runtime=Path(runtime).resolve(strict=True)
    package=runtime/'package.json';lock=runtime/'package-lock.json'
    if not package.is_file():raise ValueError('explicit installed Node runtime package.json required')
    assets=[local_file(l['path'],path.parent) for l in spec['layers'] if l['type'] in ('image','audio')]
    inputs=[path,package,*([lock] if lock.exists() else []),*assets]
    job=EditJob(output,spec,inputs,Path(__file__).resolve().parents[1],spec.get('budgetSeconds',180))
    if job.reused:return job.result
    with job:
        project_spec=json.loads(json.dumps(spec))
        public=job.root/'public';public.mkdir()
        for layer in spec['layers']:
            if layer['type'] in ('image','audio'):
                src=local_file(layer['path'],path.parent);target='hi3d-'+str(len(list(public.iterdir())))+src.suffix
                shutil.copyfile(src,public/target);layer['path']=target
                for saved in project_spec['layers']:
                    if saved['id']==layer['id']:saved['path']='public/'+target
        props=job.root/'hi3d-props.json';dump(props,spec)
        project=job.root/'hi3d-project.json';dump(project,project_spec)
        worker=Path(__file__).with_name('hi3d-remotion.mjs')
        argv=[node,worker,str(runtime),str(props),str(job.root)]
        if browser:argv.append(browser)
        job.run(argv,'render')
        out=job.root/'hi3d-video.mp4';ffmpeg,ffprobe=find_ffmpeg(ffmpeg),find_ffprobe(ffprobe)
        actual,errors=check_video(out,dict(width=spec['width'],height=spec['height'],frames=spec['frames'],fps=spec['fps'],duration_seconds=spec['frames']/spec['fps']),ffmpeg,ffprobe,job.budget)
        if errors:raise ValueError(';'.join(errors))
        return job.finish([out,props,project,*public.iterdir()],{'video':actual,'project':'props plus packaged template; no remote resources required'})
def execute_queue(queue_path,output,runtime,node='node',browser=None,ffmpeg=None,ffprobe=None):
    from path_safety import validate_write_roots
    path=Path(queue_path).resolve();data=json.loads(path.read_text())
    if set(data)!={'schemaVersion','specs'} or data['schemaVersion']!=1 or not isinstance(data['specs'],list) or not data['specs']:raise ValueError('queue requires schemaVersion 1 and nonempty specs')
    specs=[local_file(p,path.parent) for p in data['specs']]
    root=validate_write_roots({'output':output},package_root=Path(__file__).resolve().parents[1],protected_inputs=[path,*specs])['output']
    if root.exists() and not (root/'hi3d-queue.json').is_file():raise ValueError('not an existing queue output')
    root.mkdir(parents=True,exist_ok=True)
    report={'schemaVersion':1,'status':'running','items':[]};dump(root/'hi3d-queue.json',report)
    try:
        for i,spec in enumerate(specs):
            result=execute(spec,root/f'job-{i:03}',runtime,node,browser,ffmpeg,ffprobe)
            report['items'].append({'index':i,'status':result['status'],'path':f'job-{i:03}/hi3d-result.json'})
            dump(root/'hi3d-queue.json',report)
    except BaseException as exc:
        report.update(status='interrupted' if isinstance(exc,(KeyboardInterrupt,SystemExit)) else 'failed',error=type(exc).__name__)
        dump(root/'hi3d-queue.json',report);raise
    report['status']='completed';dump(root/'hi3d-queue.json',report);return report

if __name__=='__main__':
    p=argparse.ArgumentParser();group=p.add_mutually_exclusive_group(required=True);group.add_argument('--spec');group.add_argument('--queue')
    p.add_argument('--output',required=True);p.add_argument('--runtime',required=True);p.add_argument('--node',default='node');p.add_argument('--browser');p.add_argument('--ffmpeg');p.add_argument('--ffprobe')
    a=vars(p.parse_args());queue=a.pop('queue');spec=a.pop('spec')
    print(json.dumps(execute_queue(queue,**a) if queue else execute(spec,**a),ensure_ascii=False))
