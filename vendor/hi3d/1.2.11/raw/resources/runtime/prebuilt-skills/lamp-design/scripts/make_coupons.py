"""Standard-library STL coupons. Dimensions in mm; labels encoded in file names."""
import argparse,math,struct,json,io
from pathlib import Path
from coupon_records import clearance_series, pair_record

def stl_bytes(verts,faces):
    def sub(a,b):return [x-y for x,y in zip(a,b)]
    def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
    tris=[]
    for f in faces:
        for i in range(1,len(f)-1):tris.append([verts[f[0]],verts[f[i]],verts[f[i+1]]])
    with io.BytesIO() as out:
        out.write(b'Lamp calibration coupon | millimetres'.ljust(80,b' '));out.write(struct.pack('<I',len(tris)))
        for t in tris:
            n=cross(sub(t[1],t[0]),sub(t[2],t[0]));length=math.sqrt(sum(x*x for x in n));n=[x/length if length else 0 for x in n]
            out.write(struct.pack('<12fH',*n,*(v for p in t for v in p),0))
        return out.getvalue()

def ring_mesh(rout,rin,h):
    if not all(math.isfinite(x) for x in (rout,rin,h)) or not 0 < rin < rout or h <= 0:
        raise ValueError('Require finite 0 < inner radius < outer radius and positive height')
    n=128;v=[];f=[]
    for r,z in [(rout,0),(rout,h),(rin,h),(rin,0)]:
        for i in range(n):v.append((r*math.cos(2*math.pi*i/n),r*math.sin(2*math.pi*i/n),z))
    for k in range(4):
        for i in range(n):f.append((k*n+i,k*n+(i+1)%n,((k+1)%4)*n+(i+1)%n,((k+1)%4)*n+i))
    return v,f

def write_coupons(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    if any(out.glob('*.stl')) or (out/'coupon-guide.json').exists() or (out/'fit-pairs.json').exists():
        raise FileExistsError('Use a fresh coupon output directory')
    # Hollow pin avoids separate n-gon triangulation while retaining a 20 mm OD mating surface.
    (out/'pin_OD20_mm.stl').write_bytes(stl_bytes(*ring_mesh(10,6,15)))
    series=clearance_series([.2,.3,.4,.5],definition='Single-side radial gap; hole diameter = pin diameter + 2*gap')
    pairs=[]
    for candidate in series:
        gap=candidate['clearance_mm'];file=f'ring_radial_gap_{gap:.2f}_mm.stl'
        (out/file).write_bytes(stl_bytes(*ring_mesh(15,10+gap,8)))
        pairs.append(pair_record(str(candidate['index']),{'pin':'pin_OD20_mm.stl','ring':file},clearance_mm=gap,definition=candidate['definition'],orientation='Z axis normal to print bed',source={'generator':'lamp calibration rings','pin_outer_diameter_mm':20}))
    (out/'fit-pairs.json').write_text(json.dumps(pairs,indent=2))
    for thick in [.8,1.2,1.6,2.0]:
        v=[(x,y,z) for z in [0,thick] for y in [0,35] for x in [0,35]]
        (out/f'diffuser_{thick:.1f}_mm.stl').write_bytes(stl_bytes(v,[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)]))
    (out/'coupon-guide.json').write_text(json.dumps({'units':'mm','pin_outer_diameter':20,'single_side_gaps':[.2,.3,.4,.5],
      'diffuser_thicknesses':[.8,1.2,1.6,2.0],'physical_test':'pending','note':'Use the same printer, material batch and settings as the lamp. Labels are filenames; keep samples identified.'},indent=2))
    return sorted(out.glob('*.stl'))

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    files=write_coupons(a.output)
    print(f'Wrote {len(files)} mm-scale STL coupons to {a.output}')

if __name__=='__main__':main()
