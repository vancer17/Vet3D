import bpy,json,sys,shutil
from pathlib import Path
from fractions import Fraction
specpath,out=sys.argv[sys.argv.index('--')+1:];out=Path(out);spec=json.loads(Path(specpath).read_text())
if spec.get('source'):bpy.ops.wm.open_mainfile(filepath=spec['source'],load_ui=False,use_scripts=False)
scene=bpy.context.scene
scene.render.resolution_x=spec['width'];scene.render.resolution_y=spec['height'];scene.render.resolution_percentage=100
fps=Fraction(str(spec['fps']));scene.render.fps=round(float(fps));scene.render.fps_base=scene.render.fps/float(fps)
scene.frame_start=1;scene.frame_end=spec['frames'];scene.render.image_settings.file_format='PNG'
scene.view_settings.view_transform='Standard';scene.render.film_transparent=False
editor=scene.sequence_editor_create();strips=editor.strips if hasattr(editor,'strips') else editor.sequences
assets=out/'assets';assets.mkdir()
for item in spec['strips']:
    old=strips.get(item['id'])
    if old:strips.remove(old)
    kind=item['type'];kw=dict(name=item['id'],channel=item['channel'],frame_start=item['start'])
    if kind in ('image','movie','sound'):
        src=Path(item['path']);dst=assets/('hi3d-'+str(len(list(assets.iterdir())))+src.suffix);shutil.copyfile(src,dst)
        s=getattr(strips,'new_'+kind)(filepath=str(dst),**kw)
        if kind!='image' and s.frame_duration<item.get('offset',0)+item['duration']:raise ValueError('strip duration exceeds source')
        s.frame_offset_start=item.get('offset',0)
        s.frame_final_start=item['start'];s.frame_final_duration=item['duration']
        if kind=='sound':s.volume=item.get('volume',1)
    else:
        extent={'length':item['duration']} if 'length' in strips.bl_rna.functions['new_effect'].parameters else {'frame_end':item['start']+item['duration']}
        s=strips.new_effect(type='TEXT' if kind=='text' else 'COLOR',**extent,**kw)
        if kind=='text':s.text=item.get('text','');s.font_size=item.get('fontSize',48)
        else:s.color=item.get('color',[.1,.2,.4])
    if hasattr(s,'blend_alpha'):s.blend_alpha=item.get('opacity',1)
# Bundle all remaining external strips too when revising an existing project.
for s in strips:
    if s.type=='MOVIE':src=Path(bpy.path.abspath(s.filepath))
    elif s.type=='SOUND':src=Path(bpy.path.abspath(s.sound.filepath))
    elif s.type=='IMAGE':
        for el in s.elements:
            src=Path(bpy.path.abspath(s.directory))/el.filename
            if src.parent.resolve()!=assets.resolve():
                dst=assets/('hi3d-existing-'+str(len(list(assets.iterdir())))+src.suffix);shutil.copyfile(src,dst);el.filename=dst.name
        s.directory='//assets/';continue
    else:continue
    if src.parent.resolve()!=assets.resolve():
        dst=assets/('hi3d-existing-'+str(len(list(assets.iterdir())))+src.suffix);shutil.copyfile(src,dst)
    else:dst=src
    if s.type=='MOVIE':s.filepath='//assets/'+dst.name
    else:s.sound.filepath='//assets/'+dst.name
for i,a in enumerate(strips):
    if a.frame_final_start<1 or a.frame_final_end>scene.frame_end+1:raise ValueError('existing strip outside output range')
    for b in list(strips)[i+1:]:
        if a.channel==b.channel and max(a.frame_final_start,b.frame_final_start)<min(a.frame_final_end,b.frame_final_end):raise ValueError('existing strip channel overlap')
scene.render.use_sequencer=True
bpy.ops.wm.save_as_mainfile(filepath=str(out/'hi3d-project.blend'),check_existing=False)
bpy.ops.wm.open_mainfile(filepath=str(out/'hi3d-project.blend'),load_ui=False,use_scripts=False)
scene=bpy.context.scene;editor=scene.sequence_editor;strips=editor.strips if hasattr(editor,'strips') else editor.sequences
for item in spec['strips']:
    s=strips.get(item['id'])
    if not s or s.frame_final_start!=item['start'] or s.frame_final_duration!=item['duration']:raise ValueError('reopened strip mismatch')
    if item['type']=='text' and s.text!=item.get('text',''):raise ValueError('text lost on reopen')
    if item['type']=='sound' and abs(s.volume-item.get('volume',1))>1e-6:raise ValueError('volume changed')
(out/'hi3d-review.json').write_text(json.dumps({'reopened':True,'strips':[s.name for s in strips],'frames':scene.frame_end,'blender':bpy.app.version_string}))
if spec.get('render',True):
    (out/'frames').mkdir();scene.render.filepath=str(out/'frames'/'hi3d-frame-');bpy.ops.render.render(animation=True)
