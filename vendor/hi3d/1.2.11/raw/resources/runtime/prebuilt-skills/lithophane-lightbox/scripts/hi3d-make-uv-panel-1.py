#!/usr/bin/env python3
"""Make a flat-backed V5 UV panel from a photo and a registered 0..1 heightfield.

Requires numpy and Pillow. No GLB-unit guessing or optical calibration.
"""
from pathlib import Path
import argparse
import io
import json
import math
import struct
import hashlib
import numpy as np
from PIL import Image, ImageCms, ImageOps


def sample(a,x,y):
    h,w=a.shape[:2];x=np.clip(x,0,w-1);y=np.clip(y,0,h-1)
    i,j=np.floor(x).astype(int),np.floor(y).astype(int)
    ii,jj=np.minimum(i+1,w-1),np.minimum(j+1,h-1)
    u,v=x-i,y-j
    if a.ndim==3:u,v=u[...,None],v[...,None]
    return ((1-u)*(1-v)*a[j,i]+u*(1-v)*a[j,ii]
            +(1-u)*v*a[jj,i]+u*v*a[jj,ii])


def mesh_from_field(bounds,pitch,field):
    x0,y0,x1,y1=bounds
    nx,ny=math.ceil((x1-x0)/pitch)+1,math.ceil((y1-y0)/pitch)+1
    if (nx-1)*(ny-1)>1_000_000:
        raise ValueError('mesh exceeds 1 million top cells; choose a coarser --pitch')
    xx,yy=np.meshgrid(np.linspace(x0,x1,nx),np.linspace(y0,y1,ny))
    zz=field(xx,yy)
    top=np.stack([xx-x0,yy-y0,zz],axis=-1).reshape(-1,3)
    ids=np.arange(nx*ny).reshape(ny,nx)
    a,b,c,d=(ids[:-1,:-1].ravel(),ids[:-1,1:].ravel(),
             ids[1:,:-1].ravel(),ids[1:,1:].ravel())
    fs=[np.stack([a,b,d],axis=1),np.stack([a,d,c],axis=1)]
    ring=np.r_[ids[0],ids[1:,-1],ids[-1,-2::-1],ids[-2:0:-1,0]]
    bottom=top[ring].copy();bottom[:,2]=0
    bi=np.arange(len(ring))+len(top);rn=np.roll(ring,-1);bn=np.roll(bi,-1)
    fs.extend([np.stack([ring,bi,bn],axis=1),np.stack([ring,bn,rn],axis=1),
               np.stack([np.full(len(ring),len(top)+len(bottom)),bn,bi],axis=1)])
    v=np.vstack([top,bottom,[(x1-x0)/2,(y1-y0)/2,0]]).astype(np.float32)
    return v,np.vstack(fs).astype(np.int32),zz


def save_checked_stl(path,v,f,z):
    e=np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]])
    _,inv,count=np.unique(np.sort(e,axis=1),axis=0,return_inverse=True,return_counts=True)
    balance=np.bincount(inv,weights=np.where(e[:,0]<e[:,1],1,-1))
    tri=v[f].astype(float)
    normal=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
    norm=np.linalg.norm(normal,axis=1)
    volume=float(np.einsum('ij,ij->i',tri[:,0],np.cross(tri[:,1],tri[:,2])).sum()/6)
    if not (np.all(count==2) and np.all(balance==0) and np.all(norm>1e-9) and volume>0):
        raise ValueError('mesh topology validation failed')
    dtype=np.dtype([('n','<f4',(3,)),('v','<f4',(3,3)),('a','<u2')])
    data=np.zeros(len(f),dtype=dtype);data['n']=normal/norm[:,None];data['v']=tri
    with path.open('wb') as h:
        h.write(b'V5 UV white relief | mm | XY flat | planar back Z0'.ljust(80,b' '))
        h.write(struct.pack('<I',len(f)));h.write(data.tobytes())
    raw=path.read_bytes()
    saved=np.frombuffer(raw,dtype=dtype,offset=84)
    if len(raw)!=84+50*len(f) or not np.array_equal(saved['v'],v[f]):
        raise ValueError('STL round trip failed')
    return dict(file=path.name,units='mm',triangles=len(f),closed_edges=True,
        consistent_winding=True,zero_area_triangles=0,volume_mm3=volume,
        extents_mm=(v.max(0)-v.min(0)).tolist(),planar_back_z_mm=0,
        surface_z_range_mm=[float(z.min()),float(z.max())],stl_round_trip='PASS',
        construction='single-valued front heightfield, rectangular planar back')


