import test from 'node:test';
import assert from 'node:assert/strict';
import * as m from '../scripts/hi3d-core.mjs';
const s={match:'a',tick:0,units:{p:{hp:10,team:0,readyAt:0},e:{hp:8,team:1,readyAt:0}}};const cmd={match:'a',attacker:'p',target:'e',tick:0};
 test('damage, cooldown and stale callbacks',()=>{const r=m.strike(s,cmd,{damage:3,cooldown:2});assert.equal(r.state.units.e.hp,5);assert.equal(s.units.e.hp,8);assert.equal(m.strike(r.state,cmd,{damage:3,cooldown:2}).events.length,0);assert.throws(()=>m.strike(s,{...cmd,match:'old'},{damage:3,cooldown:2}));});
 test('death emits once, no negative hp',()=>{const r=m.strike(s,cmd,{damage:99,cooldown:1});assert.equal(r.state.units.e.hp,0);assert.equal(r.events.at(-1).type,'defeated');assert.equal(m.strike(r.state,{...cmd,tick:2},{damage:99,cooldown:1}).events.length,0);});
