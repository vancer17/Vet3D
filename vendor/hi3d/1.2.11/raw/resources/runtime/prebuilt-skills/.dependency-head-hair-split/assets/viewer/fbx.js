/* Narrow FBX 7.4 binary writer: static indexed triangles, Y-up metres, one
   embedded diffuse image, no animation/skinning/PBR extensions. */
const StaticFBX=(()=>{
 const enc=new TextEncoder(),str=s=>enc.encode(s);
 const prop=(type,value)=>({type,value});
 const I=v=>prop('I',v),L=v=>prop('L',v),D=v=>prop('D',v),S=v=>prop('S',v),A=v=>prop(v instanceof Float64Array?'d':'i',v),R=v=>prop('R',v);
 const node=(name,properties=[],children=[])=>({name,properties,children});
 const leaf=(name,p)=>node(name,[p]);
 const P=(name,type,label,flags,...values)=>node('P',[S(name),S(type),S(label),S(flags),...values]);
 async function property(p){
   let payload;
   if(p.type==='S'||p.type==='R'){const b=p.type==='S'?str(p.value):p.value;payload=new Uint8Array(4+b.length);new DataView(payload.buffer).setUint32(0,b.length,true);payload.set(b,4);}
   else if('dilfb'.includes(p.type)){
     const a=p.value,bytes=new Uint8Array(a.buffer,a.byteOffset,a.byteLength);
     const compressed=new Uint8Array(await new Response(new Blob([bytes]).stream().pipeThrough(new CompressionStream('deflate'))).arrayBuffer());
     payload=new Uint8Array(12+compressed.length);const dv=new DataView(payload.buffer);dv.setUint32(0,a.length,true);dv.setUint32(4,1,true);dv.setUint32(8,compressed.length,true);payload.set(compressed,12);
   }else{const len=p.type==='L'||p.type==='D'?8:4;payload=new Uint8Array(len);const dv=new DataView(payload.buffer);if(p.type==='L')dv.setBigInt64(0,BigInt(p.value),true);else if(p.type==='D')dv.setFloat64(0,p.value,true);else dv.setInt32(0,p.value,true);}
   const out=new Uint8Array(payload.length+1);out[0]=p.type.charCodeAt(0);out.set(payload,1);return out;
 }
 async function packNode(n){n.nameBytes=str(n.name);n.packed=[];for(const p of n.properties)n.packed.push(await property(p));delete n.properties;for(const c of n.children)await packNode(c);n.propLen=n.packed.reduce((a,p)=>a+p.length,0);n.size=13+n.nameBytes.length+n.propLen+n.children.reduce((a,c)=>a+c.size,0)+(n.children.length?13:0);}
 function putNode(out,dv,n,offset){const end=offset+n.size;dv.setUint32(offset,end,true);dv.setUint32(offset+4,n.packed.length,true);dv.setUint32(offset+8,n.propLen,true);out[offset+12]=n.nameBytes.length;offset+=13;out.set(n.nameBytes,offset);offset+=n.nameBytes.length;for(const p of n.packed){out.set(p,offset);offset+=p.length;}for(const c of n.children)offset=putNode(out,dv,c,offset);return end;}
 function geometry(d,labels,klass,id,name){
   const nv=d.positions.length/3,map=new Int32Array(nv).fill(-1);let count=0,nf=0;
   for(let f=0;f<labels.length;f++)if(labels[f]===klass){nf++;for(let k=0;k<3;k++){const v=d.faces[f*3+k];if(map[v]<0)map[v]=count++;}}
   if(!nf)throw Error('不能导出空部件');
   const vertices=new Float64Array(count*3),normals=new Float64Array(count*3),uv=new Float64Array(count*2),polys=new Int32Array(nf*3),uvIndex=new Int32Array(nf*3);
   for(let v=0;v<nv;v++)if(map[v]>=0){const k=map[v];for(let c=0;c<3;c++){vertices[k*3+c]=d.positions[v*3+c];normals[k*3+c]=d.normals[v*3+c];}uv[k*2]=d.uv[v*2];uv[k*2+1]=1-d.uv[v*2+1];}
   let t=0;for(let f=0;f<labels.length;f++)if(labels[f]===klass){for(let k=0;k<3;k++){const v=map[d.faces[f*3+k]];uvIndex[t]=v;polys[t++]=k===2?-v-1:v;}}
   const layer=(kind,mapping,reference,data)=>node(kind,[I(0)],[leaf('Version',I(101)),leaf('Name',S(kind==='LayerElementUV'?'UVMap':'')),leaf('MappingInformationType',S(mapping)),leaf('ReferenceInformationType',S(reference)),...data]);
   const smooth=new Int32Array(nf).fill(1);
   return node('Geometry',[L(id),S(name+'\x00\x01Geometry'),S('Mesh')],[leaf('GeometryVersion',I(124)),leaf('Vertices',A(vertices)),leaf('PolygonVertexIndex',A(polys)),
     layer('LayerElementNormal','ByVertice','Direct',[leaf('Normals',A(normals))]),
     layer('LayerElementUV','ByPolygonVertex','IndexToDirect',[leaf('UV',A(uv)),leaf('UVIndex',A(uvIndex))]),
     layer('LayerElementSmoothing','ByPolygon','Direct',[leaf('Smoothing',A(smooth))]),
     layer('LayerElementMaterial','AllSame','IndexToDirect',[leaf('Materials',A(new Int32Array([0])))]),
     node('Layer',[I(0)],[leaf('Version',I(100)),...['Normal','UV','Smoothing','Material'].map(k=>node('LayerElement',[],[leaf('Type',S('LayerElement'+k)),leaf('TypedIndex',I(0))]))])]);
 }
 async function exportFile(d,labels,image,progress=()=>{},material={}){
   const filename=material.filename||'original.jpg',factor=material.factor||[1,1,1];
   const objects=[],connections=[];
   for(let c=0;c<2;c++){
     const name=c?'Hair':'Head',g=100+c,m=200+c;progress('FBX · '+name);
     objects.push(geometry(d,labels,c,g,name));
     objects.push(node('Model',[L(m),S(name+'\x00\x01Model'),S('Mesh')],[leaf('Version',I(232)),node('Properties70',[],[
       P('Lcl Translation','Lcl Translation','','A',D(0),D(0),D(0)),P('Lcl Rotation','Lcl Rotation','','A',D(0),D(0),D(0)),P('Lcl Scaling','Lcl Scaling','','A',D(1),D(1),D(1))]),leaf('Shading',I(1)),leaf('Culling',S('CullingOff'))]));
     connections.push(node('C',[S('OO'),L(g),L(m)]),node('C',[S('OO'),L(m),L(0)]),node('C',[S('OO'),L(300),L(m)]));
   }
   objects.push(node('Material',[L(300),S('OriginalTexture\x00\x01Material'),S('')],[leaf('Version',I(102)),leaf('ShadingModel',S('phong')),leaf('MultiLayer',I(0)),node('Properties70',[],[
     P('DiffuseColor','Color','','A',D(factor[0]),D(factor[1]),D(factor[2])),P('DiffuseFactor','Number','','A',D(1)),P('SpecularFactor','Number','','A',D(.1)),P('Shininess','Number','','A',D(20)),P('Opacity','Number','','A',D(1))])]));
   objects.push(node('Texture',[L(400),S('OriginalTexture\x00\x01Texture'),S('')],[leaf('Type',S('TextureVideoClip')),leaf('Version',I(202)),leaf('TextureName',S('OriginalTexture\x00\x01Texture')),leaf('Media',S(filename+'\x00\x01Video')),leaf('FileName',S(filename)),leaf('RelativeFilename',S(filename)),leaf('ModelUVTranslation',D(0)),node('ModelUVScaling',[D(1),D(1)]),leaf('Texture_Alpha_Source',S('None')),node('Cropping',[I(0),I(0),I(0),I(0)]),node('Properties70',[],[P('WrapModeU','enum','','',I(material.wrapS===33071?1:0)),P('WrapModeV','enum','','',I(material.wrapT===33071?1:0)),P('UVSet','KString','','',S('UVMap')),P('UseMaterial','bool','','',I(1))])]));
   objects.push(node('Video',[L(500),S(filename+'\x00\x01Video'),S('Clip')],[leaf('Type',S('Clip')),node('Properties70',[],[P('Path','KString','XRefUrl','',S(filename))]),leaf('UseMipMap',I(0)),leaf('Filename',S(filename)),leaf('RelativeFilename',S(filename)),leaf('Content',R(image))]));
   connections.push(node('C',[S('OP'),L(400),L(300),S('DiffuseColor')]),node('C',[S('OO'),L(500),L(400)]));
   const roots=[node('FBXHeaderExtension',[],[leaf('FBXHeaderVersion',I(1003)),leaf('FBXVersion',I(7400)),leaf('EncryptionType',I(0)),leaf('Creator',S('Head Hair Split offline static FBX'))]),
     node('GlobalSettings',[],[leaf('Version',I(1000)),node('Properties70',[],[
       ...[['UpAxis',1],['UpAxisSign',1],['FrontAxis',2],['FrontAxisSign',1],['CoordAxis',0],['CoordAxisSign',1]].map(([k,v])=>P(k,'int','Integer','',I(v))),P('UnitScaleFactor','double','Number','',D(100)),P('OriginalUnitScaleFactor','double','Number','',D(100))])]),
     node('Documents',[],[leaf('Count',I(1)),node('Document',[L(1),S('Scene'),S('Scene')],[node('Properties70'),leaf('RootNode',L(0))])]),node('References'),
     node('Definitions',[],[leaf('Version',I(100)),leaf('Count',I(7)),...['Geometry','Model','Material','Texture','Video'].map((s,i)=>node('ObjectType',[S(s)],[leaf('Count',I(i<2?2:1))]))]),node('Objects',[],objects),node('Connections',[],connections),node('Takes',[],[leaf('Current',S(''))])];
   progress('压缩 FBX 数组');for(const r of roots)await packNode(r);
   const nodesEnd=27+roots.reduce((a,r)=>a+r.size,0)+13,footerBase=nodesEnd+20,padding=16-(footerBase%16);
   const size=footerBase+padding+4+120+16,out=new Uint8Array(size),dv=new DataView(out.buffer);
   out.set(str('Kaydara FBX Binary  \x00\x1a\x00'));dv.setUint32(23,7400,true);let off=27;for(const r of roots)off=putNode(out,dv,r,off);
   // Footer magic follows a null top-level sentinel; standard importers use nodes.
   off+=13;out.set([0xfa,0xbc,0xab,0x09,0xd0,0xc8,0xd4,0x66,0xb1,0x76,0xfb,0x83,0x1c,0xf7,0x26,0x7e],off);dv.setUint32(footerBase+padding,7400,true);
   out.set([0xf8,0x5a,0x8c,0x6a,0xde,0xf5,0xd9,0x7e,0xec,0xe9,0x0c,0xe3,0x75,0x8f,0x29,0x0b],size-16);
   return out.buffer;
 }
 return {exportFile};
})();
if(typeof module!=='undefined')module.exports=StaticFBX;
