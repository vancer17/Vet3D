"""Frame-accurate local video edits. No shell, network inputs or implicit overwrite."""
import argparse
import json
from fractions import Fraction
from pathlib import Path
import subprocess
import importlib
_job_api=importlib.import_module('hi3d-edit-job')
EditJob=_job_api.EditJob
local_file=_job_api.local_file
number=_job_api.number
dump=_job_api.dump
from check_media import positive_rate, check_video
from media_tools import find_ffmpeg, find_ffprobe


def validate(spec):
    if spec.get('schemaVersion')!=1: raise ValueError('schemaVersion must be 1')
    allowed={'schemaVersion','width','height','fps','clips','crf','budgetSeconds','watermark'}
    if set(spec)-allowed: raise ValueError('unknown video fields')
    for key in ('width','height'):
        if type(spec.get(key)) is not int or not 2<=spec[key]<=8192 or spec[key]%2: raise ValueError('even dimensions 2..8192 required')
    rate=positive_rate(spec['fps'])
    if rate>240: raise ValueError('fps exceeds 240')
    if not isinstance(spec.get('clips'),list) or not 1<=len(spec['clips'])<=100: raise ValueError('1..100 clips required')
    frames=0;previous_count=0
    for index,c in enumerate(spec['clips']):
        if set(c)-{'path','start','end','speed','crop','transitionFrames'}: raise ValueError('unknown clip fields')
        number(c['start'],'start');number(c['end'],'end',c['start'],True)
        number(c.get('speed',1),'speed',0,True)
        if not .125<=c.get('speed',1)<=8: raise ValueError('speed range .125..8')
        duration=Fraction(str(c['end']-c['start']))/Fraction(str(c.get('speed',1)))
        count=round(duration*rate)
        if count<1: raise ValueError('clip shorter than one output frame')
        transition=c.get('transitionFrames',0)
        if type(transition) is not int or transition<0 or transition>=count or (index==0 and transition) or (index and transition>=previous_count):raise ValueError('transition must fit both adjacent clips')
        crop=c.get('crop')
        if crop:
            if set(crop)!={'x','y','width','height'} or any(type(v) is not int for v in crop.values()) or min(crop['x'],crop['y'])<0 or min(crop['width'],crop['height'])<2:raise ValueError('invalid pixel crop')
        frames+=count-transition;previous_count=count
    if type(spec.get('crf',19)) is not int or not 0<=spec.get('crf',19)<=51: raise ValueError('invalid crf')
    if spec.get('watermark'):
        w=spec['watermark']
        if set(w)!={'path','x','y'} or type(w['x']) is not int or type(w['y']) is not int or min(w['x'],w['y'])<0:raise ValueError('watermark requires path and nonnegative pixel coordinates')
    return rate,frames


