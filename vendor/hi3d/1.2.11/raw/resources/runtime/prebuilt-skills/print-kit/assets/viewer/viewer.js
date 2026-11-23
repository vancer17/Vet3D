try {
/* Offline STL-byte viewer. Bundled Three.js MIT; no network requests. */
const D=window.PRINT_KIT;
const canvas=document.getElementById('view');
const renderer=new THREE.WebGLRenderer({canvas,antialias:true});
renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.setClearColor('#e8eaeb');
renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;
const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(38,1,.1,10000);camera.up.set(0,0,1);
scene.add(new THREE.HemisphereLight(0xffffff,0x647080,2));
for(const [p,power] of [[[300,-350,600],3],[[-350,0,200],1]]){const l=new THREE.DirectionalLight(0xffffff,power);l.position.set(...p);scene.add(l);}
function loadSTL(b64){
 const bytes=Uint8Array.from(atob(b64),c=>c.charCodeAt(0)),v=new DataView(bytes.buffer),n=v.getUint32(80,true);
 if(bytes.length!==84+50*n)throw new Error('Invalid binary STL');
 const a=new Float32Array(n*9);
 for(let f=0;f<n;f++)for(let j=0;j<9;j++)a[f*9+j]=v.getFloat32(84+50*f+12+j*4,true);
 const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.BufferAttribute(a,3));g.computeVertexNormals();return g;
}
const geometries=Object.fromEntries(Object.entries(D.stl).map(([k,v])=>[k,loadSTL(v)]));
const pby=Object.fromEntries(D.plan.parts.map(p=>[p.id,p]));
const objs=D.plan.instances.map(i=>{const o=new THREE.Mesh(geometries[i.part],new THREE.MeshStandardMaterial({color:pby[i.part].color,roughness:.55,flatShading:true}));o.matrixAutoUpdate=false;scene.add(o);return o;});
let az=.65,el=.58,dist=400,target=new THREE.Vector3(),mode='assembly',expl=0;
function mat(rows){return new THREE.Matrix4().fromArray(rows.flat()).transpose();}
function modeMatrix(i){
 const m=mat(i.matrix);
 if(mode==='exploded'){m.elements[12]+=i.explode[0]*expl;m.elements[13]+=i.explode[1]*expl;m.elements[14]+=i.explode[2]*expl;}
 if(mode==='plates'){
  const p=D.plan.plates.find(p=>p.instance===i.id),idx=p.plate-1,cols=Math.min(3,Math.max(...D.plan.plates.map(p=>p.plate)));
  const b=mat(p.matrix);b.elements[12]+=(idx%cols)*(D.plan.bed_mm[0]+20);b.elements[13]+=Math.floor(idx/cols)*(D.plan.bed_mm[1]+20);return b;
 }
 if(mode==='operation'&&(D.plan.motions||[]).length){
  const mo=D.plan.motions[0];if(mo.instances.includes(i.id)){
   let r;
   if(mo.type==='translation')r=new THREE.Matrix4().makeTranslation(...new THREE.Vector3(...mo.direction).normalize().multiplyScalar(mo.distance_mm).toArray());
   else {const p=mo.pivot,axis=new THREE.Vector3(...({x:[1,0,0],y:[0,1,0],z:[0,0,1]}[mo.axis]));r=new THREE.Matrix4().makeTranslation(...p).multiply(new THREE.Matrix4().makeRotationAxis(axis,mo.end_deg*Math.PI/180)).multiply(new THREE.Matrix4().makeTranslation(...p.map(x=>-x)));}
   return r.multiply(m);
  }
 }
 return m;
}
function update(fit=false){objs.forEach((o,n)=>{o.matrix.copy(modeMatrix(D.plan.instances[n]));o.updateMatrixWorld(true);});if(fit){const b=new THREE.Box3();objs.forEach(o=>{if(o.visible)b.expandByObject(o);});if(b.isEmpty())return; b.getCenter(target);dist=Math.max(b.getSize(new THREE.Vector3()).length()*1.5,60);if(mode==='plates'){az=0;el=1.48;}else{az=.65;el=.58;}}draw();}
function draw(){const w=canvas.clientWidth,h=canvas.clientHeight;if(canvas.width!==Math.round(w*renderer.getPixelRatio())||canvas.height!==Math.round(h*renderer.getPixelRatio()))renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();camera.position.copy(target).add(new THREE.Vector3(Math.sin(az)*Math.cos(el),-Math.cos(az)*Math.cos(el),Math.sin(el)).multiplyScalar(dist));camera.lookAt(target);renderer.render(scene,camera);}
let pointer=null;
canvas.addEventListener('pointerdown',e=>{pointer=[e.clientX,e.clientY];canvas.setPointerCapture(e.pointerId);});
canvas.addEventListener('pointermove',e=>{if(!pointer)return;az-=(e.clientX-pointer[0])*.008;el=Math.max(-1.4,Math.min(1.55,el+(e.clientY-pointer[1])*.007));pointer=[e.clientX,e.clientY];draw();});
canvas.addEventListener('pointerup',()=>pointer=null);canvas.addEventListener('pointercancel',()=>pointer=null);canvas.addEventListener('wheel',e=>{e.preventDefault();dist=Math.max(20,Math.min(3000,dist*Math.exp(e.deltaY*.001)));draw();},{passive:false});
document.getElementById('mode').onchange=e=>{mode=e.target.value;expl=1;document.getElementById('explode').value=100;update(true);};
document.getElementById('explode').oninput=e=>{mode='exploded';document.getElementById('mode').value=mode;expl=e.target.value/100;update(false);};
document.getElementById('reset').onclick=()=>update(true);
const list=document.getElementById('parts');
for(const p of D.plan.parts){
 const label=document.createElement('label'),box=document.createElement('input'),text=document.createElement('span'),link=document.createElement('a');
 box.type='checkbox';box.checked=true;text.textContent=` ${p.id} ×${p.qty} `;text.style.color=p.color;
 link.textContent='STL';link.download=p.id+'.stl';link.href=printKitBlob(D.stl[p.id],'model/stl');
 box.onchange=()=>{D.plan.instances.forEach((i,n)=>{if(i.part===p.id)objs[n].visible=box.checked;});draw();};
 label.append(box,text,link);list.append(label);
}
if(!(D.plan.motions||[]).length)document.querySelector('option[value="operation"]').remove();
new ResizeObserver(draw).observe(canvas);update(true);

window.PRINT_KIT_VIEWER_READY=true;

} catch(error) {document.getElementById("viewer-status").textContent="3D 预览无法启动：请使用支持 WebGL 的浏览器。上方文件仍可下载。";console.error(error);}
