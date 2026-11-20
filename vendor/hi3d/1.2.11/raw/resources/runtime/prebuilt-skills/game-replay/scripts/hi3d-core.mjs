/** Bounded deterministic reducer replay; no eval or user scripts. */
export function replay(initial,commands,reducer,{maxCommands=10000,invariant=()=>true}={}){
 if(!Array.isArray(commands)||!Number.isSafeInteger(maxCommands)||maxCommands<0||maxCommands>100000||commands.length>maxCommands||typeof reducer!=='function')throw new Error('invalid replay');
 let state=structuredClone(initial);const trace=[];if(invariant(state)!==true)throw new Error('initial invariant');
 for(let i=0;i<commands.length;i++){const next=reducer(structuredClone(state),structuredClone(commands[i]));if(invariant(next)!==true)throw new Error(`invariant failed at ${i}`);state=structuredClone(next);trace.push(structuredClone(state));}
 return {state,trace};
}
export function seededRandom(seed){if(!Number.isSafeInteger(seed)||seed<0||seed>0xffffffff)throw new Error('invalid seed');let value=seed;return ()=>{value=(Math.imul(1664525,value)+1013904223)>>>0;return value/4294967296;};}
