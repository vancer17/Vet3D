/** Declarative graph-level checks. No scripts, assets, or expressions executed. */
export function validateLevel(level){
 const issues=[];if(!level||!Array.isArray(level.nodes)||!Array.isArray(level.edges)||level.nodes.length>10000||level.edges.length>100000)return {valid:false,issues:['invalid graph'],reachable:[]};
 const ids=new Set();for(const n of level.nodes){if(!n||typeof n.id!=='string'||!n.id||ids.has(n.id)){issues.push('invalid or duplicate node');continue;}ids.add(n.id);}
 if(!ids.has(level.start)||!Array.isArray(level.goals)||!level.goals.length||!level.goals.every(x=>ids.has(x)))issues.push('missing start or goals');
 const adj=new Map([...ids].map(id=>[id,[]]));for(const e of level.edges){if(!Array.isArray(e)||e.length!==2||!ids.has(e[0])||!ids.has(e[1]))issues.push('dangling edge');else adj.get(e[0]).push(e[1]);}
 if(issues.length)return {valid:false,issues,reachable:[]};
 const seen=new Set([level.start]),queue=[level.start];for(let i=0;i<queue.length;i++)for(const n of adj.get(queue[i]))if(!seen.has(n)){seen.add(n);queue.push(n);}
 for(const goal of level.goals)if(!seen.has(goal))issues.push(`unreachable goal: ${goal}`);
 return {valid:!issues.length,issues,reachable:[...seen]};
}
