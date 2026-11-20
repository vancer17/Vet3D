"""Original shoulder-and-snap wheel interface, millimetres.
Principles: BOSL2 snap_pin/socket and MMC OpenAT; no source geometry copied.
The elastic endpoint field is a cantilever illustration, not a material simulation.
"""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import numpy as np
from solid_tools import M,cube,cylinder

def ring_solid(profile,n=160):
 # A closed radius/axial profile revolved around Y; each ring uses the same angles.
 verts=[];faces=[]
 for radius,y in profile:
  for t in np.linspace(0,2*np.pi,n,endpoint=False):verts.append([radius*np.cos(t),y,radius*np.sin(t)])
 k=len(profile)
 for j in range(k):
  for i in range(n):
   a=j*n+i;b=j*n+(i+1)%n;c=((j+1)%k)*n+(i+1)%n;d=((j+1)%k)*n+i
   faces.extend([[a,c,b],[a,d,c]])
 m=M.Manifold(M.Mesh(np.asarray(verts,np.float32),np.asarray(faces,np.uint32)))
 if m.volume()<0:m=M.Manifold(M.Mesh(np.asarray(verts,np.float32),np.asarray(faces,np.uint32)[:,::-1].copy()))
 assert m.status()==M.Error.NoError,(m.status(),m.volume())
 return m

def dsolid(radius,lo,hi,c,clearance=0):
 return cylinder(radius,hi-lo,(0,(lo+hi)/2,c['wheel_radius_mm']),'Y',128).trim_by_plane((0,0,1),c['wheel_radius_mm']-c['shoulder_radius_mm']+c['print_flat_mm']-clearance)

def wheel(c,clearance_offset=0):
 radius=c['wheel_radius_mm'];width=c['wheel_width_mm'];cy=c['track_mm']/2
 # Rounded barrel tread: narrow vertical side is kept at the bed, curved edge above.
 ys=np.linspace(cy-width/2,cy+width/2,41)
 rs=radius-c['rim_round_mm']*(np.abs((ys-cy)/(width/2))**4)
 profile=[(c['shoulder_radius_mm']+c['wheel_radial_clearance_mm']+clearance_offset,float(ys[0]))]+list(zip(rs,ys))+[(c['shoulder_radius_mm']+c['wheel_radial_clearance_mm']+clearance_offset,float(ys[-1]))]
 w=ring_solid(profile).translate((0,0,radius))
 # Head is low and captive, fully recessed into the visual hub.
 w-=cylinder(c['head_radius_mm']+c['head_recess_radial_clearance_mm'],4,(0,c['head_stop_y_mm']+1.5,radius),'Y',128)
 return w

def pin(c):
 z=c['wheel_radius_mm'];root=c['beam_root_y_mm'];back=c['barb_back_y_mm'];tip=c['tip_y_mm'];half=c['tail_halfwidth_mm'];h=c['tail_height_mm'];bed=z-c['shoulder_radius_mm']+c['print_flat_mm'];barb=half+c['barb_projection_mm']
 s=dsolid(c['shoulder_radius_mm'],c['shoulder_stop_y_mm'],c['head_stop_y_mm']+.15,c)
 s+=dsolid(c['head_radius_mm'],c['head_stop_y_mm'],c['head_stop_y_mm']+c['head_thickness_mm'],c)
 # Two flexible tails and solid root transition are one component with the shoulder.
 pts=[[-half,c['shoulder_stop_y_mm']+.4],[half,c['shoulder_stop_y_mm']+.4],[half,back],[barb,back],[barb,back-.9],[half-.3,tip],[-half+.3,tip],[-barb,back-.9],[-barb,back],[-half,back]]
 tail=M.CrossSection([pts[::-1]]).extrude(h).translate((0,0,bed));s+=tail
 rr=c['slot_root_radius_mm'];gap=cube((2*rr,root-rr-tip+8,h+4),(0,(tip-8+root-rr)/2,bed+h/2))
 gap+=cylinder(rr,h+4,(0,root-rr,bed+h/2),'Z',64)
 return s-gap

def socket(c,clearance_offset=0):
 z=c['wheel_radius_mm'];outer=c['seat_outer_y_mm'];inner=c['seat_inner_y_mm'];stop=c['shoulder_stop_y_mm'];center=(inner+outer)/2
 body=cube((15,outer-inner,13),(0,center,z))
 body+=cube((10,outer-inner,9),(0,center,20))
 # Finite unbroken shoulder journal, with flat preventing the pin from rotating.
 body-=dsolid(c['shoulder_radius_mm']+c['seat_radial_clearance_mm']+clearance_offset,stop,outer+1,c,c['seat_radial_clearance_mm']+clearance_offset)
 bed=z-c['shoulder_radius_mm']+c['print_flat_mm']
 body-=cube((c['socket_tail_width_mm']+2*clearance_offset,stop-inner+2,c['tail_height_mm']+2*c['tail_vertical_clearance_mm']),(0,(inner+stop)/2,bed+c['tail_height_mm']/2))
 return body

def compressed_mesh(s,c,delta):
 # Shift the two tails in X using the small-deflection cantilever shape.
 mesh=s.to_mesh();v=np.asarray(mesh.vert_properties[:,:3],dtype=float).copy();root=c['beam_root_y_mm'];L=root-c['barb_back_y_mm'];u=np.clip((root-v[:,1])/L,0,1);shape=u*u*(3-u)/2
 v[:,0]-=np.sign(v[:,0])*delta*shape
 return M.Manifold(M.Mesh(np.asarray(v,np.float32),np.asarray(mesh.tri_verts,np.uint32))),v,np.asarray(mesh.tri_verts,np.uint32)

def insertion_delta(c,shift):
 # Full displacement while a barb occupies the straight seat. Release as it clears its inner edge.
 back=c['barb_back_y_mm']+shift;front=back-.9
 outer=c['seat_outer_y_mm'];inner=c['seat_inner_y_mm'];need=c['tail_halfwidth_mm']+c['barb_projection_mm']-c['socket_tail_width_mm']/2+c['animation_safety_clearance_mm']
 if c['tip_y_mm']+shift>=outer+.5:return 0.
 if back<=inner:return 0.
 return need

def release_tool(c):
 # Rigid fork, no bend or purchased fastener. Its entry ramps compress both exposed tails.
 half=c['socket_tail_width_mm']/2-c['animation_safety_clearance_mm'];y0=3.;y1=c['seat_inner_y_mm']-.1;bed=0
 pts=[[-7.5,y0],[7.5,y0],[7.5,y1],[half+.3,y1],[half,y1-.05],[half,y0+5],[-half,y0+5],[-half,y1-.05],[-half-.3,y1],[-7.5,y1]]
 return M.CrossSection([pts]).extrude(4.6)
