import bpy,json,sys,math
from pathlib import Path
specpath,out=sys.argv[sys.argv.index('--')+1:];out=Path(out);spec=json.loads(Path(specpath).read_text())
if spec.get('source'):bpy.ops.wm.open_mainfile(filepath=spec['source'],load_ui=False,use_scripts=False)
else:bpy.ops.wm.read_factory_settings(use_empty=True)
if bpy.app.version<(4,3,0):raise RuntimeError('Grease Pencil 4.3+ required')
scene=bpy.context.scene;scene.frame_start=1;scene.frame_end=spec['frames'];scene.render.fps=spec['fps']
scene.render.resolution_x=spec['width'];scene.render.resolution_y=spec['height'];scene.render.resolution_percentage=100
scene.render.engine='BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in [i.identifier for i in scene.render.bl_rna.properties['engine'].enum_items] else 'CYCLES'
scene.render.film_transparent=True;scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='Standard'
for layer in spec['layers']:
    old=bpy.data.objects.get(layer['id'])
    if old:
        if old.type!='GREASEPENCIL':raise ValueError('target id belongs to another object type')
        bpy.data.objects.remove(old,do_unlink=True)
    bpy.ops.object.grease_pencil_add(type='EMPTY',location=(0,0,0));obj=bpy.context.object;obj.name=layer['id'];gp=obj.data
    for existing in list(gp.layers):gp.layers.remove(existing)
    gp.materials.clear();mat=bpy.data.materials.new('hi3d-'+layer['id']);bpy.data.materials.create_gpencil_data(mat);mat.grease_pencil.color=layer.get('color',[.1,.3,.9,1]);gp.materials.append(mat)
    gl=gp.layers.new(layer['id'],set_active=True)
    if hasattr(gl,'use_lights'):gl.use_lights=False
    for drawing in layer['drawings']:
        dr=gl.frames.new(drawing['frame']).drawing;dr.add_strokes([len(s['points']) for s in drawing['strokes']])
        for s,definition in zip(dr.strokes,drawing['strokes']):
            s.cyclic=definition.get('cyclic',False)
            for point,xy in zip(s.points,definition['points']):point.position=(xy[0],xy[1],0);point.radius=definition.get('radius',.03);point.opacity=1
    for key in layer.get('keys',[]):
        obj.location=(key.get('x',0),key.get('y',0),0);obj.rotation_euler=(0,0,math.radians(key.get('rotation',0)));obj.scale=(key.get('scale',1),)*3
        for field in ('location','rotation_euler','scale'):obj.keyframe_insert(data_path=field,frame=key['frame'])
cam=bpy.data.objects.get('hi3d-camera')
if cam is None:
    data=bpy.data.cameras.new('hi3d-camera');cam=bpy.data.objects.new('hi3d-camera',data);scene.collection.objects.link(cam)
cam.location=(0,0,10);cam.rotation_euler=(0,0,0);cam.data.type='ORTHO';cam.data.ortho_scale=spec.get('viewWidth',10);scene.camera=cam
scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'hi3d-project.blend'),check_existing=False)
bpy.ops.wm.open_mainfile(filepath=str(out/'hi3d-project.blend'),load_ui=False,use_scripts=False)
for layer in spec['layers']:
    obj=bpy.data.objects[layer['id']]
    if obj.type!='GREASEPENCIL' or len(obj.data.layers[0].frames)!=len(layer['drawings']):raise ValueError('drawing lost on reopen')
    for definition in layer['drawings']:
        frame=next(f for f in obj.data.layers[0].frames if f.frame_number==definition['frame'])
        if len(frame.drawing.strokes)!=len(definition['strokes']):raise ValueError('stroke count changed')
        for stroke,expected in zip(frame.drawing.strokes,definition['strokes']):
            if len(stroke.points)!=len(expected['points']):raise ValueError('point count changed')
            for point,xy in zip(stroke.points,expected['points']):
                if abs(point.position.x-xy[0])>1e-5 or abs(point.position.y-xy[1])>1e-5:raise ValueError('point position changed')
    for key in layer.get('keys',[]):
        bpy.context.scene.frame_set(key['frame'])
        if abs(obj.location.x-key.get('x',0))>1e-5 or abs(obj.location.y-key.get('y',0))>1e-5:raise ValueError('keyframe changed')
(out/'hi3d-review.json').write_text(json.dumps({'reopened':True,'layers':len(spec['layers']),'blender':bpy.app.version_string}))
(out/'frames').mkdir()
if spec.get('render',True):
    bpy.context.scene.render.filepath=str(out/'frames'/'hi3d-frame-');bpy.ops.render.render(animation=True)