def rgb_photo(path):
    im=ImageOps.exif_transpose(Image.open(path))
    alpha=(im.convert('RGBA').getchannel('A')
           if 'A' in im.getbands() or 'transparency' in im.info else None)
    base=im if alpha is None and im.mode in ('RGB','CMYK','L') else im.convert('RGB')
    if im.info.get('icc_profile'):
        src=ImageCms.ImageCmsProfile(io.BytesIO(im.info['icc_profile']))
        base=ImageCms.profileToProfile(base,src,ImageCms.createProfile('sRGB'),outputMode='RGB')
    else:base=base.convert('RGB')
    # Composite in sRGB after profile conversion, preserving the displayed photo.
    if alpha is not None:
        rgba=base.convert('RGBA');rgba.putalpha(alpha)
        bg=Image.new('RGBA',im.size,'white');bg.alpha_composite(rgba);base=bg.convert('RGB')
    return np.asarray(base,dtype=np.float32)


def crop_box(photo,visible,crop=None):
    if crop is None:
        source_ratio=photo.shape[1]/photo.shape[0];target=visible[0]/visible[1]
        if source_ratio>target:
            width=target/source_ratio;crop=[(1-width)/2,0,(1+width)/2,1]
        else:
            height=source_ratio/target;crop=[0,(1-height)/2,1,(1+height)/2]
    x0,y0,x1,y1=map(float,crop)
    if not all(math.isfinite(x) for x in crop) or not (0<=x0<x1<=1 and 0<=y0<y1<=1):
        raise ValueError('crop must be finite normalized x0 y0 x1 y1 inside 0..1')
    ratio=(x1-x0)*photo.shape[1]/((y1-y0)*photo.shape[0])
    if not math.isclose(ratio,visible[0]/visible[1],rel_tol=1e-5):
        raise ValueError('crop aspect ratio must match the visible window; do not stretch')
    return [x0,y0,x1,y1]


class Panel:
    def __init__(self,spec,photo,height,args):
        self.pw,self.ph=map(float,spec['finished_panel'])
        self.vw,self.vh=map(float,spec['visible_image'])
        self.o=float(spec['panel_overlap_each_edge'])
        self.edge=float(spec['mounting_edge_thickness'])
        vals=[self.pw,self.ph,self.vw,self.vh,self.o,self.edge]
        if not all(math.isfinite(x) for x in vals):raise ValueError('invalid interface numbers')
        if spec.get('units')!='mm' or spec.get('version')!='frame_V5_interface':
            raise ValueError('use an explicit millimetre frame_V5_interface')
        if not (math.isclose(self.o,3.5) and math.isclose(self.pw,self.vw+2*self.o)
                and math.isclose(self.ph,self.vh+2*self.o) and min(vals)>0):
            raise ValueError('inconsistent V5 panel/visible/overlap dimensions')
        if not 1.5<=self.edge<=3:raise ValueError('edge thickness must be 1.5..3 mm')
        self.photo,self.height=photo,height
        self.base,self.rise=args.base_thickness,args.relief_height
        self.crop=crop_box(photo,[self.vw,self.vh],args.crop)
        self.w,self.h=round(self.pw*args.pixels_per_mm),round(self.ph*args.pixels_per_mm)
        if min(self.w,self.h)<1 or self.w*self.h>40_000_000:
            raise ValueError('raster size must be 1..40 million pixels; adjust --pixels-per-mm')
        self.sx,self.sy=self.w/self.pw,self.h/self.ph

    def uv(self,x,y):
        a,b,c,d=self.crop
        return a+(x-self.o)/self.vw*(c-a), b+(1-(y-self.o)/self.vh)*(d-b)

    def front(self,x,y,mounting=True):
        u,v=self.uv(x,y)
        h=sample(self.height,u*(self.height.shape[1]-1),(1-v)*(self.height.shape[0]-1))
        t=self.base+self.rise*h
        if mounting:
            distance=np.minimum.reduce([x,self.pw-x,y,self.ph-y])
            blend=np.clip((distance-(self.o-1)),0,1)
            t=self.edge*(1-blend)+t*blend
        return t

    def raster(self):
        out=np.full((self.h,self.w,3),255,np.uint8)
        for start in range(0,self.h,128):
            rows=np.arange(start,min(start+128,self.h))
            xx,yy=np.meshgrid((np.arange(self.w)+.5)/self.sx,self.ph-(rows+.5)/self.sy)
            u,v=self.uv(xx,yy)
            c=sample(self.photo,u*(self.photo.shape[1]-1),v*(self.photo.shape[0]-1))
            active=(xx>=self.o)&(xx<=self.pw-self.o)&(yy>=self.o)&(yy<=self.ph-self.o)
            c[~active]=255
            out[rows]=np.clip(np.rint(c),0,255).astype(np.uint8)
        return Image.fromarray(out)


