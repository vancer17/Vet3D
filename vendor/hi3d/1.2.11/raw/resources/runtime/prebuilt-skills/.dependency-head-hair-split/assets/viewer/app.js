const $=id=>document.getElementById(id),meta=JSON.parse($('metadata').textContent);
let worker,d,raw,imageBytes,renderer,last=null,ready=false,busy=false,watchdog,workerURL;
window.__portrait={ready:false,meta};
const state={threshold:meta.threshold,part:0,final:false};
function from64(text){const s=atob(text.trim()),v=new Uint8Array(s.length);for(let i=0;i<s.length;i++)v[i]=s.charCodeAt(i);return v;}
function status(text,error=false){$('status').textContent=text;$('status').classList.toggle('error',error);}
function busyState(value){busy=value;$('threshold').disabled=value||!ready;$('process').disabled=value||!ready;$('download').disabled=value||!last||last.stats.threshold!==state.threshold;$('cancel').style.display=value?'block':'none';}
function startWorker(){
 ready=false;busyState(false);worker=new Worker(workerURL);
 worker.onmessage=({data:m})=>{
  if(m.type==='ready'){ready=true;busyState(false);status('准备就绪。拖动阈值预览，再执行 mincut。');}
  if(m.type==='progress')status(m.text);
  if(m.type==='cut'){
    clearTimeout(watchdog);last=m;state.final=true;renderer.setLabels(m.labels);window.__portrait.result=m.stats;busyState(false);
    status('mincut 已完成 · 最大流与切割容量一致');$('stats').textContent=`头部 ${m.stats.head.toLocaleString()} 面\n头发 ${m.stats.hair.toLocaleString()} 面\n计算 ${m.stats.seconds.toFixed(1)} 秒 · 没有删除三角面`;
    $('viewnote').textContent='正在显示 mincut 结果 · 所有原始三角面恰好归属一个部件';
  }
  if(m.type==='fbx'){
    clearTimeout(watchdog);window.__portrait.lastExportBytes=m.buffer.byteLength;const blob=new Blob([m.buffer],{type:'application/octet-stream'}),url=URL.createObjectURL(blob),a=document.createElement('a');
    a.href=url;a.download=`portrait-head-hair-${state.threshold.toFixed(4)}.fbx`;a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);status('FBX 已生成，包含 Head / Hair 和内嵌原纹理。');busyState(false);
  }
  if(m.type==='error'){clearTimeout(watchdog);status(m.message,true);busyState(false);console.error(m.stack);}
 };
 worker.onerror=e=>{clearTimeout(watchdog);status('后台计算出错：'+e.message,true);busyState(false);};
 worker.postMessage({type:'init',meta,buffer:raw});
}
function run(type){if(type==='cut'){last=null;state.final=false;}busyState(true);status(type==='cut'?'开始计算…':'正在生成 FBX…');watchdog=setTimeout(()=>{worker.terminate();last=null;state.final=false;ready=false;busyState(false);status('已到 300 秒预算，计算停止。点击重新初始化后再试。',true);$('process').textContent='重新初始化';$('process').disabled=false;},300000);worker.postMessage({type,threshold:state.threshold,...(type==='export'?{image:imageBytes.buffer}:{})});}
$('process').onclick=()=>{if(!ready){$('process').textContent='执行 mincut';startWorker();return;}run('cut');};
$('download').onclick=()=>run('export');
$('cancel').onclick=()=>{clearTimeout(watchdog);worker.terminate();last=null;state.final=false;startWorker();$('stats').textContent='';$('viewnote').textContent='计算已取消 · 当前为阈值预览';};
$('threshold').oninput=e=>{state.threshold=+e.target.value;$('value').value=state.threshold.toFixed(4);state.final=false;last=null;busyState(false);$('stats').textContent='';status('阈值已改变，当前显示快速预览。');$('viewnote').textContent='当前为阈值预览，并非最终 mincut 边界';};
function updateParts(){const head=$('show-head').checked,hair=$('show-hair').checked;state.part=head?(hair?0:1):(hair?2:3);}
$('show-head').onchange=updateParts;$('show-hair').onchange=updateParts;