def command(spec,paths,ffmpeg,output,watermark=None):
    rate,total=validate(spec)
    argv=[ffmpeg,'-nostdin','-v','error','-n'];graph=[];counts=[]
    for i,(c,p) in enumerate(zip(spec['clips'],paths)):
        argv+=['-protocol_whitelist','file,pipe','-i',str(p)]
        count=round(Fraction(str(c['end']-c['start']))/Fraction(str(c.get('speed',1)))*rate);counts.append(count)
        crop=c.get('crop');cropfilter=f"crop={crop['width']}:{crop['height']}:{crop['x']}:{crop['y']}," if crop else ''
        graph.append(f"[{i}:v:0]trim=start={c['start']}:end={c['end']},setpts=(PTS-STARTPTS)/{c.get('speed',1)},{cropfilter}fps={rate},scale={spec['width']}:{spec['height']}:force_original_aspect_ratio=decrease,pad={spec['width']}:{spec['height']}:(ow-iw)/2:(oh-ih)/2,setsar=1,tpad=stop_mode=clone:stop_duration=1,trim=end_frame={count},settb=AVTB,setpts=N/({rate}*TB),fps={rate},settb=AVTB,format=yuv420p[v{i}]")
    current='v0';length=counts[0]
    for i in range(1,len(paths)):
        t=spec['clips'][i].get('transitionFrames',0);label=f'joined{i}'
        if t:graph.append(f'[{current}][v{i}]xfade=transition=fade:duration={float(t/rate):.9f}:offset={float((length-t)/rate):.9f}[{label}]')
        else:graph.append(f'[{current}][v{i}]concat=n=2:v=1:a=0[{label}]')
        graph.append(f'[{label}]fps={rate},settb=AVTB[normalized{i}]');current=f'normalized{i}';length+=counts[i]-t
    graph.append(f'[{current}]tpad=stop_mode=clone:stop_duration=1,trim=end_frame={total}[timed]');current='timed'
    if watermark:
        argv+=['-loop','1','-protocol_whitelist','file,pipe','-i',str(watermark)]
        w=spec['watermark'];graph.append(f'[{current}][{len(paths)}:v]overlay={w["x"]}:{w["y"]}:shortest=1[marked]');current='marked'
    return argv+['-filter_complex',';'.join(graph),'-map',f'[{current}]','-an','-r',str(rate),'-fps_mode','cfr','-frames:v',str(total),'-c:v','libx264','-crf',str(spec.get('crf',19)),'-pix_fmt','yuv420p','-movflags','+faststart',str(output)]


def execute(spec_path,output,ffmpeg=None,ffprobe=None):
    path=Path(spec_path).resolve();spec=json.loads(path.read_text());rate,frames=validate(spec)
    paths=[local_file(c['path'],path.parent) for c in spec['clips']]
    watermark=local_file(spec['watermark']['path'],path.parent) if spec.get('watermark') else None
    ffmpeg,ffprobe=find_ffmpeg(ffmpeg),find_ffprobe(ffprobe)
    if not ffmpeg or not ffprobe: raise ValueError('ffmpeg and ffprobe required')
    for c,p in zip(spec['clips'],paths):
        info=subprocess.run([ffprobe,'-v','error','-protocol_whitelist','file,pipe','-show_streams','-show_format','-of','json',str(p)],capture_output=True,text=True,check=True,timeout=15)
        data=json.loads(info.stdout);streams=[s for s in data['streams'] if s['codec_type']=='video']
        if not streams: raise ValueError('video stream required')
        if streams[0].get('color_transfer') in ('smpte2084','arib-std-b67'): raise ValueError('HDR needs explicit tone mapping; not silently converted')
        if c['end']>float(data['format']['duration'])+.001: raise ValueError('clip exceeds source duration')
        crop=c.get('crop')
        if crop and (crop['x']+crop['width']>streams[0]['width'] or crop['y']+crop['height']>streams[0]['height']):raise ValueError('crop outside source')
    job=EditJob(output,spec,[path,*paths,*([watermark] if watermark else [])],Path(__file__).resolve().parents[1],spec.get('budgetSeconds',120))
    if job.reused:return job.result
    with job:
        video=job.root/'hi3d-video.mp4'
        job.run(command(spec,paths,ffmpeg,video,watermark),'encode')
        expected=dict(width=spec['width'],height=spec['height'],fps=str(rate),frames=frames,duration_seconds=float(frames/rate))
        actual,errors=check_video(video,expected,ffmpeg,ffprobe,job.budget)
        if errors:raise ValueError(';'.join(errors))
        dump(job.root/'hi3d-edit.json',spec)
        return job.finish([video,job.root/'hi3d-edit.json'],{'video':actual,'audio':'not retained; use explicit audio mix'})


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--spec',required=True);p.add_argument('--output',required=True);p.add_argument('--ffmpeg');p.add_argument('--ffprobe')
    a=p.parse_args();print(json.dumps(execute(a.spec,a.output,a.ffmpeg,a.ffprobe),ensure_ascii=False))
if __name__=='__main__':main()
