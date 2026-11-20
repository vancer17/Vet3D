"""Lossless GLB triangle partition: original buffers, attributes and node transforms."""
from pathlib import Path
import copy, json, struct
import numpy as np
from glb_clips import read_glb
DT={5120:'i1',5121:'u1',5122:'<i2',5123:'<u2',5125:'<u4',5126:'<f4'}
SZ={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}
def read(path):
    doc, chunks = read_glb(Path(path).read_bytes())
    if len(chunks) != 1 or chunks[0][0] != b'BIN\x00':
        raise ValueError("Expected a single embedded BIN chunk")
    return doc, chunks[0][1]

def validate(doc, binary):
    if len(doc.get("meshes", [])) != 1 or len(doc["meshes"][0].get("primitives", [])) != 1:
        raise ValueError("Expected one mesh and one primitive")
    if len(doc.get("buffers", [])) != 1 or "uri" in doc["buffers"][0]:
        raise ValueError("Only embedded buffer supported")
    if doc.get("animations") or doc.get("skins") or doc.get("extensionsRequired"):
        raise ValueError("Only uncompressed static meshes supported")
    nodes = [n for n in doc.get("nodes", []) if "mesh" in n]
    if len(nodes) != 1 or nodes[0]["mesh"] != 0 or nodes[0].get("extensions"):
        raise ValueError("Expected one uninstanced mesh node")
    prim = doc["meshes"][0]["primitives"][0]
    if prim.get("mode", 4) != 4 or prim.get("targets") or prim.get("extensions"):
        raise ValueError("Expected static triangle primitive without extensions")
    if "indices" not in prim or "POSITION" not in prim.get("attributes", {}):
        raise ValueError("Indexed POSITION required")
    if doc["accessors"][prim["indices"]]["componentType"] not in (5121, 5123, 5125):
        raise ValueError("Unsigned triangle indices required")
    for img in doc.get("images", []):
        if "bufferView" not in img or "uri" in img:
            raise ValueError("All images must be embedded")
    vertices, faces = arrays(doc, binary)
    if not len(vertices) or not len(faces) or not np.isfinite(vertices).all():
        raise ValueError("Empty or nonfinite geometry")
    if faces.min() < 0 or faces.max() >= len(vertices):
        raise ValueError("Index out of bounds")
    return vertices, faces

def access(d, b, i):
    a = d["accessors"][i]
    if "sparse" in a or a.get("normalized"):
        raise ValueError("Sparse/normalized accessors are not supported")
    v = d["bufferViews"][a["bufferView"]]
    typ, width = np.dtype(DT[a["componentType"]]), SZ[a["type"]]
    count, local = a["count"], a.get("byteOffset", 0)
    offset, stride = v.get("byteOffset", 0), v.get("byteStride", width * typ.itemsize)
    size = width * typ.itemsize
    if v.get("buffer", 0) != 0 or count < 1 or min(local, offset) < 0 or stride < size:
        raise ValueError("Invalid accessor layout")
    if local + (count - 1) * stride + size > v["byteLength"] or offset + v["byteLength"] > min(len(b), d["buffers"][0]["byteLength"]):
        raise ValueError("Accessor exceeds buffer")
    return np.ndarray((count, width), typ, buffer=b, offset=offset+local, strides=(stride, typ.itemsize))

def arrays(d,b):
 p=d['meshes'][0]['primitives'][0]
 return access(d,b,p['attributes']['POSITION']),access(d,b,p['indices']).reshape(-1,3)

def write_partition(path,d,b,faces,labels,names):
 o=copy.deepcopy(d);data=bytearray(b);p=d['meshes'][0]['primitives'][0];o['meshes']=[]
 meshnode=next(n for n in o['nodes'] if n.get('mesh')==0);del meshnode['mesh'];meshnode.setdefault('children',[])
 for k,name in enumerate(names):
  ids=np.flatnonzero(labels==k)
  if not len(ids):continue
  raw=np.ascontiguousarray(faces[ids],dtype='<u4').tobytes()
  while len(data)%4:data.append(0)
  vi=len(o['bufferViews']);o['bufferViews'].append({'buffer':0,'byteOffset':len(data),'byteLength':len(raw),'target':34963});data.extend(raw)
  ai=len(o['accessors']);o['accessors'].append({'bufferView':vi,'componentType':5125,'count':len(ids)*3,'type':'SCALAR'})
  prim=copy.deepcopy(p);prim['indices']=ai
  mi=len(o['meshes']);o['meshes'].append({'name':name,'primitives':[prim],'extras':{'part_id':k,'source_triangle_count':len(ids)}})
  meshnode['children'].append(len(o['nodes']));o['nodes'].append({'name':name,'mesh':mi,'extras':{'part_id':k}})
 o['asset']['generator']='Pure Python segmentation; original geometry and embedded assets preserved'
 o['buffers']=[{'byteLength':len(data)}]
 meta=json.dumps(o,separators=(',',':')).encode();meta+=b' '*(-len(meta)%4);data+=b'\0'*(-len(data)%4)
 body=struct.pack('<I4s',len(meta),b'JSON')+meta+struct.pack('<I4s',len(data),b'BIN\0')+data
 with Path(path).open('xb') as stream:
  stream.write(struct.pack('<4sII',b'glTF',2,len(body)+12)+body)
