import test from 'node:test';
import assert from 'node:assert/strict';
import * as m from '../scripts/hi3d-core.mjs';
test('repeatable commands and invariant failures',()=>{const s={x:0},commands=[1,2];const run=()=>m.replay(s,commands,(a,b)=>({x:a.x+b}));assert.deepEqual(run(),run());assert.deepEqual(s,{x:0});assert.throws(()=>m.replay(s,[1],()=>({x:-1}),{invariant:s=>s.x>=0}));assert.throws(()=>m.replay(s,[1],x=>x,{maxCommands:0}));});
 test('seed reproducibility',()=>{const a=m.seededRandom(7),b=m.seededRandom(7);for(let i=0;i<100;i++){const x=a();assert.equal(x,b());assert(x>=0&&x<1);}assert.throws(()=>m.seededRandom(-1));});
