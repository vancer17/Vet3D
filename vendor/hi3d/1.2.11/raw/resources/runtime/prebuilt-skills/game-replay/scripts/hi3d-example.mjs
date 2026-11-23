import * as m from './hi3d-core.mjs';
console.log(m.replay({x:0},[1,2,3],(s,c)=>({x:s.x+c})));
