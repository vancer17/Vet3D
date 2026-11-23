const $ = (id) => document.getElementById(id);
const state = {style:'04',scene:'bedside',goal:'full',complexity:'balanced',notes:'',step:0,view:'image',light:'on'};
const scenes={bedside:'床头氛围',desk:'书桌陪伴',accent:'客厅艺术摆件'};
const goals={full:'交给 Codex，完成全流程',concepts:'交给 Codex，本次只出图',fdm:'交给 Codex，本次只做工程包',lighting:'交给 Codex，本次只迭代光效'};
let catalog=[], viewer, modelPromise, savedBrief, generation=0;
const sessionToken=location.pathname.split('/')[2];
const base=new URL('./',location.href);
function asset(file){return new URL(`media/${state.style}/${file}`,base).href;}
function showError(message){$('error').textContent=message;$('error').hidden=false;}
function clearReceipt(){savedBrief=undefined;$('receipt').hidden=true;$('submit').disabled=false;$('submit').hidden=state.step!==2;$('error').hidden=true;}
function updateChoices(){
 document.querySelectorAll('[data-field]').forEach(group=>group.querySelectorAll('button').forEach(button=>button.setAttribute('aria-pressed',String(state[group.dataset.field]===button.dataset.value))));
 document.querySelectorAll('[data-style]').forEach(button=>button.setAttribute('aria-pressed',String(state.style===button.dataset.style)));
 const style=catalog.find(x=>x.id===state.style);$('summary').textContent=`${style?.title||''} · ${scenes[state.scene]} · ${state.complexity==='rich'?'曲面更丰富':state.complexity==='quiet'?'简洁克制':'丰富而清楚'}`;
 $('submit').replaceChildren(document.createTextNode(goals[state.goal]+' '));const arrow=document.createElement('span');arrow.setAttribute('aria-hidden','true');arrow.textContent='↗';$('submit').append(arrow);
}
function step(n){state.step=n;for(let i=0;i<3;i++)$('step'+i).hidden=i!==n;document.querySelectorAll('[data-step]').forEach(b=>n===Number(b.dataset.step)?b.setAttribute('aria-current','step'):b.removeAttribute('aria-current'));$('back').hidden=n===0;$('next').hidden=n===2;$('submit').hidden=n!==2||!!savedBrief;$('next').textContent=n===0?'下一步 · 选用途 ↗':'下一步 · 开始设计 ↗';updateChoices();}
async function loadViewer(){
 if(!modelPromise){window.ModelViewerElement={dracoDecoderLocation:new URL('vendor/draco/',base).href};modelPromise=import('./vendor/model-viewer.min.js').catch(e=>{modelPromise=null;throw e;});}
 await modelPromise;
 if(!viewer){viewer=document.createElement('model-viewer');viewer.setAttribute('camera-controls','');viewer.setAttribute('touch-action','pan-y');viewer.setAttribute('environment-image','neutral');viewer.setAttribute('shadow-intensity','1');viewer.setAttribute('interaction-prompt','none');viewer.setAttribute('camera-orbit','25deg 75deg auto');viewer.addEventListener('load',()=>{$('model-status').hidden=true;$('reset-view').disabled=false;});viewer.addEventListener('error',()=>mediaError());$('model-holder').append(viewer);}
 return viewer;
}
function mediaError(){const file=state.view==='model'?'lamp.glb':state.light+(state.view==='video'?'.mp4':'.png');$('media-error').hidden=false;$('model-status').hidden=true;$('media-download').href=asset(file);}
async function preview(){
 const current=++generation;const style=catalog.find(x=>x.id===state.style);if(!style)return;
 $('preview-title').textContent=style.name+' / '+style.title;$('preview-description').textContent=style.description;
 document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===state.view)));
 document.querySelectorAll('[data-light]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.light===state.light)));
 $('preview-video').pause();$('media-error').hidden=true;$('model-status').hidden=true;
 $('preview-image').hidden=state.view!=='image';$('preview-video').hidden=state.view!=='video';$('model-holder').hidden=state.view!=='model';$('light-toggle').hidden=state.view==='model';$('reset-view').hidden=state.view!=='model';
 $('preview-caption').textContent=state.view==='model'?'拖动旋转 · 双指缩放 · 3D 用于看形状':state.view==='video'?'4 秒真实渲染 · 点击播放 · 可切换开关灯':'真实场景渲染 · 点击开关看变化';
 if(state.view==='image'){$('preview-image').alt=style.name+(state.light==='on'?'开灯':'关灯')+'示例';$('preview-image').src=asset(state.light+'.png');}
 if(state.view==='video'){const video=$('preview-video');video.src=asset(state.light+'.mp4');video.poster=asset(state.light+'.png');video.setAttribute('aria-label',style.name+(state.light==='on'?'开灯':'关灯')+'环绕影片');video.load();}
 if(state.view==='model'){
  $('model-status').hidden=false;$('reset-view').disabled=true;
  try{const el=await loadViewer();if(current!==generation)return;el.alt=style.name+'可旋转三维样机';const src=asset('lamp.glb');if(el.src===src&&el.loaded){$('model-status').hidden=true;$('reset-view').disabled=false;}else{el.poster=asset('off.png');el.src=src;}}
  catch{if(current===generation)mediaError();}
 }
}
async function init(){
 try{const response=await fetch('catalog.json');if(!response.ok)throw new Error();const data=await response.json();catalog=data.styles;state.style=data.default_style;}
 catch{showError('示例素材未能载入，请从 Codex 重新打开体验入口。');$('next').disabled=true;return;}
 for(const item of catalog){const button=document.createElement('button');button.type='button';button.className='style-card';button.dataset.style=item.id;button.setAttribute('aria-label',item.title+'，'+item.description);const img=document.createElement('img');img.src=`media/${item.id}/off.png`;img.alt=item.name+'关灯造型';const tick=document.createElement('span');tick.className='tick';tick.textContent='✓';tick.setAttribute('aria-hidden','true');const text=document.createElement('span');text.className='card-text';const title=document.createElement('b');title.textContent=item.title;const sub=document.createElement('small');sub.textContent=item.description;text.append(title,sub);button.append(img,tick,text);button.onclick=()=>{state.style=item.id;clearReceipt();updateChoices();preview();};$('style-cards').append(button);}
 updateChoices();preview();
 try{const response=await fetch('api/selection');if(response.ok){const value=(await response.json()).selection;if(value){Object.assign(state,value.selection);$('notes').value=state.notes;updateChoices();preview();}}}catch{}
}
$('next').onclick=()=>step(state.step+1);$('back').onclick=()=>step(state.step-1);
document.querySelectorAll('[data-step]').forEach(b=>b.onclick=()=>step(Number(b.dataset.step)));
document.querySelectorAll('[data-field]').forEach(group=>group.querySelectorAll('button').forEach(b=>b.onclick=()=>{state[group.dataset.field]=b.dataset.value;clearReceipt();updateChoices();}));
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{state.view=b.dataset.view;preview();});document.querySelectorAll('[data-light]').forEach(b=>b.onclick=()=>{state.light=b.dataset.light;preview();});
$('notes').oninput=()=>{state.notes=$('notes').value;clearReceipt();};$('preview-image').onerror=mediaError;$('preview-video').onerror=mediaError;
$('reset-view').onclick=()=>{if(viewer){viewer.cameraOrbit='25deg 75deg auto';viewer.cameraTarget='auto auto auto';viewer.fieldOfView='30deg';viewer.jumpCameraToGoal();}};
$('submit').onclick=async()=>{
 $('submit').disabled=true;$('error').hidden=true;
 try{const {style,scene,goal,complexity,notes}=state;const response=await fetch('api/selection',{method:'POST',headers:{'Content-Type':'application/json','X-Lamp-Session':sessionToken},body:JSON.stringify({style,scene,goal,complexity,notes})});const result=await response.json();if(!response.ok)throw new Error(result.error||'暂时未能保存，请重试。');savedBrief=result.brief;$('receipt').hidden=false;$('submit').hidden=true;$('receipt').scrollIntoView({block:'nearest',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});}
 catch(e){showError(e.message||'暂时未能保存，请重试。');$('submit').disabled=false;}
};
$('edit').onclick=()=>{clearReceipt();step(0);};$('copy-brief').onclick=async()=>{if(!savedBrief)return;try{await navigator.clipboard.writeText(savedBrief.prompt);$('copy-brief').textContent='已复制';}catch{showError('此浏览器未允许复制，请下载需求记录。');}};
init();
