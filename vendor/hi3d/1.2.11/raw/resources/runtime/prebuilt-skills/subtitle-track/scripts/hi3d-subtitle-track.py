"""Generate timed UTF-8 SRT and ASS from explicit cues; no speech recognition."""
import argparse
import json
from pathlib import Path
import importlib
_job_api=importlib.import_module('hi3d-edit-job')
EditJob=_job_api.EditJob
number=_job_api.number


def validate(spec):
    if set(spec)-{'schemaVersion','cues','font','fontSize','width','height','margin','maxLineChars'} or spec.get('schemaVersion')!=1:raise ValueError('invalid subtitle schema')
    for key,default in [('fontSize',36),('width',1280),('height',720),('margin',40),('maxLineChars',24)]:
        if type(spec.get(key,default)) is not int or spec.get(key,default)<=0:raise ValueError('positive integer '+key+' required')
    font=spec.get('font','Arial')
    if not isinstance(font,str) or any(c in font for c in ',\r\n'):raise ValueError('invalid font name')
    if not isinstance(spec.get('cues'),list) or not spec['cues']:raise ValueError('cues required')
    end=0
    for cue in spec['cues']:
        if set(cue)!={'start','end','text'}:raise ValueError('cue requires start/end/text')
        number(cue['start'],'start',end);number(cue['end'],'end',cue['start'],True)
        if not isinstance(cue['text'],str) or not cue['text'].strip() or any(c in cue['text'] for c in '{}\\\x00'):raise ValueError('plain text required, no ASS control codes')
        if round(cue['end']*100)<=round(cue['start']*100):raise ValueError('cue shorter than ASS precision')
        end=cue['end']


def timestamp(t,ass=False):
    scale=100 if ass else 1000;n=round(t*scale);s,f=divmod(n,scale);m,s=divmod(s,60);h,m=divmod(m,60)
    return f'{h}:{m:02}:{s:02}.{f:02}' if ass else f'{h:02}:{m:02}:{s:02},{f:03}'


def render(spec):
    validate(spec);srt=[];events=[]
    for i,c in enumerate(spec['cues'],1):
        text=c['text'].replace('\r','');limit=spec.get('maxLineChars',24)
        lines=[line[j:j+limit] for line in text.split('\n') for j in range(0,len(line),limit)]
        wrapped='\n'.join(lines);ass_text='\\N'.join(lines)
        srt.append(f"{i}\n{timestamp(c['start'])} --> {timestamp(c['end'])}\n{wrapped}\n")
        events.append(f"Dialogue: 0,{timestamp(c['start'],True)},{timestamp(c['end'],True)},Default,,0,0,0,,{ass_text}")
    ass=f"""[Script Info]
ScriptType: v4.00+
PlayResX: {spec.get('width',1280)}
PlayResY: {spec.get('height',720)}
WrapStyle: 2
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{spec.get('font','Arial')},{spec.get('fontSize',36)},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,0,2,{spec.get('margin',40)},{spec.get('margin',40)},{spec.get('margin',40)},1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""+'\n'.join(events)+'\n'
    return '\n'.join(srt),ass


def execute(spec_path,output):
    path=Path(spec_path).resolve();spec=json.loads(path.read_text());srt,ass=render(spec)
    job=EditJob(output,spec,[path],Path(__file__).resolve().parents[1])
    if job.reused:return job.result
    with job:
        files=[job.root/'hi3d-subtitles.srt',job.root/'hi3d-subtitles.ass']
        for p,content in zip(files,[srt,ass]):p.write_text(content,encoding='utf-8')
        return job.finish(files,{'cues':len(spec['cues']),'font':'requested, availability must be checked by renderer','speechRecognition':False})
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--spec',required=True);p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(execute(a.spec,a.output),ensure_ascii=False))