def save_rasters(image,stem,physical):
    dpi=(image.width*25.4/physical[0],image.height*25.4/physical[1])
    icc=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    checks=[]
    for ext in ['.png','.tif']:
        path=Path(str(stem)+ext);kw=dict(dpi=dpi,icc_profile=icc)
        if ext=='.tif':kw['compression']='tiff_lzw'
        image.save(path,**kw);r=Image.open(path)
        if not np.array_equal(np.asarray(image),np.asarray(r)):raise ValueError('image round trip failed')
        checks.append(dict(file=path.name,pixels=list(image.size),physical_mm=list(physical),
            dpi=[float(x) for x in r.info['dpi']],icc='sRGB',lossless_round_trip='PASS'))
    return checks


def guide(path,panel):
    w,h=panel.pw,panel.ph;o=panel.o
    path.write_text(f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w+30}mm" height="{h+36}mm" viewBox="0 0 {w+30} {h+36}">
<rect width="100%" height="100%" fill="white"/>
<g font-family="sans-serif" font-size="3"><text x="15" y="7">FRONT VIEW - TOP +Y - NO MIRROR</text>
<rect x="15" y="15" width="{w}" height="{h}" fill="#eee" stroke="black" stroke-width="0.2"/>
<rect x="{15+o}" y="{15+o}" width="{panel.vw}" height="{panel.vh}" fill="white" stroke="#c30" stroke-width="0.15"/>
<text x="15" y="{h+21}">Plate {w:g} x {h:g} mm; visible {panel.vw:g} x {panel.vh:g} mm</text>
<text x="15" y="{h+26}">Lower-left plate corner X0 Y0. Guide only, not print artwork.</text>
<text x="15" y="{h+31}">RIP: exact physical size; no fit-to-page; no auto white ink.</text></g></svg>''')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['interface','photo','heightfield','out']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--height-origin',choices=['bottom-left','top-left'],required=True)
    p.add_argument('--base-thickness',type=float,default=1.65)
    p.add_argument('--relief-height',type=float,default=.55)
    p.add_argument('--pitch',type=float,default=.25)
    p.add_argument('--pixels-per-mm',type=float,default=24)
    p.add_argument('--crop',nargs=4,type=float)
    p.add_argument('--coupon',nargs=4,type=float,metavar=('X0','Y0','X1','Y1'))
    a=p.parse_args()
    try:
        vals=[a.base_thickness,a.relief_height,a.pitch,a.pixels_per_mm]
        if not all(math.isfinite(x) for x in vals) or min(a.base_thickness,a.pitch,a.pixels_per_mm)<=0 or a.relief_height<0:
            raise ValueError('thickness, pitch and pixel density must be finite; relief cannot be negative')
        if a.base_thickness+a.relief_height>3:raise ValueError('panel exceeds conservative V5 3 mm envelope')
        height=np.load(a.heightfield,allow_pickle=False)
        if height.ndim!=2 or min(height.shape)<2 or not np.isfinite(height).all() or height.min()<0 or height.max()>1:
            raise ValueError('heightfield must be a finite 2D 0..1 array, at least 2x2')
        if a.height_origin=='top-left':height=height[::-1]
        spec=json.loads(a.interface.read_text());photo=rgb_photo(a.photo)
        panel=Panel(spec,photo,height,a)
        # Validate/snap a requested coupon before writing any manufacturing output.
        coupon=None;pixel_box=None
        if a.coupon:
            x0,y0,x1,y1=a.coupon
            if not all(math.isfinite(x) for x in a.coupon) or not (
                panel.o<=x0<x1<=panel.pw-panel.o and panel.o<=y0<y1<=panel.ph-panel.o):
                raise ValueError('coupon must lie inside the visible image')
            left,top,right,bottom=(round(x0*panel.sx),round((panel.ph-y1)*panel.sy),
                                   round(x1*panel.sx),round((panel.ph-y0)*panel.sy))
            if left>=right or top>=bottom:raise ValueError('coupon smaller than one raster pixel')
            pixel_box=(left,top,right,bottom)
            coupon=[left/panel.sx,panel.ph-bottom/panel.sy,right/panel.sx,panel.ph-top/panel.sy]
        a.out.mkdir(parents=True,exist_ok=True)
        checks={'geometry':[],'rasters':[],'optical_calibration':'NOT performed','physical_test':False}
        full=panel.raster()
        bounds=[0,0,panel.pw,panel.ph]
        v,f,z=mesh_from_field(bounds,a.pitch,panel.front)
        checks['geometry'].append(save_checked_stl(a.out/'hi3d-panel-flat-white.stl',v,f,z))
        checks['rasters']+=save_rasters(full,a.out/'hi3d-panel-uv-colour',[panel.pw,panel.ph])
        if coupon:
            v,f,z=mesh_from_field(coupon,a.pitch,lambda x,y:panel.front(x,y,False))
            checks['geometry'].append(save_checked_stl(a.out/'hi3d-coupon-flat-white.stl',v,f,z))
            im=full.crop(pixel_box)
            size=[coupon[2]-coupon[0],coupon[3]-coupon[1]]
            checks['rasters']+=save_rasters(im,a.out/'hi3d-coupon-uv-colour',size)
            checks['coupon']={'requested_bounds_mm':a.coupon,'actual_bounds_mm':coupon,
                'alignment':'exact full-raster crop; mesh uses same actual bounds',
                'note':'bounds snapped to nearest full-raster pixel; see actual dimensions'}
        guide(a.out/'hi3d-position-guide-1to1.svg',panel)
        result=dict(version='UV_panel_prototype',frame_interface=spec,
            crop_normalized_top_left=panel.crop,base_thickness_mm=a.base_thickness,
            relief_rise_mm=a.relief_height,edge_thickness_mm=panel.edge,
            raster_pixels_per_mm=[panel.sx,panel.sy],mesh_pitch_limit_mm=a.pitch,
            axes='X right, Y photo up, Z thickness; planar back Z0 down; front UV print, no mirror',
            white_ink='OFF for initial white-substrate test; confirm with UV operator',
            colour='sRGB master; actual output profile/ink limits set in UV RIP',
            geometry='provided geometric heightfield; no photometric transmission calibration',
            material='white transmitting material; actual adhesion/transmission untested',
            source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [a.photo,a.heightfield,a.interface]},
            checks=checks)
        (a.out/'hi3d-manufacturing-spec.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        print(json.dumps({'output':str(a.out.resolve()),'panel_mm':[panel.pw,panel.ph],
            'crop':panel.crop,'geometry_checks':'PASS','coupon':checks.get('coupon')},ensure_ascii=False))
    except (ValueError,TypeError,KeyError,OSError) as e:p.error(str(e))


if __name__=='__main__':main()
