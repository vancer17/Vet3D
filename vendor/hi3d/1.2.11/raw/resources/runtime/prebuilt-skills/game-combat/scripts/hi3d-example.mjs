import * as m from './hi3d-core.mjs';
const s={match:'a',tick:0,units:{p:{hp:10,team:0,readyAt:0},e:{hp:3,team:1,readyAt:0}}};console.log(m.strike(s,{match:'a',attacker:'p',target:'e',tick:0},{damage:4,cooldown:2}));
