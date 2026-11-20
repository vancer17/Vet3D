import test from 'node:test';
import assert from 'node:assert/strict';
import * as m from '../scripts/hi3d-core.mjs';
const s={x:0,z:0,heading:0,speed:0},c={wheelbase:2,maxSpeed:20,acceleration:5,drag:.1,maxSteer:.5};
 test('drive stationary straight and capped',()=>{assert.deepEqual(m.drive(s,{throttle:0,steer:1},.1,c),s);let r=m.drive(s,{throttle:1,steer:0},.1,c);assert(r.z>0);assert.equal(r.x,0);for(let i=0;i<1000;i++)r=m.drive(r,{throttle:1,steer:.5},.1,c);assert(r.speed<=20);assert.throws(()=>m.drive(s,{throttle:0,steer:0},1,c));});
 test('ordered checkpoints',()=>{let r={next:0,laps:0};assert.equal(m.checkpoint(r,1,3),r);for(let i=0;i<3;i++)r=m.checkpoint(r,i,3);assert.deepEqual(r,{next:0,laps:1});});
