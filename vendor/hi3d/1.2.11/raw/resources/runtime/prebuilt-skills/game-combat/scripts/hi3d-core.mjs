/** Deterministic single-target damage/cooldown resolution; caller owns hit detection. */
export function strike(state,command,rules){
 const {attacker,target,tick,match}=command;
 if(match!==state.match)throw new Error('stale match');
 if(!Number.isSafeInteger(tick)||tick<state.tick)throw new Error('nonmonotonic tick');
 if(![rules.damage,rules.cooldown].every(n=>Number.isSafeInteger(n)&&n>=0)||rules.cooldown<1)throw new Error('invalid combat rules');
 const a=state.units[attacker],b=state.units[target];
 if(!a||!b||attacker===target)throw new Error('unknown or self target');
 if(![a.hp,b.hp,a.readyAt].every(n=>Number.isSafeInteger(n)&&n>=0))throw new Error('invalid unit');
 if(a.hp===0||b.hp===0||a.team===b.team||tick<a.readyAt)return {state,events:[]};
 if(!Number.isSafeInteger(tick+rules.cooldown))throw new Error('tick overflow');
 const hp=Math.max(0,b.hp-rules.damage),damage=b.hp-hp;
 return {state:{...state,tick,units:{...state.units,[attacker]:{...a,readyAt:tick+rules.cooldown},[target]:{...b,hp}}},events:[{type:'damage',attacker,target,damage},...(hp===0?[{type:'defeated',target}]:[])]};
}
