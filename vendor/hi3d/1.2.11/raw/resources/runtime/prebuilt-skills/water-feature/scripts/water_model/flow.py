"""Explicit programme water illustration: geometry plus a complete start/stop sequence, not CFD."""
from pathlib import Path
import math,numpy as np,bpy
from . import media
from .product_core import pipe as _g_pipe


def create_flow_illustration(points_mm,radii_mm,material):
    points=np.asarray(points_mm,float)/1000;radii=np.asarray(radii_mm,float)/1000
    if points.ndim!=2 or points.shape[1]!=3 or len(points)<2 or len(points)!=len(radii) or np.any(radii<=0):raise ValueError('Provide matched flow points and positive radii')
    ob,centers,rs=_g_pipe('DISPLAY programme water',points,radii,material,res=8,n=32)
    ob['simulation_status']='Authored water illustration, not flow or leakage proof'
    return ob


def author_flow_cycle(output,objects,water_objects,fps=24):
    """Write native dry→start→steady→stop→dry cycle for caller-selected water objects."""
    if fps<24 or not water_objects:raise ValueError('Requires water geometry and fps >=24')
    s=bpy.context.scene;s.frame_start=1;s.frame_end=144;s.render.fps=fps
    for ob in water_objects:
        for f,hidden in [(1,True),(18,True),(19,False),(116,False),(117,True),(144,True)]:ob.hide_render=hidden;ob.keyframe_insert(data_path='hide_render',frame=f)
        # Reveal via axial growth only if geometry was authored around its own upstream origin.
    framing=media.check_framing(s,s.camera,objects,range(1,145));s.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(Path(output)))
    return {'frames':[1,144],'fps':fps,'framing':framing,'method':'Visibility cycle on actual water meshes; continuous startup/drain morphology must be authored for the current channel when needed','physics':'Not simulated'}
