/** Fixed-step simulation clock. Explicit seconds; no timers or global state. */
export function createClock({hz=60,maxSteps=8}={}){
 if(!Number.isFinite(hz)||hz<=0||hz>1000||!Number.isSafeInteger(maxSteps)||maxSteps<1||maxSteps>1000)throw new RangeError('invalid clock configuration');
 return {dt:1/hz,maxSteps,tick:0,remainder:0,paused:false,dropped:0};
}
export function advance(clock,elapsed){
 if(!Number.isFinite(elapsed)||elapsed<0)throw new RangeError('elapsed must be nonnegative seconds');
 if(clock.paused)return {clock:{...clock},steps:0};
 const total=clock.remainder+elapsed;
 if(!Number.isFinite(total)||total/clock.dt>Number.MAX_SAFE_INTEGER)throw new RangeError('elapsed exceeds clock range');
 const due=Math.floor((total+clock.dt*1e-9)/clock.dt),steps=Math.min(due,clock.maxSteps);
 if(!Number.isSafeInteger(clock.tick+steps))throw new RangeError('tick overflow');
 return {steps,clock:{...clock,tick:clock.tick+steps,remainder:Math.max(0,total-due*clock.dt),dropped:clock.dropped+(due-steps)*clock.dt}};
}
export function pause(clock,paused=true){return {...clock,paused:Boolean(paused),remainder:0};}
export function transition(state,event){
 const graph={ready:{start:'playing'},playing:{pause:'paused',win:'won',lose:'lost',fail:'error'},paused:{resume:'playing',restart:'ready'},won:{restart:'ready'},lost:{restart:'ready'},error:{restart:'ready'}};
 const next=graph[state]?.[event];if(!next)throw new Error(`invalid transition ${state}/${event}`);return next;
}
