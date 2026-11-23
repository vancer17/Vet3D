import bpy, bmesh, numpy as np, math, json, struct, os, pathlib
from pathlib import Path
from mathutils import Vector, Matrix
from math import sin, cos, pi
MM = S = .001
def render(path,w=1200,h=1000,samples=24,*,enabled=True,engine=None):
 if not enabled:return None
 s=bpy.context.scene;previous=s.render.engine;s.render.engine=engine or previous;s.render.resolution_x=w;s.render.resolution_y=h;s.cycles.samples=samples;s.render.filepath=str(path);bpy.ops.render.render(write_still=True);s.render.engine=previous
