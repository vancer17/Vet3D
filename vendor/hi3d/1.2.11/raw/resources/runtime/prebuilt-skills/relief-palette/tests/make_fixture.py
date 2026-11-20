"""Create small synthetic offline inputs outside the package, without model inference."""
import argparse
import base64
import json
from pathlib import Path
import shutil
import struct


def create(directory, package):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
    shutil.copy2(Path(package)/'assets/example/model.py',directory/'model.py')
    # Valid one-pixel PNG identifies a synthetic test fixture, not a cartoon deliverable.
    png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j2ioAAAAASUVORK5CYII=')
    pans=[]
    for i,color in enumerate(['B88A51','8E4942','42272E']):
        (directory/f'{i}.png').write_bytes(png)
        # Closed low-poly bas-relief with a different apex, for geometry regression only.
        vs=[(-1,-1,0),(1,-1,0),(1,1,0),(-1,1,0),(-.3+i*.25,0,.6+i*.2)]
        fs=[(0,2,1),(0,3,2),(0,1,4),(1,2,4),(2,3,4),(3,0,4)]
        body=bytearray(b'Offline synthetic relief'.ljust(80,b'\0')+struct.pack('<I',len(fs)))
        for f in fs:body.extend(struct.pack('<12fH',0,0,0,*[v for k in f for v in vs[k]],0))
        (directory/f'{i}.stl').write_bytes(body)
        pans.append(dict(id=f'pan-{i}',variant_id=f'pose-{i}',color=color,center_mm=[(i-1)*31,3,5.4],
                         size_mm=[27,24,1.8],corner_mm=.8,margin_mm=2,relief_height_mm=.8,embed_mm=.1,
                         axes=[0,1,2],depth_sign=1,image=f'{i}.png',relief=f'{i}.stl'))
    config=dict(schema_version=1,task_id='offline-three-pan',builder='model.py',pans=pans,
                hinge=dict(pivot_mm=[0,28,8.8],axis='X',sign=-1,max_angle=110),
                keyframes=[[1,0],[20,110],[30,110],[50,0]],check_frames=list(range(1,51,3)),
                resolution=[480,400],samples=8,exposure=-2,shots=['open','closed'])
    (directory/'job.json').write_text(json.dumps(config,indent=2))
    return directory/'job.json'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);a=p.parse_args()
    print(create(a.output,Path(__file__).resolve().parents[1]))
