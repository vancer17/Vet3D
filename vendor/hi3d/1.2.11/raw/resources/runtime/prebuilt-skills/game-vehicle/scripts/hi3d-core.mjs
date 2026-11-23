/** Planar kinematic bicycle, SI units. No tyres, suspension or contact solver. */
export function drive(state,input,dt,config){
 const {wheelbase,maxSpeed,acceleration,drag,maxSteer}=config;
 if(![state.x,state.z,state.heading,state.speed,input.throttle,input.steer,dt,wheelbase,maxSpeed,acceleration,drag,maxSteer].every(Number.isFinite)||dt<0||dt>0.1||wheelbase<=0||maxSpeed<=0||acceleration<0||drag<0||maxSteer<0||maxSteer>=Math.PI/2)throw new Error('invalid vehicle input');
 const clamp=n=>Math.max(-1,Math.min(1,n));
 const speed=Math.max(-maxSpeed,Math.min(maxSpeed,(state.speed+clamp(input.throttle)*acceleration*dt)*Math.exp(-drag*dt)));
 const heading=state.heading+speed/wheelbase*Math.tan(clamp(input.steer)*maxSteer)*dt;
 return {x:state.x+Math.sin(heading)*speed*dt,z:state.z+Math.cos(heading)*speed*dt,heading:Math.atan2(Math.sin(heading),Math.cos(heading)),speed};
}
export function checkpoint(state,index,total){if(!Number.isSafeInteger(total)||total<1||!Number.isSafeInteger(index)||index<0||index>=total||!Number.isSafeInteger(state.next)||state.next<0||state.next>=total||!Number.isSafeInteger(state.laps)||state.laps<0)throw new Error('invalid checkpoint');if(index!==state.next)return state;return {next:(index+1)%total,laps:state.laps+(index===total-1?1:0)};}
