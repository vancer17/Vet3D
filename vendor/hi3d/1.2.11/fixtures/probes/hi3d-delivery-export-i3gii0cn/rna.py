import sys, json, bpy
sys.dont_write_bytecode=True
rna=bpy.ops.export_scene.gltf.get_rna_type()
names=['export_animations','export_skins','export_morph','export_extras','export_animation_mode','export_frame_range','export_force_sampling','export_yup','export_apply','export_all_influences','export_influence_nb']
result={}
for name in names:
    if name in rna.properties:
        p=rna.properties[name]
        result[name]={'type':p.type,'default':str(p.default)}
        if p.type=='ENUM': result[name]['items']=[x.identifier for x in p.enum_items]
print('EXPORT_RNA',json.dumps(result))
