import * as m from './hi3d-core.mjs';
const s={order:'o',user:'u',product:'p',revision:0,status:'pending',events:[]};console.log(m.applyEvent(s,{id:'e',order:'o',user:'u',product:'p',revision:1,status:'paid'}));