function viewer(d){
 const canvas=$('canvas'),gl=canvas.getContext('webgl2',{antialias:true,alpha:false,preserveDrawingBuffer:true});if(!gl)throw Error('需要支持 WebGL2 的桌面浏览器');
 const camera=new THREE.PerspectiveCamera(35,1,.001,100),controls=new THREE.OrbitControls(camera,canvas);controls.enableDamping=true;
 const p=d.positions,lo=[Infinity,Infinity,Infinity],hi=[-Infinity,-Infinity,-Infinity];for(let i=0;i<p.length;i++) {const c=i%3;lo[c]=Math.min(lo[c],p[i]);hi[c]=Math.max(hi[c],p[i]);}
 const center=new THREE.Vector3(...lo.map((a,c)=>(a+hi[c])/2)),span=Math.max(...lo.map((a,c)=>hi[c]-a));controls.target.copy(center);camera.position.copy(center).add(new THREE.Vector3(0,0,span*2.05));camera.near=span*.01;camera.far=span*20;camera.updateProjectionMatrix();controls.minDistance=span*.55;controls.maxDistance=span*5;
 document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{const map={front:[0,0,1],back:[0,0,-1],left:[-1,0,0],right:[1,0,0]};camera.position.copy(center).add(new THREE.Vector3(...map[b.dataset.view]).multiplyScalar(span*2.05));controls.target.copy(center);controls.update();});
 const vs=`#version 300 es
 precision highp float;precision highp int;uniform highp usampler2D indices;uniform sampler2D positions,normals,brightness,classes;uniform mat4 projection,view;uniform float threshold;uniform int useFinal;out vec3 n;flat out float label;
 ivec2 at(int i){return ivec2(i%2048,i/2048);}void main(){int f=gl_VertexID/3;int v=int(texelFetch(indices,at(gl_VertexID),0).r);vec3 p=texelFetch(positions,at(v),0).xyz;n=texelFetch(normals,at(v),0).xyz;label=useFinal==1?texelFetch(classes,at(f),0).r:float(texelFetch(brightness,at(f),0).r>threshold);gl_Position=projection*view*vec4(p,1);}`;
 const fs=`#version 300 es
 precision highp float;uniform int visiblePart;in vec3 n;flat in float label;out vec4 color;void main(){if(visiblePart==3)discard;if(visiblePart==1&&label>.5)discard;if(visiblePart==2&&label<.5)discard;vec3 nn=normalize(n)*(gl_FrontFacing?1.:-1.);float light=.44+.4*max(dot(nn,normalize(vec3(-1.,1.5,2.))),0.)+.15*max(dot(nn,normalize(vec3(1.,.7,-1.))),0.);vec3 cls=mix(vec3(.44,.85,.88),vec3(.87,.66,.96),label);color=vec4(cls*light,1.);}`;
 function compile(type,src){const s=gl.createShader(type);gl.shaderSource(s,src);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s;}
 const program=gl.createProgram();gl.attachShader(program,compile(gl.VERTEX_SHADER,vs));gl.attachShader(program,compile(gl.FRAGMENT_SHADER,fs));gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(program));gl.useProgram(program);gl.bindVertexArray(gl.createVertexArray());
 const uniform=name=>gl.getUniformLocation(program,name);let unit=0;
 function texture(name,values,components,integer=false){const u=unit++,count=values.length/components,height=Math.ceil(count/2048),T=integer?Uint32Array:Float32Array,a=new T(2048*height*components);a.set(values);const t=gl.createTexture();gl.activeTexture(gl.TEXTURE0+u);gl.bindTexture(gl.TEXTURE_2D,t);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.NEAREST);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.NEAREST);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);const format=integer?gl.RED_INTEGER:components===1?gl.RED:components===2?gl.RG:gl.RGBA,internal=integer?gl.R32UI:components===1?gl.R32F:components===2?gl.RG32F:gl.RGBA32F;gl.texImage2D(gl.TEXTURE_2D,0,internal,2048,height,0,format,integer?gl.UNSIGNED_INT:gl.FLOAT,a);gl.uniform1i(uniform(name),u);return{t,u,height};}
 function pad4(a){const out=new Float32Array(a.length/3*4);for(let i=0,j=0;i<a.length;i+=3,j+=4){out[j]=a[i];out[j+1]=a[i+1];out[j+2]=a[i+2];}return out;}
 texture('indices',d.faces,1,true);texture('positions',pad4(d.positions),4);texture('normals',pad4(d.normals),4);texture('brightness',d.lum,1);const classTex=texture('classes',new Float32Array(meta.faces),1);
 const loc=Object.fromEntries(['projection','view','threshold','useFinal','visiblePart'].map(k=>[k,uniform(k)]));gl.enable(gl.DEPTH_TEST);gl.clearColor(.07,.095,.125,1);
 let frames=0;function draw(){const r=canvas.getBoundingClientRect(),scale=Math.min(devicePixelRatio,1.5),w=Math.max(1,Math.round(r.width*scale)),h=Math.max(1,Math.round(r.height*scale));if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;gl.viewport(0,0,w,h);camera.aspect=w/h;camera.updateProjectionMatrix();}controls.update();camera.updateMatrixWorld();camera.matrixWorldInverse.copy(camera.matrixWorld).invert();gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.uniformMatrix4fv(loc.projection,false,camera.projectionMatrix.elements);gl.uniformMatrix4fv(loc.view,false,camera.matrixWorldInverse.elements);gl.uniform1f(loc.threshold,state.threshold);gl.uniform1i(loc.useFinal,+state.final);gl.uniform1i(loc.visiblePart,state.part);gl.drawArrays(gl.TRIANGLES,0,meta.faces*3);window.__portrait.frames=++frames;requestAnimationFrame(draw);}draw();
 return{setLabels(a){const values=new Float32Array(2048*classTex.height);values.set(a);gl.activeTexture(gl.TEXTURE0+classTex.u);gl.bindTexture(gl.TEXTURE_2D,classTex.t);gl.texSubImage2D(gl.TEXTURE_2D,0,0,0,2048,classTex.height,gl.RED,gl.FLOAT,values);}};
}
(async()=>{try{
 const compressed=from64($('payload').textContent);$('payload').remove();raw=await new Response(new Blob([compressed]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();d=SplitCut.views(raw,meta);
 // Original image bytes and UVs are retained for FBX export only, not preview.
 imageBytes=from64($('texture').textContent);$('texture').remove();
 renderer=viewer(d);$('threshold').value=state.threshold;$('value').value=state.threshold.toFixed(4);$('facecount').textContent=meta.faces.toLocaleString();$('vertexcount').textContent=meta.vertices.toLocaleString();$('loading').remove();
 workerURL=URL.createObjectURL(new Blob([$('worker-code').textContent],{type:'text/javascript'}));$('worker-code').remove();startWorker();window.__portrait.ready=true;
 }catch(e){status(e.message,true);$('loadtext').textContent=e.message;console.error(e);}})();
