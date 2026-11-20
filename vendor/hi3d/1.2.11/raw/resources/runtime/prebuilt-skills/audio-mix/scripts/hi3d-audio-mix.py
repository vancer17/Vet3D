"""Explicit soundtrack mix with offsets, trim, gain, fades and optional subtitles."""
import argparse
import json
from pathlib import Path
import subprocess
import importlib
_job_api=importlib.import_module('hi3d-edit-job')
EditJob=_job_api.EditJob
local_file=_job_api.local_file
number=_job_api.number
dump=_job_api.dump
from media_tools import find_ffmpeg,find_ffprobe


def validate(spec):
    if spec.get('schemaVersion')!=1 or set(spec)-{'schemaVersion','tracks','duration','video','subtitles','fontDir','loudness','budgetSeconds'}:raise ValueError('invalid mix schema')
    number(spec['duration'],'duration',0,True)
    if not isinstance(spec.get('tracks'),list) or not 1<=len(spec['tracks'])<=32:raise ValueError('1..32 tracks required')
    for t in spec['tracks']:
        if set(t)-{'path','start','end','offset','gainDb','fadeIn','fadeOut'}:raise ValueError('unknown track fields')
        number(t.get('start',0),'start');number(t['end'],'end',t.get('start',0),True)
        number(t.get('offset',0),'offset');number(t.get('gainDb',0),'gainDb',-60)
        duration=t['end']-t.get('start',0)
        if t.get('gainDb',0)>24 or t.get('offset',0)>=spec['duration']:raise ValueError('track outside mix')
        for k in ('fadeIn','fadeOut'):
            number(t.get(k,0),k)
            if t.get(k,0)>duration:raise ValueError('fade longer than track')
    if spec.get('subtitles') and not spec.get('video'):raise ValueError('subtitles require video')
    number(spec.get('loudness',-16),'loudness',-70)
    if spec.get('loudness',-16)>-5:raise ValueError('loudness > -5 LUFS')


def escape_filter_path(path):
    return str(path).replace('\\','\\\\').replace(':','\\:').replace("'", "'\\''")


def execute(spec_path,output,ffmpeg=None,ffprobe=None):
    path=Path(spec_path).resolve();spec=json.loads(path.read_text());validate(spec)
    tracks=[local_file(t['path'],path.parent) for t in spec['tracks']]
    video=local_file(spec['video'],path.parent) if spec.get('video') else None
    subs=local_file(spec['subtitles'],path.parent) if spec.get('subtitles') else None
    fonts=(path.parent/spec['fontDir']).resolve(strict=True) if spec.get('fontDir') else None
    if fonts and not fonts.is_dir():raise ValueError('fontDir must be directory')
    fontfiles=list(fonts.glob('*')) if fonts else []
    fontfiles=[p for p in fontfiles if p.is_file()]
    inputs=[path,*tracks,*([video] if video else []),*([subs] if subs else []),*fontfiles]
    ffmpeg,ffprobe=find_ffmpeg(ffmpeg),find_ffprobe(ffprobe)
    if not ffmpeg or not ffprobe:raise ValueError('ffmpeg and ffprobe required')
    for t,src in zip(spec['tracks'],tracks):
        raw=subprocess.run([ffprobe,'-v','error','-protocol_whitelist','file,pipe','-show_streams','-show_format','-of','json',str(src)],check=True,capture_output=True,text=True,timeout=15)
        meta=json.loads(raw.stdout)
        if not any(s['codec_type']=='audio' for s in meta['streams']):raise ValueError('track has no audio')
        if t['end']>float(meta['format']['duration'])+.02:raise ValueError('audio trim exceeds source')
    if video:
        raw=subprocess.run([ffprobe,'-v','error','-show_streams','-of','json',str(video)],check=True,capture_output=True,text=True,timeout=15)
        v=[s for s in json.loads(raw.stdout)['streams'] if s['codec_type']=='video']
        if not v or float(v[0].get('duration',0))+.05<spec['duration']:raise ValueError('video shorter than requested mix')
    job=EditJob(output,spec,inputs,Path(__file__).resolve().parents[1],spec.get('budgetSeconds',120))
    if job.reused:return job.result
    with job:
        out=job.root/('hi3d-mixed.mp4' if video else 'hi3d-mixed.wav')
        argv=[ffmpeg,'-nostdin','-v','error','-n'];graph=[]
        for src in tracks+([video] if video else []):argv+=['-protocol_whitelist','file,pipe','-i',str(src)]
        for i,t in enumerate(spec['tracks']):
            duration=t['end']-t.get('start',0)
            f=f"[{i}:a:0]atrim=start={t.get('start',0)}:end={t['end']},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,volume={t.get('gainDb',0)}dB"
            if t.get('fadeIn',0):f+=f",afade=t=in:st=0:d={t['fadeIn']}"
            if t.get('fadeOut',0):f+=f",afade=t=out:st={duration-t['fadeOut']}:d={t['fadeOut']}"
            delay=round(t.get('offset',0)*1000);f+=f',adelay={delay}:all=1[a{i}]';graph.append(f)
        graph.append(''.join(f'[a{i}]' for i in range(len(tracks)))+f"amix=inputs={len(tracks)}:normalize=0,apad,atrim=duration={spec['duration']},loudnorm=I={spec.get('loudness',-16)}:TP=-1.5:LRA=11,aresample=48000[a]")
        argv+=['-filter_complex',';'.join(graph),'-map','[a]']
        if video:
            argv+=['-map',f'{len(tracks)}:v:0','-c:v','libx264','-pix_fmt','yuv420p']
            if subs:
                filt=f"subtitles=filename='{escape_filter_path(subs)}'"
                if fonts:filt+=f":fontsdir='{escape_filter_path(fonts)}'"
                argv+=['-vf',filt]
            argv+=['-c:a','aac','-movflags','+faststart']
        else:argv+=['-c:a','pcm_s16le']
        argv+=['-t',str(spec['duration']),str(out)];job.run(argv,'mix')
        job.run([ffmpeg,'-nostdin','-v','error','-xerror','-i',out,'-map','0','-f','null','-'],'decode')
        raw=subprocess.run([ffprobe,'-v','error','-show_streams','-show_format','-of','json',str(out)],check=True,capture_output=True,text=True,timeout=15)
        meta=json.loads(raw.stdout)
        if abs(float(meta['format']['duration'])-spec['duration'])>.1:raise ValueError('duration mismatch')
        streams=meta['streams'];audio=[s for s in streams if s['codec_type']=='audio']
        if len(audio)!=1 or audio[0]['sample_rate']!='48000':raise ValueError('audio output mismatch')
        if video:
            v=[s for s in streams if s['codec_type']=='video']
            if not v or abs(float(v[0].get('duration',0))-float(audio[0].get('duration',0)))>.1:raise ValueError('audio/video duration mismatch')
        dump(job.root/'hi3d-mix.json',spec)
        return job.finish([out,job.root/'hi3d-mix.json'],{'fullDecode':True,'duration':float(meta['format']['duration']),'loudness':'single-pass target; not measured compliance','subtitles':bool(subs)})
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--spec',required=True);p.add_argument('--output',required=True);p.add_argument('--ffmpeg');p.add_argument('--ffprobe');a=p.parse_args();print(json.dumps(execute(a.spec,a.output,a.ffmpeg,a.ffprobe),ensure_ascii=False))
