/** Session/sequence acceptance; no transport, authentication or authority claim. */
export function acceptSnapshot(current,incoming){
 if(!incoming||typeof incoming.session!=='string'||!Number.isSafeInteger(incoming.seq)||incoming.seq<0||!Number.isSafeInteger(incoming.tick)||incoming.tick<0)throw new Error('invalid snapshot');
 if(incoming.session!==current.session)return {accepted:false,reason:'session',snapshot:current};
 if(incoming.seq<=current.seq||incoming.tick<current.tick)return {accepted:false,reason:'stale',snapshot:current};
 return {accepted:true,reason:null,snapshot:structuredClone(incoming)};
}
export function interpolate(a,b,time){
 if(![a.time,a.x,a.y,a.z,b.time,b.x,b.y,b.z,time].every(Number.isFinite)||b.time<=a.time)throw new Error('invalid interpolation interval');
 const t=Math.max(0,Math.min(1,(time-a.time)/(b.time-a.time)));return {x:a.x+(b.x-a.x)*t,y:a.y+(b.y-a.y)*t,z:a.z+(b.z-a.z)*t};
}
export function retryDelay(attempt,{base=250,max=10000,maxAttempts=5}={}){if(!Number.isSafeInteger(attempt)||attempt<0||!Number.isSafeInteger(maxAttempts)||maxAttempts<1||maxAttempts>100||![base,max].every(n=>Number.isFinite(n)&&n>0))throw new Error('invalid retry config');return attempt>=maxAttempts?null:Math.min(max,base*2**attempt);}
