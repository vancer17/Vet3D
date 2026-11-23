"""Thin local-stage CLI for the circular bayonet recipe; no online services."""
from pathlib import Path
import argparse
import json
import shutil
import subprocess
import sys
import uuid
import time
from datetime import datetime
from frame_recipe import validate_recipe
from heightfield_io import load_heightfield
from frame_diy_runtime import prepare_paths, timed_stage


def executable(value):
    found = shutil.which(str(value))
    if found:
        return str(Path(found).resolve())
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f'Executable not found: {value}')
    return str(path)


def run(*, output, work, blender, stage='build', heightfield=None, artwork=None,
        config=None, no_render=False, render_animation=False, ffmpeg=None,
        task_id='frame-diy', attempt_id=None, resume_of=None):
    """Run selected local stages; append timing and subprocess logs to work.

    build/coupons/print/verify/media can be replayed independently. all composes them;
    it does not deploy a website or prove physical printing. Media frame/MP4
    rendering is opt-in and requires an explicit FFmpeg executable.
    """
    selected = ['build','coupons','print','verify','media'] if stage == 'all' else [stage]
    if any(s not in ('build','coupons','print','verify','media') for s in selected):
        raise ValueError('Unknown stage')
    raw = {}
    if 'build' in selected:
        if any(value is None for value in (heightfield, artwork, config)):
            raise ValueError('build requires heightfield, artwork and config')
        raw = {'heightfield':heightfield, 'artwork':artwork, 'config':config}
    paths, inputs = prepare_paths(output=output, work=work, raw_inputs=raw)
    out, workspace = paths['output'], paths['work']
    if raw:
        recipe = validate_recipe(json.loads(inputs['config'].read_text()))
        load_heightfield(inputs['heightfield'], recipe['height_key'])
    elif not (out/'measurements.json').is_file():
        raise FileNotFoundError('Existing output/measurements.json required for staged replay')
    else:
        validate_recipe(json.loads((out/'measurements.json').read_text())['configuration'])
    binary = executable(blender)
    ffmpeg_binary = executable(ffmpeg) if render_animation and ffmpeg else None
    if render_animation and not ffmpeg_binary:
        raise ValueError('Rendering/encoding animation requires explicit --ffmpeg')
    scripts = Path(__file__).resolve().parent
    if 'media' in selected and not (scripts/'animate_frame_diy.py').is_file():
        raise FileNotFoundError('The installed package lacks the DIY media stage')
    attempt_id = attempt_id or uuid.uuid4().hex
    if not attempt_id or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in attempt_id):
        raise ValueError('attempt_id accepts only letters, digits, underscore and dash')
    logs = workspace/('attempt-'+attempt_id)
    if logs.exists():
        raise FileExistsError('Keep the existing attempt; choose a new attempt_id for replay')
    started_at=datetime.now().astimezone().isoformat();clock=time.monotonic()
    out.mkdir(parents=True, exist_ok=True);workspace.mkdir(parents=True, exist_ok=True);logs.mkdir()
    records=[]
    def invoke(label, arguments, use_blender):
        command = [binary,'--background','--factory-startup','--threads','2','--python-exit-code','1','--python',str(scripts/arguments[0]),'--',*arguments[1:]] if use_blender else [sys.executable,str(scripts/arguments[0]),*arguments[1:]]
        command = list(map(str,command));log=logs/(label+'.log')
        with timed_stage(log=workspace/'timing.jsonl',task_id=task_id,attempt_id=attempt_id,stage=label,resume_of=resume_of):
            with log.open('w',encoding='utf-8') as stream:
                subprocess.run(command,check=True,stdout=stream,stderr=subprocess.STDOUT)
        records.append({'stage':label,'log':str(log),'status':'succeeded'})
    for current in selected:
        if current == 'build':
            args=['build_frame_diy.py','--output',out,'--heightfield',inputs['heightfield'],'--artwork',inputs['artwork'],'--config',inputs['config']]
            invoke('build',args+(['--no-render'] if no_render else []),True)
        elif current == 'coupons':
            invoke('coupons',['make_diy_coupons.py','--source',out/'flat-assembly.blend','--output',out/'coupons'],True)
        elif current == 'print':
            args=['prepare_diy_print.py','--source',out/'flat-assembly.blend','--coupons',out/'coupons/coupons.blend','--output',out/'manufacturing']
            invoke('print-placement',args+([] if no_render else ['--render-layout']),True)
        elif current == 'verify':
            invoke('release-exports',['export_diy_flex.py','--source',out/'flat-assembly.blend','--output',out/'verification'],True)
            invoke('assembly-stl',['verify_stl.py','--input',out/'print','--output',out/'validation/assembly-stl.json'],False)
            invoke('manufacturing',['check_diy_manufacturing.py','--source',out,'--output',out/'validation/manufacturing.json'],False)
            invoke('coupon-stl',['verify_stl.py','--input',out/'coupons','--output',out/'validation/coupon-stl.json'],False)
            invoke('coupon-pairs',['check_diy_coupons.py','--source',out/'coupons','--output',out/'validation/coupon-pairs.json'],False)
            invoke('interfaces',['check_diy_interfaces.py','--source',out,'--output',out/'validation/interfaces.json'],False)
            invoke('support',['check_diy_support.py','--source',out/'model.glb','--output',out/'validation/support.json'],True)
            invoke('fresh-models',['audit_models.py','--input',out,'--output',out/'validation/fresh-models.json'],True)
        elif current == 'media':
            args=['animate_frame_diy.py','--source',out/'scene.blend','--output',out]
            if no_render:args+=['--no-stills']
            if render_animation:args+=['--render-animation','--frames',workspace/'frames']
            invoke('media-scene',args,True)
            invoke('media-fresh-import',['check_diy_animation.py','--source',out/'motion.glb','--native',out/'assembly.blend','--output',out/'validation/animation.json'],True)
            if render_animation:
                rate=json.loads((out/'video-manifest.json').read_text())['fps']
                with timed_stage(log=workspace/'timing.jsonl',task_id=task_id,attempt_id=attempt_id,stage='encode',resume_of=resume_of):
                    with (logs/'encode.log').open('w') as stream:
                        subprocess.run([ffmpeg_binary,'-y','-framerate',str(rate),'-i',str(workspace/'frames/frame-%04d.png'),'-c:v','libx264','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(out/'demo.mp4')],check=True,stdout=subprocess.DEVNULL,stderr=stream)
                records.append({'stage':'encode','status':'succeeded','file':str(out/'demo.mp4')})
    report={'task_id':task_id,'attempt_id':attempt_id,'resume_of':resume_of,'selected_stages':selected,'results':records,'timing_log':str(workspace/'timing.jsonl'),'started_at':started_at,'ended_at':datetime.now().astimezone().isoformat(),'wall_seconds':time.monotonic()-clock,'scope':'Local selected stages only; visual/video/web/physical acceptance remains separate'}
    (logs/'result.json').write_text(json.dumps(report,indent=2));return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True);p.add_argument('--work',required=True);p.add_argument('--blender',required=True)
    p.add_argument('--stage',choices=['build','coupons','print','verify','media','all'],default='build')
    p.add_argument('--heightfield');p.add_argument('--artwork');p.add_argument('--config');p.add_argument('--no-render',action='store_true')
    p.add_argument('--render-animation',action='store_true');p.add_argument('--ffmpeg')
    p.add_argument('--task-id',default='frame-diy');p.add_argument('--attempt-id');p.add_argument('--resume-of')
    run(**vars(p.parse_args(argv)))


if __name__=='__main__':
    main()
