#!/usr/bin/env python3
"""Generate an original, fixed generic adult-shaped mannequin; no personal input.

Python 3.9+, standard library only. Output OBJ coordinates are millimetres.
This is a design fixture, not a scan, anthropometric standard or certified headform.
"""
import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

PROFILE = [(-145,45,42,18),(-108,44,43,18),(-82,42,39,8),
           (-68,41,39,-2),(-52,56,62,5),(-22,68,79,12),
           (8,72,89,15),(40,74,88,19),(76,70,79,20),
           (106,54,60,19),(125,26,31,18),(130,0,0,18)]

def slopes(column):
    h=[b[0]-a[0] for a,b in zip(PROFILE,PROFILE[1:])]
    d=[(b[column]-a[column])/step for a,b,step in zip(PROFILE,PROFILE[1:],h)]
    out=[d[0]]
    for i in range(1,len(PROFILE)-1):
        if d[i-1]*d[i]<=0:out.append(0.)
        else:
            w1=2*h[i]+h[i-1];w2=h[i]+2*h[i-1]
            out.append((w1+w2)/(w1/d[i-1]+w2/d[i]))
    return out+[d[-1]]

SLOPES={c:slopes(c) for c in (1,2,3)}

def profile(z):
    # Monotone cubic derivatives avoid the horizontal terraces produced by
    # resetting the slope to zero at every profile sample.
    for k,(a,b) in enumerate(zip(PROFILE, PROFILE[1:])):
        if z <= b[0]:
            h=b[0]-a[0];t=(z-a[0])/h
            return tuple((2*t**3-3*t**2+1)*a[c]+(t**3-2*t*t+t)*h*SLOPES[c][k]
                         +(-2*t**3+3*t*t)*b[c]+(t**3-t*t)*h*SLOPES[c][k+1] for c in (1,2,3))
    return PROFILE[-1][1:]

def bump(x,z,cx,cz,wx,wz):
    return math.exp(-((x-cx)/wx)**2-((z-cz)/wz)**2)

def point(z, angle):
    width,depth,cy=profile(z); sn,cs=math.sin(angle),math.cos(angle)
    x=width*sn; y=cy-depth*cs
    # Ear/cheek envelope is continuous with the head, not detached decoration.
    x += math.copysign(9*math.exp(-((z-7)/23)**2)*abs(sn)**30, sn)
    if cs > 0:
        relief=14*bump(x,z,0,14,10,28)+20*bump(x,z,0,-6,11,10)
        relief+=sum(5*bump(x,z,s*11,-11,6,7) for s in (-1,1))
        relief+=sum(4*bump(x,z,s*43,-1,18,24)+3*bump(x,z,s*30,44,20,6)-4*bump(x,z,s*32,32,15,9) for s in (-1,1))
        relief+=4*bump(x,z,0,-34,21,5)+5*bump(x,z,0,-56,24,10)
        y-=relief*cs**2
    return (x,y,z)

def sub(a,b): return tuple(x-y for x,y in zip(a,b))
def cross(a,b): return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def dot(a,b): return sum(x*y for x,y in zip(a,b))

def build_head():
    """Return fixed fixture vertices (mm) and outward triangles; no I/O."""
    sectors=192; rings=184
    vertices=[point(-145+274*i/(rings-1),2*math.pi*j/sectors) for i in range(rings) for j in range(sectors)]
    faces=[]
    for i in range(rings-1):
        for j in range(sectors):
            a=i*sectors+j;b=i*sectors+(j+1)%sectors;c=b+sectors;d=a+sectors
            faces.extend([(a,b,c),(a,c,d)])
    bottom=len(vertices);vertices.append((0,18,-145));top=len(vertices);vertices.append((0,18,130))
    for j in range(sectors):
        k=(j+1)%sectors;faces.append((bottom,k,j));faces.append((top,(rings-1)*sectors+j,(rings-1)*sectors+k))
    volume=sum(dot(vertices[a],cross(vertices[b],vertices[c])) for a,b,c in faces)/6
    if volume<0:faces=[(a,c,b) for a,b,c in faces]
    return vertices, faces


def head_metadata(vertices, faces, obj_digest):
    """Audit fixture/provenance without I/O; ValueError on invalid topology."""
    volume=sum(dot(vertices[a],cross(vertices[b],vertices[c])) for a,b,c in faces)/6
    edges=Counter(tuple(sorted((a,b))) for f in faces for a,b in zip(f,f[1:]+f[:1]))
    if not faces or not all(n==2 for n in edges.values()) or volume<=0:
        raise ValueError('Fixture must have closed positive-volume topology')
    if min(dot(n,n) for a,b,c in faces for n in [cross(sub(vertices[b],vertices[a]),sub(vertices[c],vertices[a]))])<=1e-14:
        raise ValueError('Fixture contains degenerate triangles')
    lo=[min(v[i] for v in vertices) for i in range(3)];hi=[max(v[i] for v in vertices) for i in range(3)]
    report={'name':'Default_Adult_Head_v1','head_source':'generic_default','personal_identity':False,'source':'Original procedural geometry from bundled default_head.py; no photos or individual scans','license':'CC0-1.0 for this generated original fixture','mesh':'default-head.obj','units':'mm','coordinate_convention':'X transverse, -Y anterior, Z up','vertices':len(vertices),'triangles':len(faces),'bounds_mm':[lo,hi],'dimensions_including_neck_mm':[b-a for a,b in zip(lo,hi)],'eye_region_landmarks_xz_mm':[[-32,32],[32,32]],'nose_region_xz_mm':[0,-6],'mouth_region_xz_mm':[0,-34],'landmark_status':'Synthetic design coordinates, not measured human anatomy','topology':{'edge_incidence_two':True,'euler_characteristic':len(vertices)-len(edges)+len(faces),'signed_volume_mm3':volume},'sha256':obj_digest,'limits':['Non-personal fixture; never label as the user head','Not an anthropometric average, size coverage claim or medical standard','Closed stylized eye/nostril surfaces do not model real eyeballs or nasal lumen','Physical fit and wearer comfort remain untested']}
    return report


def obj_text(vertices, faces):
    """Serialize deterministic millimetre OBJ without file effects."""
    lines=['# Original generic mannequin. Coordinates in mm; X left/right, -Y front, Z up.\n', 'o Default_Adult_Head_v1\n']
    lines.extend('v %.9f %.9f %.9f\n'%v for v in vertices)
    lines.extend('f %d %d %d\n'%tuple(i+1 for i in f) for f in faces)
    return ''.join(lines)


def save_head(dest, text, metadata):
    """Write exclusive OBJ/JSON; retain partial writes for inspection on failure."""
    dest=Path(dest).resolve()
    obj=dest/'default-head.obj'; meta=dest/'default-head.json'
    if obj.exists() or meta.exists():
        raise FileExistsError('Output already exists; reuse it or choose a new directory')
    dest.mkdir(parents=True,exist_ok=True)
    with obj.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(text)
    with meta.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(metadata,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    return obj,meta


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',required=True,type=Path)
    args=ap.parse_args()
    vertices,faces=build_head()
    text=obj_text(vertices,faces)
    metadata=head_metadata(vertices,faces,hashlib.sha256(text.encode('utf-8')).hexdigest())
    obj,meta=save_head(args.out,text,metadata)
    print(json.dumps({'mesh':str(obj),'metadata':str(meta),'triangles':len(faces),'head_source':'generic_default'},ensure_ascii=False))

if __name__=='__main__':main()
