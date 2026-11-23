/** Swept axis-aligned box versus static box, normalized frame time [0,1]. */
export function sweep(box,delta,obstacle){
 const valid=b=>b&&Array.isArray(b.min)&&Array.isArray(b.max)&&b.min.length===3&&b.max.length===3&&b.min.every((v,i)=>Number.isFinite(v)&&Number.isFinite(b.max[i])&&v<b.max[i]);
 if(!valid(box)||!valid(obstacle)||!Array.isArray(delta)||delta.length!==3||!delta.every(Number.isFinite))throw new Error('invalid AABB sweep');
 if(box.min.every((v,i)=>v<obstacle.max[i]&&box.max[i]>obstacle.min[i]))return {hit:true,time:0,normal:[0,0,0],overlap:true};
 let entry=-Infinity,exit=Infinity,axis=-1;
 for(let i=0;i<3;i++){
  if(delta[i]===0){if(box.max[i]<=obstacle.min[i]||box.min[i]>=obstacle.max[i])return {hit:false};continue;}
  const a=(obstacle.min[i]-box.max[i])/delta[i],b=(obstacle.max[i]-box.min[i])/delta[i];
  const lo=Math.min(a,b),hi=Math.max(a,b);if(lo>entry){entry=lo;axis=i;}exit=Math.min(exit,hi);
 }
 if(entry>exit||entry<0||entry>1||exit<0||axis<0)return {hit:false};
 const normal=[0,0,0];normal[axis]=-Math.sign(delta[axis]);return {hit:true,time:entry,normal,overlap:false};
}
