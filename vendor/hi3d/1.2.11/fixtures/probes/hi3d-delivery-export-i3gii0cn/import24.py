import sys,json,bpy
from pathlib import Path
sys.dont_write_bytecode=True
root=Path(__file__).parent
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene
assert scene.render.fps/scene.render.fps_base==24.0
bpy.ops.import_scene.gltf(filepath=str(root/'animated.glb'))
result={'fps':scene.render.fps/scene.render.fps_base,'actions':[{'name':a.name,'range':list(a.frame_range)} for a in bpy.data.actions]}
(root/'import24-result.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print('IMPORT24_PROBE',json.dumps(result))
